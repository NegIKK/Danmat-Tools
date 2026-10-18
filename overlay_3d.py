import bpy
import gpu
import time
from dataclasses import dataclass
from mathutils import Vector
from gpu_extras.batch import batch_for_shader


DEFAULT_COLOR = (1.0, 1.0, 1.0, 1.0)
DEFAULT_LINE_WIDTH = 2.0
DEFAULT_POINT_SIZE = 0.05


# =====================================================================
# INTERNAL DATA
# =====================================================================

@dataclass
class _LineFx:
    start: Vector
    end: Vector
    color: tuple
    width: float
    overlay: bool
    start_time: float
    appear: float
    fade: float
    peak_alpha: float
    rest_alpha: float
    delay: float


@dataclass
class _PointFx:
    pos: Vector
    color: tuple
    size: float
    overlay: bool
    start_time: float
    appear: float
    fade: float
    peak_alpha: float
    rest_alpha: float
    delay: float


@dataclass
class _TriFx:
    v0: Vector
    v1: Vector
    v2: Vector
    color: tuple
    overlay: bool
    start_time: float
    appear: float
    fade: float
    peak_alpha: float
    rest_alpha: float
    delay: float


_lines = []
_points = []
_tris = []

_draw_handler = None
_timer_handle = None
_shader_cache = None


# =====================================================================
# HELPERS
# =====================================================================

def _clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return float(value)


def _smoothstep(value: float) -> float:
    value = _clamp01(value)
    return value * value * (3.0 - 2.0 * value)


def _to_rgba(color) -> tuple:
    """
    Принимает RGB или RGBA, всегда возвращает RGBA.
    """
    if color is None:
        return DEFAULT_COLOR

    try:
        if len(color) == 3:
            return (
                float(color[0]),
                float(color[1]),
                float(color[2]),
                1.0,
            )

        if len(color) >= 4:
            return (
                float(color[0]),
                float(color[1]),
                float(color[2]),
                float(color[3]),
            )
    except Exception:
        pass

    return DEFAULT_COLOR


def _as_vector(value):
    """
    Безопасно приводит входные данные к mathutils.Vector.
    """
    if value is None:
        return None

    if isinstance(value, Vector):
        return value.copy()

    try:
        return Vector(value)
    except Exception:
        return None


def _as_indices(indices):
    """
    Принимает int, list, tuple, range, set и возвращает tuple[int, ...].
    """
    if indices is None:
        return ()

    if isinstance(indices, int):
        return (indices,)

    try:
        return tuple(int(i) for i in indices)
    except Exception:
        return ()


def _get_mesh(obj):
    """
    Возвращает Mesh, если объект его содержит.
    Для v1 используем obj.data.
    """
    if obj is None:
        return None

    me = getattr(obj, "data", None)
    if isinstance(me, bpy.types.Mesh):
        return me

    return None


def _alpha_multiplier(item, now: float) -> float:
    """
    Возвращает множитель альфы 0..1.

    Логика:
    - delay: эффект еще не начался.
    - appear: плавное появление от 0 до peak_alpha.
    - fade: плавное затухание от peak_alpha до rest_alpha.
    - если appear=0 и fade=0: статичный эффект.
    """
    elapsed = now - item.start_time - item.delay
    total_duration = item.appear + item.fade

    if total_duration <= 0.0:
        return 1.0 if elapsed >= 0.0 else 0.0

    if elapsed <= 0.0:
        return 0.0

    # Fade-in.
    if item.appear > 0.0 and elapsed < item.appear:
        t = elapsed / item.appear
        return item.peak_alpha * _smoothstep(t)

    after_appear = elapsed - item.appear

    # Нет fade-out: держим peak_alpha.
    if item.fade <= 0.0:
        return item.peak_alpha

    # Fade-out закончился.
    if after_appear >= item.fade:
        return item.rest_alpha

    # Ease-out quadratic.
    t = after_appear / item.fade
    ease_out = (1.0 - t) * (1.0 - t)
    return item.rest_alpha + (item.peak_alpha - item.rest_alpha) * ease_out


def _is_expired(item, now: float) -> bool:
    """
    Эффект удаляется только если он полностью отыграл и rest_alpha ~= 0.
    Если rest_alpha > 0, эффект остается статичным следом.
    """
    total_duration = item.appear + item.fade
    if total_duration <= 0.0:
        return False

    elapsed = now - item.start_time - item.delay
    return elapsed >= total_duration and item.rest_alpha <= 0.0001


def _needs_timer(item, now: float) -> bool:
    """
    Таймер нужен только пока эффект анимируется или ждет delay.
    """
    total_duration = item.appear + item.fade
    if total_duration <= 0.0:
        return False

    elapsed = now - item.start_time - item.delay
    return elapsed < total_duration


def _prune(items: list, now: float) -> None:
    """
    Удаляет протухшие эффекты на месте.
    """
    write = 0
    for item in items:
        if not _is_expired(item, now):
            items[write] = item
            write += 1
    del items[write:]


def _has_active_fx(now: float) -> bool:
    for item in _lines:
        if _needs_timer(item, now):
            return True
    for item in _points:
        if _needs_timer(item, now):
            return True
    for item in _tris:
        if _needs_timer(item, now):
            return True
    return False


def _tag_redraw() -> None:
    """
    Принудительно перерисовывает все 3D-вьюпорты.
    """
    try:
        wm = bpy.context.window_manager
        for window in wm.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
    except Exception:
        pass


def _fx_timer():
    global _timer_handle

    now = time.monotonic()

    if not _has_active_fx(now):
        _timer_handle = None
        return None

    _tag_redraw()

    # ~60 FPS.
    return 0.016


def _ensure_timer() -> None:
    global _timer_handle

    if _timer_handle is not None:
        return

    now = time.monotonic()
    if not _has_active_fx(now):
        return

    try:
        _timer_handle = bpy.app.timers.register(
            _fx_timer,
            first_interval=0.016,
        )
    except Exception:
        _timer_handle = None


def _get_shader():
    """
    Кэширует шейдер.

    [Неизвестно] В Blender 5.0.1 точный список builtin-шейдеров.
    Поэтому пробуем несколько распространенных имен.
    """
    global _shader_cache

    if _shader_cache is not None:
        return _shader_cache

    last_error = None

    for shader_name in (
        'SMOOTH_COLOR',
        '3D_SMOOTH_COLOR',
        'FLAT_COLOR',
    ):
        try:
            _shader_cache = gpu.shader.from_builtin(shader_name)
            return _shader_cache
        except Exception as exc:
            last_error = exc

    raise RuntimeError(
        f"overlay_3d: failed to load supported builtin shader. Last error: {last_error}"
    )


def _get_camera_basis():
    """
    Возвращает (right, up) в мировых координатах, перпендикулярные взгляду камеры.
    Используется для бильборд-квадратов вместо POINTS.
    """
    view_dir = Vector((0.0, 0.0, -1.0))
    found = False

    # Сначала пробуем текущий контекст. В draw handler он обычно указывает
    # на тот viewport, который сейчас рисуется.
    try:
        area = bpy.context.area
        if area is not None and area.type == 'VIEW_3D':
            space = area.spaces.active
            rv3d = space.region_3d
            view_dir = rv3d.view_rotation @ Vector((0.0, 0.0, -1.0))
            found = True
    except Exception:
        pass

    # Fallback: первый найденный 3D viewport.
    if not found:
        try:
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        rv3d = area.spaces.active.region_3d
                        view_dir = rv3d.view_rotation @ Vector((0.0, 0.0, -1.0))
                        found = True
                        break
                if found:
                    break
        except Exception:
            pass

    if view_dir.length < 1e-6:
        view_dir = Vector((0.0, 0.0, -1.0))
    else:
        view_dir.normalize()

    up_ref = Vector((0.0, 0.0, 1.0))
    if abs(view_dir.dot(up_ref)) > 0.99:
        up_ref = Vector((0.0, 1.0, 0.0))

    right = view_dir.cross(up_ref)
    if right.length < 1e-6:
        right = Vector((1.0, 0.0, 0.0))
    else:
        right.normalize()

    up = right.cross(view_dir)
    if up.length < 1e-6:
        up = Vector((0.0, 1.0, 0.0))
    else:
        up.normalize()

    return right, up


def _set_draw_state(overlay: bool) -> None:
    """
    overlay=True  — рисуем поверх всего, без depth test.
    overlay=False — уважаем глубину вьюпорта.
    """
    try:
        gpu.state.blend_set('ALPHA')
    except Exception:
        pass

    try:
        if overlay:
            gpu.state.depth_test_set('NONE')
        else:
            gpu.state.depth_test_set('LESS')
    except Exception:
        pass

    try:
        # Оверлеи не должны писать в depth buffer.
        gpu.state.depth_write_set(False)
    except Exception:
        pass


def _reset_draw_state() -> None:
    """
    Возвращаем базовые состояния.
    """
    try:
        gpu.state.blend_set('NONE')
    except Exception:
        pass

    try:
        gpu.state.depth_test_set('LESS')
    except Exception:
        pass

    try:
        gpu.state.depth_write_set(True)
    except Exception:
        pass

    try:
        gpu.state.face_culling_set('BACK')
    except Exception:
        pass

    try:
        gpu.state.line_width_set(1.0)
    except Exception:
        pass

    try:
        gpu.state.point_size_set(1.0)
    except Exception:
        pass


# =====================================================================
# DRAW CALLBACK
# =====================================================================

def _draw_lines(shader, now: float) -> None:
    if not _lines:
        return

    groups = {}

    for item in _lines:
        mult = _alpha_multiplier(item, now)
        if mult <= 0.001:
            continue

        alpha = _clamp01(item.color[3] * mult)
        if alpha <= 0.001:
            continue

        color = (
            item.color[0],
            item.color[1],
            item.color[2],
            alpha,
        )

        key = (item.overlay, item.width)
        groups.setdefault(key, []).append((item.start, item.end, color))

    if not groups:
        return

    # Сначала depth-aware, потом overlay поверх всего.
    for (overlay, width), items in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        coords = []
        colors = []

        for start, end, color in items:
            coords.append(start)
            coords.append(end)
            colors.append(color)
            colors.append(color)

        if not coords:
            continue

        _set_draw_state(overlay)

        try:
            gpu.state.line_width_set(width)
        except Exception:
            pass

        batch = batch_for_shader(
            shader,
            'LINES',
            {"pos": coords, "color": colors},
        )

        shader.bind()
        batch.draw(shader)


def _draw_points(shader, now: float) -> None:
    """
    Рисует точки как бильборд-квадраты.

    Это сделано специально вместо gpu POINTS, потому что point_size_set()
    на некоторых GPU/драйверах игнорируется или ограничивается 1 пикселем.

    ВАЖНО:
    size здесь — мировой размер стороны квадрата, не пиксели.
    """
    if not _points:
        return

    right, up = _get_camera_basis()

    groups = {}

    for item in _points:
        mult = _alpha_multiplier(item, now)
        if mult <= 0.001:
            continue

        alpha = _clamp01(item.color[3] * mult)
        if alpha <= 0.001:
            continue

        color = (
            item.color[0],
            item.color[1],
            item.color[2],
            alpha,
        )

        groups.setdefault(item.overlay, []).append((item.pos, item.size, color))

    if not groups:
        return

    culling_changed = False
    try:
        gpu.state.face_culling_set('NONE')
        culling_changed = True
    except Exception:
        pass

    try:
        for overlay, items in sorted(groups.items(), key=lambda kv: kv[0]):
            coords = []
            colors = []

            _set_draw_state(overlay)

            for pos, size, color in items:
                half = max(1e-6, float(size)) * 0.5

                p1 = pos + right * (-half) + up * (-half)
                p2 = pos + right * (half) + up * (-half)
                p3 = pos + right * (half) + up * (half)
                p4 = pos + right * (-half) + up * (half)

                # Два треугольника:
                # p1-p2-p3 и p1-p3-p4
                coords.extend((p1, p2, p3))
                colors.extend((color, color, color))

                coords.extend((p1, p3, p4))
                colors.extend((color, color, color))

            if not coords:
                continue

            batch = batch_for_shader(
                shader,
                'TRIS',
                {"pos": coords, "color": colors},
            )

            shader.bind()
            batch.draw(shader)
    finally:
        if culling_changed:
            try:
                gpu.state.face_culling_set('BACK')
            except Exception:
                pass


def _draw_tris(shader, now: float) -> None:
    if not _tris:
        return

    groups = {}

    for item in _tris:
        mult = _alpha_multiplier(item, now)
        if mult <= 0.001:
            continue

        alpha = _clamp01(item.color[3] * mult)
        if alpha <= 0.001:
            continue

        color = (
            item.color[0],
            item.color[1],
            item.color[2],
            alpha,
        )

        groups.setdefault(item.overlay, []).append((item.v0, item.v1, item.v2, color))

    if not groups:
        return

    culling_changed = False
    try:
        gpu.state.face_culling_set('NONE')
        culling_changed = True
    except Exception:
        pass

    try:
        for overlay, items in sorted(groups.items(), key=lambda kv: kv[0]):
            coords = []
            colors = []

            _set_draw_state(overlay)

            for v0, v1, v2, color in items:
                coords.extend((v0, v1, v2))
                colors.extend((color, color, color))

            if not coords:
                continue

            batch = batch_for_shader(
                shader,
                'TRIS',
                {"pos": coords, "color": colors},
            )

            shader.bind()
            batch.draw(shader)
    finally:
        if culling_changed:
            try:
                gpu.state.face_culling_set('BACK')
            except Exception:
                pass


def draw_overlay_3d_callback() -> None:
    now = time.monotonic()

    _prune(_lines, now)
    _prune(_points, now)
    _prune(_tris, now)

    if not (_lines or _points or _tris):
        return

    try:
        shader = _get_shader()
    except Exception as exc:
        print(f"[overlay_3d] shader error: {exc}")
        return

    try:
        _draw_lines(shader, now)
        _draw_points(shader, now)
        _draw_tris(shader, now)
    finally:
        _reset_draw_state()


# =====================================================================
# PUBLIC LOW-LEVEL API
# =====================================================================

def draw_line(
    start,
    end,
    color=None,
    width=None,
    fade: float = 0.0,
    appear: float = 0.0,
    peak_alpha: float = 1.0,
    rest_alpha: float = 1.0,
    delay: float = 0.0,
    overlay: bool = True,
) -> None:
    """
    Мирная 3D-линия.

    Параметры:
    - start/end: Vector или tuple/list из 3 чисел.
    - color: RGB или RGBA.
    - width: толщина линии. Может игнорироваться драйвером.
    - appear: длительность плавного появления, сек.
    - fade: длительность плавного затухания, сек.
    - peak_alpha: максимальный множитель альфы.
    - rest_alpha: альфа после затухания. Если 0 и fade > 0, эффект удалится.
    - delay: задержка старта, сек.
    - overlay: True — поверх всего, False — с учетом глубины.
    """
    start_v = _as_vector(start)
    end_v = _as_vector(end)

    if start_v is None or end_v is None:
        return

    final_color = _to_rgba(color)
    final_width = max(0.01, float(width if width is not None else DEFAULT_LINE_WIDTH))

    _lines.append(_LineFx(
        start=start_v,
        end=end_v,
        color=final_color,
        width=final_width,
        overlay=bool(overlay),
        start_time=time.monotonic(),
        appear=max(0.0, float(appear)),
        fade=max(0.0, float(fade)),
        peak_alpha=_clamp01(peak_alpha),
        rest_alpha=_clamp01(rest_alpha),
        delay=max(0.0, float(delay)),
    ))

    _ensure_timer()


def draw_point(
    pos,
    color=None,
    size=None,
    fade: float = 0.0,
    appear: float = 0.0,
    peak_alpha: float = 1.0,
    rest_alpha: float = 1.0,
    delay: float = 0.0,
    overlay: bool = True,
) -> None:
    """
    Мирная 3D-точка.

    ВАЖНО:
    size — мировой размер стороны бильборд-квадрата, не пиксели.
    Для обычного маркера используй 0.03–0.1.
    """
    pos_v = _as_vector(pos)
    if pos_v is None:
        return

    final_color = _to_rgba(color)
    final_size = max(1e-6, float(size if size is not None else DEFAULT_POINT_SIZE))

    _points.append(_PointFx(
        pos=pos_v,
        color=final_color,
        size=final_size,
        overlay=bool(overlay),
        start_time=time.monotonic(),
        appear=max(0.0, float(appear)),
        fade=max(0.0, float(fade)),
        peak_alpha=_clamp01(peak_alpha),
        rest_alpha=_clamp01(rest_alpha),
        delay=max(0.0, float(delay)),
    ))

    _ensure_timer()


def draw_polygon(
    points,
    color=None,
    width=None,
    filled: bool = True,
    outline: bool = True,
    outline_color=None,
    fade: float = 0.0,
    appear: float = 0.0,
    peak_alpha: float = 1.0,
    rest_alpha: float = 1.0,
    delay: float = 0.0,
    overlay: bool = True,
) -> None:
    """
    Мирный полигон из списка точек.

    Для простых случаев используется triangle fan.
    Для вогнутых n-gon возможны артефакты.
    """
    if points is None:
        return

    verts = []
    for p in points:
        v = _as_vector(p)
        if v is None:
            return
        verts.append(v)

    if len(verts) < 3:
        return

    final_color = _to_rgba(color)

    if outline_color is None:
        # Контур по умолчанию делаем более плотным, чем заливка.
        final_outline_color = (
            final_color[0],
            final_color[1],
            final_color[2],
            1.0,
        )
    else:
        final_outline_color = _to_rgba(outline_color)

    final_width = max(0.01, float(width if width is not None else DEFAULT_LINE_WIDTH))
    now = time.monotonic()

    if filled:
        for i in range(1, len(verts) - 1):
            _tris.append(_TriFx(
                v0=verts[0],
                v1=verts[i],
                v2=verts[i + 1],
                color=final_color,
                overlay=bool(overlay),
                start_time=now,
                appear=max(0.0, float(appear)),
                fade=max(0.0, float(fade)),
                peak_alpha=_clamp01(peak_alpha),
                rest_alpha=_clamp01(rest_alpha),
                delay=max(0.0, float(delay)),
            ))

    if outline:
        count = len(verts)
        for i in range(count):
            _lines.append(_LineFx(
                start=verts[i],
                end=verts[(i + 1) % count],
                color=final_outline_color,
                width=final_width,
                overlay=bool(overlay),
                start_time=now,
                appear=max(0.0, float(appear)),
                fade=max(0.0, float(fade)),
                peak_alpha=_clamp01(peak_alpha),
                rest_alpha=_clamp01(rest_alpha),
                delay=max(0.0, float(delay)),
            ))

    _ensure_timer()


# =====================================================================
# PUBLIC HIGH-LEVEL API
# =====================================================================

def draw_vertex(
    obj,
    indices,
    color=None,
    size=None,
    fade: float = 0.35,
    appear: float = 0.0,
    peak_alpha: float = 1.0,
    rest_alpha: float = 0.0,
    delay: float = 0.0,
    overlay: bool = True,
) -> None:
    """
    Подсветка вершин объекта.

    Пример:
        draw_vertex(obj, 0)
        draw_vertex(obj, [0, 1, 2])

    ВАЖНО:
    size — мировой размер бильборд-квадрата.
    Обычно 0.03–0.1.
    """
    me = _get_mesh(obj)
    if me is None:
        return

    mw = obj.matrix_world
    final_color = _to_rgba(color)
    final_size = max(1e-6, float(size if size is not None else DEFAULT_POINT_SIZE))
    now = time.monotonic()

    for idx in _as_indices(indices):
        if 0 <= idx < len(me.vertices):
            pos = mw @ me.vertices[idx].co

            _points.append(_PointFx(
                pos=pos,
                color=final_color,
                size=final_size,
                overlay=bool(overlay),
                start_time=now,
                appear=max(0.0, float(appear)),
                fade=max(0.0, float(fade)),
                peak_alpha=_clamp01(peak_alpha),
                rest_alpha=_clamp01(rest_alpha),
                delay=max(0.0, float(delay)),
            ))

    _ensure_timer()


def draw_edge(
    obj,
    indices,
    color=None,
    width=None,
    fade: float = 0.35,
    appear: float = 0.0,
    peak_alpha: float = 1.0,
    rest_alpha: float = 0.0,
    delay: float = 0.0,
    overlay: bool = True,
) -> None:
    """
    Подсветка ребер объекта.
    """
    me = _get_mesh(obj)
    if me is None:
        return

    mw = obj.matrix_world
    final_color = _to_rgba(color)
    final_width = max(0.01, float(width if width is not None else DEFAULT_LINE_WIDTH))
    now = time.monotonic()

    for idx in _as_indices(indices):
        if 0 <= idx < len(me.edges):
            edge = me.edges[idx]
            v1_idx, v2_idx = edge.vertices

            if v1_idx >= len(me.vertices) or v2_idx >= len(me.vertices):
                continue

            p1 = mw @ me.vertices[v1_idx].co
            p2 = mw @ me.vertices[v2_idx].co

            _lines.append(_LineFx(
                start=p1,
                end=p2,
                color=final_color,
                width=final_width,
                overlay=bool(overlay),
                start_time=now,
                appear=max(0.0, float(appear)),
                fade=max(0.0, float(fade)),
                peak_alpha=_clamp01(peak_alpha),
                rest_alpha=_clamp01(rest_alpha),
                delay=max(0.0, float(delay)),
            ))

    _ensure_timer()


def draw_face(
    obj,
    indices,
    color=None,
    width=None,
    filled: bool = True,
    outline: bool = True,
    outline_color=None,
    fade: float = 0.35,
    appear: float = 0.0,
    peak_alpha: float = 1.0,
    rest_alpha: float = 0.0,
    delay: float = 0.0,
    overlay: bool = True,
) -> None:
    """
    Подсветка граней объекта.

    По умолчанию:
    - color — полупрозрачная заливка, если передан RGBA.
    - outline_color — более плотный контур.
    """
    me = _get_mesh(obj)
    if me is None:
        return

    mw = obj.matrix_world

    if color is None:
        final_color = (1.0, 1.0, 1.0, 0.35)
    else:
        final_color = _to_rgba(color)

    if outline_color is None:
        final_outline_color = (
            final_color[0],
            final_color[1],
            final_color[2],
            1.0,
        )
    else:
        final_outline_color = _to_rgba(outline_color)

    final_width = max(0.01, float(width if width is not None else DEFAULT_LINE_WIDTH))
    now = time.monotonic()

    for idx in _as_indices(indices):
        if 0 <= idx < len(me.polygons):
            poly = me.polygons[idx]
            verts = []

            for vi in poly.vertices:
                if 0 <= vi < len(me.vertices):
                    verts.append(mw @ me.vertices[vi].co)

            if len(verts) < 3:
                continue

            if filled:
                for i in range(1, len(verts) - 1):
                    _tris.append(_TriFx(
                        v0=verts[0],
                        v1=verts[i],
                        v2=verts[i + 1],
                        color=final_color,
                        overlay=bool(overlay),
                        start_time=now,
                        appear=max(0.0, float(appear)),
                        fade=max(0.0, float(fade)),
                        peak_alpha=_clamp01(peak_alpha),
                        rest_alpha=_clamp01(rest_alpha),
                        delay=max(0.0, float(delay)),
                    ))

            if outline:
                count = len(verts)
                for i in range(count):
                    _lines.append(_LineFx(
                        start=verts[i],
                        end=verts[(i + 1) % count],
                        color=final_outline_color,
                        width=final_width,
                        overlay=bool(overlay),
                        start_time=now,
                        appear=max(0.0, float(appear)),
                        fade=max(0.0, float(fade)),
                        peak_alpha=_clamp01(peak_alpha),
                        rest_alpha=_clamp01(rest_alpha),
                        delay=max(0.0, float(delay)),
                    ))

    _ensure_timer()


# =====================================================================
# EVALUATED GEOMETRY HELPERS
# =====================================================================

def draw_eval_vertex(
    obj,
    indices=None,
    color=None,
    size=None,
    fade: float = 0.35,
    appear: float = 0.0,
    peak_alpha: float = 1.0,
    rest_alpha: float = 0.0,
    delay: float = 0.0,
    overlay: bool = True,
    depsgraph=None,
) -> None:
    """
    Подсветка вершин ПОСЛЕ модификаторов / Geometry Nodes.

    ВАЖНО:
    indices должны быть индексами evaluated mesh.
    Если indices=None — берутся все вершины evaluated mesh.

    Для статичной подсветки используй:
        fade=0.0, rest_alpha=1.0
    """
    if obj is None:
        return

    if depsgraph is None:
        depsgraph = bpy.context.evaluated_depsgraph_get()

    try:
        eval_obj = obj.evaluated_get(depsgraph)
    except Exception:
        return

    if eval_obj is None:
        return

    me = None

    try:
        me = eval_obj.to_mesh()
        if me is None:
            return

        mw = eval_obj.matrix_world

        if indices is None:
            idx_iter = range(len(me.vertices))
        else:
            idx_iter = _as_indices(indices)

        for idx in idx_iter:
            if 0 <= idx < len(me.vertices):
                draw_point(
                    pos=mw @ me.vertices[idx].co,
                    color=color,
                    size=size,
                    fade=fade,
                    appear=appear,
                    peak_alpha=peak_alpha,
                    rest_alpha=rest_alpha,
                    delay=delay,
                    overlay=overlay,
                )

    finally:
        if me is not None:
            try:
                eval_obj.to_mesh_clear()
            except Exception:
                pass


def draw_eval_edge(
    obj,
    indices=None,
    color=None,
    width=None,
    fade: float = 0.35,
    appear: float = 0.0,
    peak_alpha: float = 1.0,
    rest_alpha: float = 0.0,
    delay: float = 0.0,
    overlay: bool = True,
    depsgraph=None,
) -> None:
    """
    Подсветка рёбер ПОСЛЕ модификаторов / Geometry Nodes.

    ВАЖНО:
    indices должны быть индексами evaluated mesh.
    Если indices=None — берутся все рёбра evaluated mesh.
    """
    if obj is None:
        return

    if depsgraph is None:
        depsgraph = bpy.context.evaluated_depsgraph_get()

    try:
        eval_obj = obj.evaluated_get(depsgraph)
    except Exception:
        return

    if eval_obj is None:
        return

    me = None

    try:
        me = eval_obj.to_mesh()
        if me is None:
            return

        mw = eval_obj.matrix_world

        if indices is None:
            idx_iter = range(len(me.edges))
        else:
            idx_iter = _as_indices(indices)

        for idx in idx_iter:
            if 0 <= idx < len(me.edges):
                edge = me.edges[idx]
                v1_idx, v2_idx = edge.vertices

                if v1_idx < 0 or v1_idx >= len(me.vertices):
                    continue
                if v2_idx < 0 or v2_idx >= len(me.vertices):
                    continue

                draw_line(
                    start=mw @ me.vertices[v1_idx].co,
                    end=mw @ me.vertices[v2_idx].co,
                    color=color,
                    width=width,
                    fade=fade,
                    appear=appear,
                    peak_alpha=peak_alpha,
                    rest_alpha=rest_alpha,
                    delay=delay,
                    overlay=overlay,
                )

    finally:
        if me is not None:
            try:
                eval_obj.to_mesh_clear()
            except Exception:
                pass


def draw_eval_face(
    obj,
    indices=None,
    color=None,
    width=None,
    filled: bool = True,
    outline: bool = True,
    outline_color=None,
    fade: float = 0.35,
    appear: float = 0.0,
    peak_alpha: float = 1.0,
    rest_alpha: float = 0.0,
    delay: float = 0.0,
    overlay: bool = True,
    depsgraph=None,
) -> None:
    """
    Подсветка граней ПОСЛЕ модификаторов / Geometry Nodes.

    ВАЖНО:
    indices должны быть индексами evaluated mesh.
    Если indices=None — берутся все полигоны evaluated mesh.

    Для статичной подсветки выбранного utility объекта обычно нужно:
        fade=0.0,
        rest_alpha=1.0
    """
    if obj is None:
        return

    if depsgraph is None:
        depsgraph = bpy.context.evaluated_depsgraph_get()

    try:
        eval_obj = obj.evaluated_get(depsgraph)
    except Exception:
        return

    if eval_obj is None:
        return

    me = None

    try:
        me = eval_obj.to_mesh()
        if me is None:
            return

        mw = eval_obj.matrix_world

        if color is None:
            final_color = (1.0, 1.0, 1.0, 0.35)
        else:
            final_color = _to_rgba(color)

        if outline_color is None:
            final_outline_color = (
                final_color[0],
                final_color[1],
                final_color[2],
                1.0,
            )
        else:
            final_outline_color = _to_rgba(outline_color)

        if indices is None:
            idx_iter = range(len(me.polygons))
        else:
            idx_iter = _as_indices(indices)

        for idx in idx_iter:
            if 0 <= idx < len(me.polygons):
                poly = me.polygons[idx]
                points = []

                for vi in poly.vertices:
                    if 0 <= vi < len(me.vertices):
                        points.append(mw @ me.vertices[vi].co)

                if len(points) < 3:
                    continue

                draw_polygon(
                    points=points,
                    color=final_color,
                    width=width,
                    filled=filled,
                    outline=outline,
                    outline_color=final_outline_color,
                    fade=fade,
                    appear=appear,
                    peak_alpha=peak_alpha,
                    rest_alpha=rest_alpha,
                    delay=delay,
                    overlay=overlay,
                )

    finally:
        if me is not None:
            try:
                eval_obj.to_mesh_clear()
            except Exception:
                pass


# =====================================================================
# CONTROL
# =====================================================================

def clear() -> None:
    """
    Полностью очищает overlay_3d.
    """
    _lines.clear()
    _points.clear()
    _tris.clear()


def register() -> None:
    global _draw_handler

    if _draw_handler is None:
        _draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            draw_overlay_3d_callback,
            (),
            'WINDOW',
            'POST_VIEW',
        )


def unregister() -> None:
    global _draw_handler, _timer_handle

    if _timer_handle is not None:
        try:
            bpy.app.timers.unregister(_timer_handle)
        except Exception:
            pass
        _timer_handle = None

    if _draw_handler is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_draw_handler, 'WINDOW')
        except Exception:
            pass
        _draw_handler = None

    clear()
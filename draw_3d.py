# draw_3d.py
import bpy
import gpu
import mathutils
import time
import math

from gpu_extras.batch import batch_for_shader
from dataclasses import dataclass
from bpy_extras import view3d_utils
from mathutils import Vector

from . import dev_tools
from .config_visual import Draw3DConfig, AXIS_COLORS


@dataclass
class LinePrimitive:
    start: mathutils.Vector
    end: mathutils.Vector
    color: tuple = Draw3DConfig.COLOR_DEFAULT_LINE
    width: float = Draw3DConfig.DEFAULT_LINE_WIDTH


@dataclass
class PointPrimitive:
    pos: mathutils.Vector
    color: tuple = (1.0, 1.0, 1.0, 1.0)
    size: float = 6.0


_lines_registry = []
_points_registry = []
_draw_handler = None


# --- LINE PRIMITIVES ---

def add_line(start: mathutils.Vector, end: mathutils.Vector, color=None, width=None):
    """Добавляет базовую линию."""
    final_color = color if color is not None else Draw3DConfig.COLOR_DEFAULT_LINE
    final_width = width if width is not None else Draw3DConfig.DEFAULT_LINE_WIDTH

    primitive = LinePrimitive(
        start=start.copy(), 
        end=end.copy(), 
        color=final_color, 
        width=float(final_width)
    )
    _lines_registry.append(primitive)


def add_axis_ray(origin: mathutils.Vector, axis_name: str, length: float = 1.0, is_active: bool = False):
    """Хелпер: Добавить направляющий луч оси (X, Y или Z)"""
    axis_dirs = {
        'X': mathutils.Vector((1, 0, 0)),
        'Y': mathutils.Vector((0, 1, 0)),
        'Z': mathutils.Vector((0, 0, 1)),
    }
    direction = axis_dirs.get(axis_name.upper(), mathutils.Vector((0, 0, 0)))
    end = origin + (direction * length)
    
    color = AXIS_COLORS.get(axis_name.upper(), Draw3DConfig.COLOR_DEFAULT_LINE)
    width = Draw3DConfig.ACTIVE_LINE_WIDTH if is_active else Draw3DConfig.AXIS_LINE_WIDTH
    
    add_line(origin, end, color=color, width=width)


# --- POINT PRIMITIVES ---

def add_point(pos: mathutils.Vector, color=None, size=None):
    """Добавляет одну 3D-точку."""
    final_color = color if color is not None else (1.0, 0.5, 0.0, 1.0)
    final_size = size if size is not None else 6.0

    primitive = PointPrimitive(
        pos=pos.copy(),
        color=final_color,
        size=float(final_size)
    )
    _points_registry.append(primitive)


def add_points_bulk(positions: list[mathutils.Vector], color=None, size=None):
    """Массовое добавление точек (для вертекс-групп или массивов)."""
    final_color = color if color is not None else (0.2, 0.8, 1.0, 0.8)
    final_size = size if size is not None else 5.0
    
    _points_registry.extend([
        PointPrimitive(pos=p.copy(), color=final_color, size=float(final_size))
        for p in positions
    ])


def clear():
    """Очищает реестры линий и точек перед каждым кадром."""
    _lines_registry.clear()
    _points_registry.clear()


# --- DRAW CALLBACK ---

def draw_3d_callback():
    # 1. ОТРИСОВКА ЛИНИЙ (Старый сохраненный функционал)
    if _lines_registry:
        shader_line = gpu.shader.from_builtin('SMOOTH_COLOR')

        lines_by_width = {}
        for line in _lines_registry:
            lines_by_width.setdefault(line.width, []).append(line)

        for width, lines in lines_by_width.items():
            coords = []
            colors = []

            for line in lines:
                coords.extend((line.start, line.end))
                colors.extend((line.color, line.color))

            batch = batch_for_shader(shader_line, 'LINES', {"pos": coords, "color": colors})

            gpu.state.line_width_set(width)
            shader_line.bind()
            batch.draw(shader_line)

        gpu.state.line_width_set(1.0)

    # 2. ОТРИСОВКА ТОЧЕК (Новый функционал)
    if _points_registry:
        shader_point = gpu.shader.from_builtin('SMOOTH_COLOR')
        
        gpu.state.blend_set('ALPHA')
        
        points_by_size = {}
        for pt in _points_registry:
            points_by_size.setdefault(pt.size, []).append(pt)

        for size, points in points_by_size.items():
            coords = [pt.pos for pt in points]
            colors = [pt.color for pt in points]

            batch = batch_for_shader(shader_point, 'POINTS', {"pos": coords, "color": colors})

            gpu.state.point_size_set(size)
            shader_point.bind()
            batch.draw(shader_point)

        gpu.state.point_size_set(1.0)
        gpu.state.blend_set('NONE')


# --- HIGH LEVEL FUNCTIONS ---

def get_mouse_3d_pos_camera_offset(context, mouse_2d, offset_distance=5.0):
    region = context.region
    rv3d = context.space_data.region_3d
    origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, mouse_2d)
    vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, mouse_2d)
    vector.normalize()
    return origin + vector * offset_distance


def update_overlay_axes(context, origin_3d, mx, mouse_2d, base_length=Draw3DConfig.AXIS_LINE_LENGTH, active_length=Draw3DConfig.AXIS_ACTIVE_LINE_LENGTH):
    """
    Вычисляет ближайшую ось к курсору мыши, перерисовывает оси в draw_3d
    и возвращает (axis_name, direction).
    """
    clear()

    axis_name, direction = dev_tools.get_closest_axis_2d(context, origin_3d, mx, mouse_2d)

    axis_map = {'X': 0, 'Y': 1, 'Z': 2}
    active_idx = axis_map.get(axis_name, 0)
    dir_sign = 1 if direction == 'POSITIVE' else -1

    quat = mx.to_quaternion()

    axes_data = [
        (0, quat @ Vector((1, 0, 0)), (1.0, 0.2, 0.2, 1.0)),  # X
        (1, quat @ Vector((0, 1, 0)), (0.2, 1.0, 0.2, 1.0)),  # Y
        (2, quat @ Vector((0, 0, 1)), (0.2, 0.5, 1.0, 1.0)),  # Z
    ]

    for axis_idx, axis_vec, color in axes_data:
        is_active = (active_idx == axis_idx)

        # Положительная полуось
        is_pos_active = is_active and (dir_sign > 0)
        pos_len = active_length if is_pos_active else base_length
        pos_width = Draw3DConfig.ACTIVE_LINE_WIDTH if is_pos_active else Draw3DConfig.DEFAULT_LINE_WIDTH
        add_line(origin_3d, origin_3d + axis_vec * pos_len, color=color, width=pos_width)

        # Отрицательная полуось
        is_neg_active = is_active and (dir_sign < 0)
        neg_len = active_length if is_neg_active else base_length
        neg_width = Draw3DConfig.ACTIVE_LINE_WIDTH if is_neg_active else Draw3DConfig.DEFAULT_LINE_WIDTH
        neg_color = (color[0], color[1], color[2], 0.8 if is_active else 0.4)
        add_line(origin_3d, origin_3d - axis_vec * neg_len, color=neg_color, width=neg_width)

    return axis_name, direction

# =====================================================================
# ADDITIVE FX LAYER
# Не изменяет существующие функции draw_3d.py.
# Использует тот же стиль: реестры + draw handler + gpu batches.
# =====================================================================

_fx_lines = []
_fx_points = []
_fx_tris = []

_fx_draw_handler = None
_fx_timer_handle = None


@dataclass
class FxLine:
    start: Vector
    end: Vector
    color: tuple
    width: float
    start_time: float
    duration: float
    peak_alpha: float
    rest_alpha: float
    delay: float = 0.0


@dataclass
class FxPoint:
    pos: Vector
    color: tuple
    size: float
    start_time: float
    duration: float
    peak_alpha: float
    rest_alpha: float
    delay: float = 0.0


@dataclass
class FxTri:
    v0: Vector
    v1: Vector
    v2: Vector
    color: tuple
    start_time: float
    duration: float
    peak_alpha: float
    rest_alpha: float
    delay: float = 0.0


def _clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return float(value)


def _normalize_rgba(color) -> tuple:
    """
    Принимает RGB или RGBA и всегда возвращает RGBA.
    """
    try:
        if len(color) == 3:
            return (float(color[0]), float(color[1]), float(color[2]), 1.0)
        return (float(color[0]), float(color[1]), float(color[2]), float(color[3]))
    except Exception:
        return (1.0, 1.0, 1.0, 1.0)


def _with_alpha(color: tuple, multiplier: float) -> tuple:
    r, g, b, a = _normalize_rgba(color)
    return (r, g, b, _clamp01(a * multiplier))


def _as_indices(indices) -> tuple:
    """
    Приводит int / list / tuple / range к tuple[int, ...].
    """
    if isinstance(indices, int):
        return (indices,)
    try:
        return tuple(indices)
    except TypeError:
        return ()


def _mesh(obj):
    """
    Возвращает Mesh, если объект его содержит.
    Для v1 берём obj.data. Evaluated mesh / modifiers — отдельный следующий шаг.
    """
    me = getattr(obj, "data", None)
    if isinstance(me, bpy.types.Mesh):
        return me
    return None


def _anim_multiplier(effect, now: float) -> float:
    """
    Вспышка: peak_alpha -> rest_alpha по ease-out.
    duration <= 0 означает статичный эффект после delay.
    """
    elapsed = now - effect.start_time - effect.delay

    if effect.duration <= 0.0:
        return 1.0 if elapsed >= 0.0 else 0.0

    if elapsed <= 0.0:
        return 0.0

    if elapsed >= effect.duration:
        return _clamp01(effect.rest_alpha)

    t = elapsed / effect.duration
    ease_out = (1.0 - t) * (1.0 - t)
    value = effect.rest_alpha + (effect.peak_alpha - effect.rest_alpha) * ease_out
    return _clamp01(value)


def _is_expired(effect, now: float) -> bool:
    """
    Удаляем только те эффекты, которые закончили затухание в ноль.
    Если rest_alpha > 0, эффект остаётся статичным следом.
    """
    if effect.duration <= 0.0:
        return False

    elapsed = now - effect.start_time - effect.delay
    return elapsed >= effect.duration and effect.rest_alpha <= 0.0001


def _needs_timer(effect, now: float) -> bool:
    """
    Таймер нужен только пока эффект анимируется или ждёт delay.
    Статичные эффекты не должны держать редрав вечно.
    """
    elapsed = now - effect.start_time - effect.delay

    if effect.duration > 0.0:
        return elapsed < effect.duration

    # duration == 0: нужен таймер только если ещё не наступил delay
    return elapsed < 0.0


def _prune_effects(items: list, now: float) -> None:
    """
    Удаляет протухшие эффекты на месте, без создания нового списка каждый кадр.
    """
    write = 0
    for item in items:
        if not _is_expired(item, now):
            items[write] = item
            write += 1
    del items[write:]


def _has_active_fx(now: float) -> bool:
    for item in _fx_lines:
        if _needs_timer(item, now):
            return True
    for item in _fx_points:
        if _needs_timer(item, now):
            return True
    for item in _fx_tris:
        if _needs_timer(item, now):
            return True
    return False


def _fx_timer():
    global _fx_timer_handle

    now = time.monotonic()

    if not _has_active_fx(now):
        _fx_timer_handle = None
        return None

    # Принудительно перерисовываем все 3D-вьюпорты.
    try:
        wm = bpy.context.window_manager
        for window in wm.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
    except Exception:
        pass

    # ~60 FPS. Для "калашникова" можно поднять до 0.033, если нужно экономнее.
    return 0.016


def _ensure_fx_timer() -> None:
    global _fx_timer_handle
    if _fx_timer_handle is None:
        try:
            _fx_timer_handle = bpy.app.timers.register(
                _fx_timer,
                first_interval=0.016
            )
        except Exception:
            _fx_timer_handle = None


def _add_fx_line(
    start: Vector,
    end: Vector,
    color: tuple,
    width: float,
    duration: float,
    peak_alpha: float,
    rest_alpha: float,
    delay: float,
    start_time: float = None,
) -> None:
    if start_time is None:
        start_time = time.monotonic()

    _fx_lines.append(FxLine(
        start=Vector(start),
        end=Vector(end),
        color=_normalize_rgba(color),
        width=max(0.1, float(width)),
        start_time=start_time,
        duration=max(0.0, float(duration)),
        peak_alpha=_clamp01(peak_alpha),
        rest_alpha=_clamp01(rest_alpha),
        delay=max(0.0, float(delay)),
    ))
    _ensure_fx_timer()


def _add_fx_point(
    pos: Vector,
    color: tuple,
    size: float,
    duration: float,
    peak_alpha: float,
    rest_alpha: float,
    delay: float,
    start_time: float = None,
) -> None:
    if start_time is None:
        start_time = time.monotonic()

    _fx_points.append(FxPoint(
        pos=Vector(pos),
        color=_normalize_rgba(color),
        size=max(1.0, float(size)),
        start_time=start_time,
        duration=max(0.0, float(duration)),
        peak_alpha=_clamp01(peak_alpha),
        rest_alpha=_clamp01(rest_alpha),
        delay=max(0.0, float(delay)),
    ))
    _ensure_fx_timer()


def _add_fx_tri(
    v0: Vector,
    v1: Vector,
    v2: Vector,
    color: tuple,
    duration: float,
    peak_alpha: float,
    rest_alpha: float,
    delay: float,
    start_time: float = None,
) -> None:
    if start_time is None:
        start_time = time.monotonic()

    _fx_tris.append(FxTri(
        v0=Vector(v0),
        v1=Vector(v1),
        v2=Vector(v2),
        color=_normalize_rgba(color),
        start_time=start_time,
        duration=max(0.0, float(duration)),
        peak_alpha=_clamp01(peak_alpha),
        rest_alpha=_clamp01(rest_alpha),
        delay=max(0.0, float(delay)),
    ))
    _ensure_fx_timer()


def draw_fx_callback():
    """
    Отрисовка временных FX-эффектов.
    Не трогает _lines_registry / _points_registry из основной части.
    """
    if not (_fx_lines or _fx_points or _fx_tris):
        return

    now = time.monotonic()

    _prune_effects(_fx_lines, now)
    _prune_effects(_fx_points, now)
    _prune_effects(_fx_tris, now)

    if not (_fx_lines or _fx_points or _fx_tris):
        return

    # [Неизвестно] Проверь для Blender 5.0.1: возможно, нужен '3D_SMOOTH_COLOR'.
    shader = gpu.shader.from_builtin('SMOOTH_COLOR')

    gpu.state.blend_set('ALPHA')

    # Если нужно гарантированно рисовать поверх геометрии, позже проверь и включи:
    # gpu.state.depth_test_set('NONE')
    # gpu.state.depth_write_set(False)

    # -------------------------
    # LINES
    # -------------------------
    if _fx_lines:
        lines_by_width = {}

        for line in _fx_lines:
            mult = _anim_multiplier(line, now)
            if mult <= 0.001:
                continue

            col = _with_alpha(line.color, mult)
            if col[3] <= 0.001:
                continue

            lines_by_width.setdefault(line.width, []).append((line.start, line.end, col))

        for width, items in lines_by_width.items():
            coords = []
            colors = []

            for start, end, col in items:
                coords.extend((start, end))
                colors.extend((col, col))

            if not coords:
                continue

            batch = batch_for_shader(shader, 'LINES', {"pos": coords, "color": colors})
            gpu.state.line_width_set(width)
            shader.bind()
            batch.draw(shader)

        gpu.state.line_width_set(1.0)

    # -------------------------
    # POINTS
    # -------------------------
    if _fx_points:
        points_by_size = {}

        for point in _fx_points:
            mult = _anim_multiplier(point, now)
            if mult <= 0.001:
                continue

            col = _with_alpha(point.color, mult)
            if col[3] <= 0.001:
                continue

            points_by_size.setdefault(point.size, []).append((point.pos, col))

        for size, items in points_by_size.items():
            coords = []
            colors = []

            for pos, col in items:
                coords.append(pos)
                colors.append(col)

            if not coords:
                continue

            batch = batch_for_shader(shader, 'POINTS', {"pos": coords, "color": colors})
            gpu.state.point_size_set(size)
            shader.bind()
            batch.draw(shader)

        gpu.state.point_size_set(1.0)

    # -------------------------
    # TRIANGLES / FACE FILL
    # -------------------------
    if _fx_tris:
        coords = []
        colors = []

        for tri in _fx_tris:
            mult = _anim_multiplier(tri, now)
            if mult <= 0.001:
                continue

            col = _with_alpha(tri.color, mult)
            if col[3] <= 0.001:
                continue

            coords.extend((tri.v0, tri.v1, tri.v2))
            colors.extend((col, col, col))

        if coords:
            batch = batch_for_shader(shader, 'TRIS', {"pos": coords, "color": colors})
            shader.bind()
            batch.draw(shader)

    gpu.state.blend_set('NONE')


def register_fx():
    """
    Регистрирует дополнительный FX handler.
    Существующий register() не меняется.
    """
    global _fx_draw_handler

    if _fx_draw_handler is None:
        _fx_draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            draw_fx_callback,
            (),
            'WINDOW',
            'POST_VIEW'
        )


def unregister_fx():
    """
    Снимает FX handler и таймер.
    """
    global _fx_draw_handler, _fx_timer_handle

    if _fx_timer_handle is not None:
        try:
            bpy.app.timers.unregister(_fx_timer_handle)
        except Exception:
            pass
        _fx_timer_handle = None

    if _fx_draw_handler is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_fx_draw_handler, 'WINDOW')
        except Exception:
            pass
        _fx_draw_handler = None

    clear_fx()


def clear_fx():
    """
    Очищает только FX-реестры.
    Старый clear() не трогает.
    """
    _fx_lines.clear()
    _fx_points.clear()
    _fx_tris.clear()


# =====================================================================
# HIGHLIGHT HELPERS
# =====================================================================

def highlight_vertices(
    obj,
    indices,
    color=(1.0, 1.0, 1.0, 1.0),
    size=6.0,
    fade=0.35,
    peak_alpha=1.0,
    rest_alpha=0.0,
    delay=0.0,
):
    """
    Подсветка вершин.
    По умолчанию: вспышка и затухание.
    """
    me = _mesh(obj)
    if me is None:
        return

    mw = obj.matrix_world
    now = time.monotonic()
    color = _normalize_rgba(color)

    for idx in _as_indices(indices):
        if 0 <= idx < len(me.vertices):
            pos = mw @ me.vertices[idx].co
            _add_fx_point(
                pos=pos,
                color=color,
                size=size,
                duration=fade,
                peak_alpha=peak_alpha,
                rest_alpha=rest_alpha,
                delay=delay,
                start_time=now,
            )


def highlight_edges(
    obj,
    indices,
    color=(1.0, 1.0, 1.0, 1.0),
    width=2.0,
    fade=0.35,
    peak_alpha=1.0,
    rest_alpha=0.0,
    delay=0.0,
):
    """
    Подсветка рёбер.
    """
    me = _mesh(obj)
    if me is None:
        return

    mw = obj.matrix_world
    now = time.monotonic()
    color = _normalize_rgba(color)

    for idx in _as_indices(indices):
        if 0 <= idx < len(me.edges):
            edge = me.edges[idx]
            v1_idx, v2_idx = edge.vertices

            if v1_idx >= len(me.vertices) or v2_idx >= len(me.vertices):
                continue

            p1 = mw @ me.vertices[v1_idx].co
            p2 = mw @ me.vertices[v2_idx].co

            _add_fx_line(
                start=p1,
                end=p2,
                color=color,
                width=width,
                duration=fade,
                peak_alpha=peak_alpha,
                rest_alpha=rest_alpha,
                delay=delay,
                start_time=now,
            )


def highlight_faces(
    obj,
    indices,
    color=(1.0, 1.0, 1.0, 1.0),
    width=1.5,
    fill_alpha=0.25,
    filled=True,
    outline=True,
    fade=0.35,
    peak_alpha=1.0,
    rest_alpha=0.0,
    delay=0.0,
):
    """
    Подсветка граней.

    filled=True  — заливка треугольным веером.
    outline=True — контур по границам полигона.

    [Гипотеза] Для простых полигонов triangle fan нормален.
    Для сложных n-gon / самопересечений позже нужна триангуляция.
    """
    me = _mesh(obj)
    if me is None:
        return

    mw = obj.matrix_world
    now = time.monotonic()
    color = _normalize_rgba(color)
    fill_color = (color[0], color[1], color[2], _clamp01(fill_alpha))

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
                # Triangle fan от первой вершины.
                for i in range(1, len(verts) - 1):
                    _add_fx_tri(
                        v0=verts[0],
                        v1=verts[i],
                        v2=verts[i + 1],
                        color=fill_color,
                        duration=fade,
                        peak_alpha=peak_alpha,
                        rest_alpha=rest_alpha,
                        delay=delay,
                        start_time=now,
                    )

            if outline:
                count = len(verts)
                for i in range(count):
                    _add_fx_line(
                        start=verts[i],
                        end=verts[(i + 1) % count],
                        color=color,
                        width=width,
                        duration=fade,
                        peak_alpha=peak_alpha,
                        rest_alpha=rest_alpha,
                        delay=delay,
                        start_time=now,
                    )


# =====================================================================
# SHAPE HELPERS
# =====================================================================

def _plane_basis(normal):
    """
    Возвращает ортонормированный базис плоскости (x, y, normal).
    """
    n = Vector(normal)

    if n.length < 1e-6:
        n = Vector((0.0, 0.0, 1.0))
    else:
        n.normalize()

    # Выбираем референс, не параллельный нормали.
    if abs(n.z) < 0.99:
        ref = Vector((0.0, 0.0, 1.0))
    else:
        ref = Vector((0.0, 1.0, 0.0))

    x = ref.cross(n)
    if x.length < 1e-6:
        x = Vector((1.0, 0.0, 0.0))
    else:
        x.normalize()

    y = n.cross(x)
    if y.length < 1e-6:
        y = Vector((0.0, 1.0, 0.0))
    else:
        y.normalize()

    return x, y, n


def draw_circle(
    center,
    radius,
    color=(1.0, 1.0, 1.0, 1.0),
    width=2.0,
    segments=32,
    normal=(0.0, 0.0, 1.0),
    fade=0.0,
    peak_alpha=1.0,
    rest_alpha=1.0,
    delay=0.0,
):
    """
    Круг в 3D-пространстве.
    radius — в мировых единицах, не в пикселях.
    """
    center = Vector(center)
    radius = float(radius)

    if radius <= 0.0:
        return

    segments = max(3, int(segments))
    x, y, _ = _plane_basis(normal)
    color = _normalize_rgba(color)
    now = time.monotonic()

    prev = None

    for i in range(segments + 1):
        angle = 2.0 * math.pi * i / segments
        cur = center + (x * math.cos(angle) + y * math.sin(angle)) * radius

        if prev is not None:
            _add_fx_line(
                start=prev,
                end=cur,
                color=color,
                width=width,
                duration=fade,
                peak_alpha=peak_alpha,
                rest_alpha=rest_alpha,
                delay=delay,
                start_time=now,
            )

        prev = cur


def draw_cross(
    center,
    size=1.0,
    color=(1.0, 1.0, 1.0, 1.0),
    width=2.0,
    normal=(0.0, 0.0, 1.0),
    fade=0.0,
    peak_alpha=1.0,
    rest_alpha=1.0,
    delay=0.0,
):
    """
    Крест в плоскости normal.
    size — полный размер в мировых единицах.
    """
    center = Vector(center)
    size = float(size)

    if size <= 0.0:
        return

    x, y, _ = _plane_basis(normal)
    color = _normalize_rgba(color)
    now = time.monotonic()
    half = size * 0.5

    _add_fx_line(
        start=center - x * half,
        end=center + x * half,
        color=color,
        width=width,
        duration=fade,
        peak_alpha=peak_alpha,
        rest_alpha=rest_alpha,
        delay=delay,
        start_time=now,
    )

    _add_fx_line(
        start=center - y * half,
        end=center + y * half,
        color=color,
        width=width,
        duration=fade,
        peak_alpha=peak_alpha,
        rest_alpha=rest_alpha,
        delay=delay,
        start_time=now,
    )


def draw_triangle(
    center,
    size=1.0,
    rotation=0.0,
    color=(1.0, 1.0, 1.0, 1.0),
    width=2.0,
    normal=(0.0, 0.0, 1.0),
    filled=False,
    fade=0.0,
    peak_alpha=1.0,
    rest_alpha=1.0,
    delay=0.0,
):
    """
    Равносторонний треугольник.
    size — радиус описанной окружности, не сторона.
    rotation — радианы вокруг нормали.
    """
    center = Vector(center)
    size = float(size)

    if size <= 0.0:
        return

    x, y, _ = _plane_basis(normal)
    color = _normalize_rgba(color)
    now = time.monotonic()

    pts = []
    for i in range(3):
        angle = float(rotation) + math.pi / 2.0 + i * 2.0 * math.pi / 3.0
        pt = center + (x * math.cos(angle) + y * math.sin(angle)) * size
        pts.append(pt)

    if filled:
        _add_fx_tri(
            v0=pts[0],
            v1=pts[1],
            v2=pts[2],
            color=color,
            duration=fade,
            peak_alpha=peak_alpha,
            rest_alpha=rest_alpha,
            delay=delay,
            start_time=now,
        )

    for i in range(3):
        _add_fx_line(
            start=pts[i],
            end=pts[(i + 1) % 3],
            color=color,
            width=width,
            duration=fade,
            peak_alpha=peak_alpha,
            rest_alpha=rest_alpha,
            delay=delay,
            start_time=now,
        )


def draw_arrow(
    start,
    end,
    head_length=0.1,
    head_width=0.05,
    color=(1.0, 1.0, 1.0, 1.0),
    width=2.0,
    filled_head=True,
    fade=0.0,
    peak_alpha=1.0,
    rest_alpha=1.0,
    delay=0.0,
):
    """
    Стрелка в 3D.
    head_length / head_width — мировые единицы.
    """
    start = Vector(start)
    end = Vector(end)

    direction = end - start
    length = direction.length

    if length <= 1e-6:
        return

    dn = direction.normalized()
    color = _normalize_rgba(color)
    now = time.monotonic()

    head_length = max(0.0, float(head_length))
    head_width = max(0.0, float(head_width))

    # Не даём наконечнику съесть всю стрелку.
    head_length = min(head_length, length * 0.5)

    # Базис для наконечника.
    if abs(dn.z) < 0.99:
        ref = Vector((0.0, 0.0, 1.0))
    else:
        ref = Vector((0.0, 1.0, 0.0))

    side = dn.cross(ref)
    if side.length < 1e-6:
        ref = Vector((1.0, 0.0, 0.0))
        side = dn.cross(ref)

    if side.length < 1e-6:
        side = Vector((1.0, 0.0, 0.0))
    else:
        side.normalize()

    tail = end - dn * head_length
    left = tail + side * (head_width * 0.5)
    right = tail - side * (head_width * 0.5)

    # Хвост
    _add_fx_line(
        start=start,
        end=tail,
        color=color,
        width=width,
        duration=fade,
        peak_alpha=peak_alpha,
        rest_alpha=rest_alpha,
        delay=delay,
        start_time=now,
    )

    # Наконечник
    if filled_head:
        _add_fx_tri(
            v0=end,
            v1=left,
            v2=right,
            color=color,
            duration=fade,
            peak_alpha=peak_alpha,
            rest_alpha=rest_alpha,
            delay=delay,
            start_time=now,
        )
    else:
        _add_fx_line(
            start=end,
            end=left,
            color=color,
            width=width,
            duration=fade,
            peak_alpha=peak_alpha,
            rest_alpha=rest_alpha,
            delay=delay,
            start_time=now,
        )
        _add_fx_line(
            start=end,
            end=right,
            color=color,
            width=width,
            duration=fade,
            peak_alpha=peak_alpha,
            rest_alpha=rest_alpha,
            delay=delay,
            start_time=now,
        )
        _add_fx_line(
            start=left,
            end=right,
            color=color,
            width=width,
            duration=fade,
            peak_alpha=peak_alpha,
            rest_alpha=rest_alpha,
            delay=delay,
            start_time=now,
        )


def draw_shape(
    shape: str,
    center,
    size=1.0,
    **kwargs,
):
    """
    Универсальная обёртка для circle / cross / triangle.
    Для arrow лучше вызывать draw_arrow напрямую, т.к. у неё start/end.
    """
    s = str(shape).upper()

    if s == 'CIRCLE':
        return draw_circle(center, radius=size, **kwargs)

    if s == 'CROSS':
        return draw_cross(center, size=size, **kwargs)

    if s == 'TRIANGLE':
        return draw_triangle(center, size=size, **kwargs)

    raise ValueError(f"Unsupported shape: {shape}")


def register():
    global _draw_handler
    if _draw_handler is None:
        _draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            draw_3d_callback, (), 'WINDOW', 'POST_VIEW'
        )


def unregister():
    global _draw_handler
    if _draw_handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handler, 'WINDOW')
        _draw_handler = None
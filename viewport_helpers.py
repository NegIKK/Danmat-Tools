import bpy
import math
from dataclasses import dataclass
from mathutils import Vector, Matrix, kdtree
from bpy_extras import view3d_utils

try:
    from . import overlay_3d as ov3d
except ImportError:
    import overlay_3d as ov3d


MAX_EVAL_SNAP_VERTS = 500_000


@dataclass
class RayHit:
    location: Vector
    normal: Vector
    index: int
    object: bpy.types.Object
    matrix: Matrix


# =====================================================================
# OVERLAY LIFECYCLE
# =====================================================================

def register():
    ov3d.register()


def unregister():
    ov3d.unregister()


def clear():
    ov3d.clear()


# =====================================================================
# BASIC HELPERS
# =====================================================================

def _is_same_object(a, b):
    if a is None or b is None:
        return False
    if a == b:
        return True
    if getattr(a, "original", None) == b:
        return True
    if getattr(b, "original", None) == a:
        return True
    return False


def _mouse_2d(event):
    return Vector((event.mouse_region_x, event.mouse_region_y))


def _is_xray_active(context):
    try:
        space = context.space_data
        if space is None or space.type != "VIEW_3D":
            return False
        shading = space.shading
        return shading.type == "WIRE" or bool(shading.show_xray)
    except Exception:
        return False


def world_to_region_2d(context, co):
    try:
        region = context.region
        rv3d = context.region_data
        if region.width <= 0 or region.height <= 0:
            return None
        co = Vector(co)
        if rv3d.view_perspective != "ORTHO":
            try:
                cam = rv3d.view_matrix.inverted().translation
                view_dir = rv3d.view_rotation @ Vector((0.0, 0.0, -1.0))
                if (co - cam).dot(view_dir) <= 1e-6:
                    return None
            except Exception:
                pass
        return view3d_utils.location_3d_to_region_2d(region, rv3d, co)
    except Exception:
        return None


def pixel_to_world(context, world_pos, pixels):
    try:
        region = context.region
        rv3d = context.region_data
        space = context.space_data
        if region.height <= 0:
            return 0.05
        world_pos = Vector(world_pos)
        pixels = max(0.0, float(pixels))
        if rv3d.view_perspective == "ORTHO":
            view_size = float(getattr(rv3d, "view_size", 1.0))
            if view_size <= 0.0:
                view_size = 1.0
            return max(1e-9, (view_size / float(region.height)) * pixels)
        try:
            cam = rv3d.view_matrix.inverted().translation
            depth = max(1e-6, (cam - world_pos).length)
        except Exception:
            depth = 1.0
        lens = 50.0
        sensor_width = 36.0
        sensor_fit = "AUTO"
        if space is not None:
            lens = max(1.0, float(getattr(space, "lens", 50.0)))
            sensor_width = max(1.0, float(getattr(space, "sensor_width", 36.0)))
            sensor_fit = getattr(space, "sensor_fit", "AUTO")
        aspect = max(1e-6, float(region.width) / float(region.height))
        if sensor_fit == "VERTICAL":
            sensor_vertical = sensor_width
        else:
            sensor_vertical = sensor_width / aspect
        fov_vertical = 2.0 * math.atan(sensor_vertical / (2.0 * lens))
        world_per_pixel = (2.0 * depth * math.tan(fov_vertical * 0.5)) / float(region.height)
        return max(1e-9, world_per_pixel * pixels)
    except Exception:
        return 0.05


# =====================================================================
# DRAW HELPERS
# =====================================================================

def draw_point_px(context, pos, color=(1.0, 1.0, 1.0, 1.0), pixels=8.0, overlay=True):
    if pos is None:
        return
    size = pixel_to_world(context, pos, pixels)
    ov3d.draw_point(pos=Vector(pos), color=color, size=size, fade=0.0, appear=0.0, peak_alpha=1.0, rest_alpha=1.0, delay=0.0, overlay=bool(overlay))


def draw_line(context, start, end, color=(1.0, 1.0, 1.0, 1.0), width=2.0, overlay=True):
    if start is None or end is None:
        return
    ov3d.draw_line(start=Vector(start), end=Vector(end), color=color, width=float(width), fade=0.0, appear=0.0, peak_alpha=1.0, rest_alpha=1.0, delay=0.0, overlay=bool(overlay))


# =====================================================================
# RAYCAST / EVAL MESH
# =====================================================================

def _ray_origin_direction(context, event):
    try:
        region = context.region
        rv3d = context.region_data
        coord = (event.mouse_region_x, event.mouse_region_y)
        origin = Vector(view3d_utils.region_2d_to_origin_3d(region, rv3d, coord))
        direction = Vector(view3d_utils.region_2d_to_vector_3d(region, rv3d, coord))
        if direction.length < 1e-9:
            return None, None
        direction.normalize()
        return origin, direction
    except Exception:
        return None, None


def raycast(context, event):
    origin, direction = _ray_origin_direction(context, event)
    if origin is None or direction is None:
        return None
    try:
        depsgraph = context.evaluated_depsgraph_get()
        res = context.scene.ray_cast(depsgraph, origin, direction)
        if not res[0]:
            return None
        matrix = res[5]
        if not isinstance(matrix, Matrix):
            matrix = Matrix.Identity(4)
        return RayHit(location=Vector(res[1]), normal=Vector(res[2]), index=int(res[3]), object=res[4], matrix=matrix)
    except Exception:
        return None


def _eval_object_mesh(context, obj):
    try:
        depsgraph = context.evaluated_depsgraph_get()
        eval_obj = obj.evaluated_get(depsgraph)
        me = getattr(eval_obj, "data", None)
        if isinstance(me, bpy.types.Mesh):
            return eval_obj, me, False
        me = eval_obj.to_mesh()
        return eval_obj, me, True
    except Exception:
        return None, None, False


def _clear_eval_mesh(eval_obj, is_temporary):
    if not is_temporary or eval_obj is None:
        return
    try:
        eval_obj.to_mesh_clear()
    except Exception:
        pass


# =====================================================================
# CANDIDATE SCORING
# =====================================================================

def _better_candidate(screen_dist, world_dist_to_hit, best_screen_dist, best_world_dist_to_hit, screen_tol=1.5, world_tol_factor=0.1):
    """
    Выбираем лучшего кандидата:
    1. Сначала по экранному расстоянию (грубый фильтр).
    2. Если экраны близки (в пределах screen_tol пикселей), выбираем того, 
       кто ближе к точке попадания луча (world_dist_to_hit).
       
    Это решает проблему "наводишь на вершину - не видит", потому что 
    даже если курсор чуть мимо, но raycast попал в эту вершину/грань рядом, 
    она выиграет у другой, которая дальше от центра попадания.
    """
    if best_screen_dist is None:
        return True

    # Если разница в экране значительна (> tol), берем ближнего к курсору
    if screen_dist < best_screen_dist - screen_tol:
        return True
    
    if screen_dist > best_screen_dist + screen_tol:
        return False

    # Экраны почти одинаковы. Решаем по близости к точке удара луча.
    # world_tol_factor позволяет немного ослабить требование, если обе точки очень близки к hit.
    if best_world_dist_to_hit is None:
        return True
        
    # Чем меньше расстояние до точки удара, тем лучше
    if world_dist_to_hit < best_world_dist_to_hit:
        return True
        
    return False


# =====================================================================
# VIEWPORT SNAPPER
# =====================================================================

class ViewportSnapper:
    def __init__(self, context, obj, bm):
        self.obj = obj
        self.bm = bm
        self.matrix_world = obj.matrix_world.copy()

        # KD Tree для EDIT MODE вершин (Target)
        self.active_kd = self._build_active_kd(bm)
        
        # Кэш для EVALUATED Mesh активного объекта (Anchor)
        self._active_eval_ptr = None
        self._active_eval_kd = None
        self._active_eval_matrix = None

        # Кэш для других объектов
        self._other_ptr = None
        self._other_kd = None
        self._other_matrix = None

    def _build_active_kd(self, bm):
        try:
            count = len(bm.verts)
            if count <= 0:
                return None
            kd = kdtree.KDTree(count)
            mw = self.matrix_world
            for v in bm.verts:
                kd.insert(mw @ v.co, v.index)
            kd.balance()
            return kd
        except Exception:
            return None

    def _build_kd_from_mesh(self, me, matrix):
        count = len(me.vertices)
        if count <= 0:
            return None, None
        kd = kdtree.KDTree(count)
        for i, v in enumerate(me.vertices):
            kd.insert(matrix @ v.co, i)
        kd.balance()
        return kd, matrix.copy()

    def _get_active_eval_kd(self, context):
        """Строит или возвращает кэш KDTree для evaluated mesh активного объекта."""
        ptr = self.obj.as_pointer()
        if self._active_eval_ptr == ptr and self._active_eval_kd is not None:
            return self._active_eval_kd, self._active_eval_matrix
            
        eval_obj, me, is_temp = _eval_object_mesh(context, self.obj)
        try:
            if me is None:
                return None, None
            if len(me.vertices) > MAX_EVAL_SNAP_VERTS:
                return None, None
                
            matrix = eval_obj.matrix_world
            kd, mat_copy = self._build_kd_from_mesh(me, matrix)
            
            self._active_eval_ptr = ptr
            self._active_eval_kd = kd
            self._active_eval_matrix = mat_copy
            return kd, mat_copy
        finally:
            _clear_eval_mesh(eval_obj, is_temp)

    def _best_from_candidates(self, context, mouse, candidates, pixels, reference=None):
        best_screen_dist = None
        best_world_dist = None
        best_index = None
        best_world = None

        pixels = max(1.0, float(pixels))
        ref = Vector(reference) if reference is not None else None

        for item in candidates:
            try:
                co, index, _dist = item
            except Exception:
                continue

            screen = world_to_region_2d(context, co)
            if screen is None:
                continue

            screen_dist = (screen - mouse).length
            if screen_dist > pixels:
                continue

            world_dist = (Vector(co) - ref).length if ref is not None else 0.0

            if _better_candidate(screen_dist, world_dist, best_screen_dist, best_world_dist):
                best_screen_dist = screen_dist
                best_world_dist = world_dist
                best_index = index
                best_world = Vector(co)

        return best_index, best_world

    # -----------------------------------------------------------------
    # ANCHOR SNAP (Supports Evaluated Mesh of Active Object)
    # -----------------------------------------------------------------
    
    def snap_anchor(self, context, event, pixels=24.0):
        """
        Возвращает (active_vertex_index_or_None, world_co_or_None, is_valid).
        
        Ищем сначала в Edit Mesh (быстро, точно для базовой геометрии).
        Если не нашли, ищем в Evaluated Mesh активного объекта (для Bevel/Subdiv).
        Затем ищем в других объектах.
        """
        hit = raycast(context, event)
        mouse = _mouse_2d(event)
        
        # 1. Пробуем найти в Edit Mesh активного объекта
        if self.active_kd is not None:
            # Используем точку попадания луча как референс для tie-breaker
            ref_point = hit.location if hit and _is_same_object(hit.object, self.obj) else _approximate_object_point(context, self.obj, event)
            
            if ref_point:
                radius = pixel_to_world(context, ref_point, pixels * 2.0) # Щедрый радиус кандидатов
                try:
                    candidates = self.active_kd.find_range(ref_point, radius)
                    idx, world = self._best_from_candidates(context, mouse, candidates, pixels, reference=ref_point)
                    if idx is not None:
                        return idx, world, True
                except Exception:
                    pass

        # 2. Пробуем найти в Evaluated Mesh активного объекта (Post-Modifier)
        # Это позволит ставить Anchor на скругления/сабдивы
        kd_eval, mat_eval = self._get_active_eval_kd(context)
        if kd_eval is not None:
            ref_point = hit.location if hit and _is_same_object(hit.object, self.obj) else _approximate_object_point(context, self.obj, event)
            if ref_point:
                radius = pixel_to_world(context, ref_point, pixels * 2.0)
                try:
                    candidates = kd_eval.find_range(ref_point, radius)
                    # Для evaluated mesh индекс не соответствует BMesh, поэтому возвращаем None как index
                    _idx_dummy, world = self._best_from_candidates(context, mouse, candidates, pixels, reference=ref_point)
                    if world is not None:
                        return None, world, True # Anchor найден, но это виртуальная точка
                except Exception:
                    pass

        # 3. Пробуем другие объекты
        if hit is not None and hit.object is not None and not _is_same_object(hit.object, self.obj):
            other_world = self._snap_other(context, hit, mouse, pixels)
            if other_world is not None:
                return None, other_world, True

        return None, None, False

    # -----------------------------------------------------------------
    # TARGET SNAP (Strictly Edit Mesh)
    # -----------------------------------------------------------------

    def snap_active_vertex(self, context, event, pixels=24.0):
        """
        Только вершины активного edit mesh.
        """
        if self.active_kd is None:
            return None, None

        hit = raycast(context, event)
        mouse = _mouse_2d(event)
        
        # Референс для tie-breaker: точка попадания луча в активный объект
        ref_point = None
        if hit is not None and _is_same_object(hit.object, self.obj):
            ref_point = hit.location
        elif hit is None or _is_xray_active(context):
             ref_point = _approximate_object_point(context, self.obj, event)
             
        if ref_point is None:
            return None, None
            
        radius = pixel_to_world(context, ref_point, pixels * 2.0)
        
        try:
            candidates = self.active_kd.find_range(ref_point, radius)
            return self._best_from_candidates(context, mouse, candidates, pixels, reference=ref_point)
        except Exception:
            return None, None

    # -----------------------------------------------------------------
    # OTHER OBJECT SNAP
    # -----------------------------------------------------------------

    def _snap_other_hit_face(self, context, hit, mouse, pixels):
        eval_obj, me, is_temp = _eval_object_mesh(context, hit.object)
        try:
            if me is None:
                return None
            if hit.index < 0 or hit.index >= len(me.polygons):
                return None
            poly = me.polygons[hit.index]
            matrix = eval_obj.matrix_world if eval_obj is not None else hit.matrix
            best_screen_dist = None
            best_world_dist = None
            best_world = None
            pixels = max(1.0, float(pixels))
            reference = Vector(hit.location)
            for vi in poly.vertices:
                if vi < 0 or vi >= len(me.vertices):
                    continue
                world = matrix @ me.vertices[vi].co
                screen = world_to_region_2d(context, world)
                if screen is None:
                    continue
                screen_dist = (screen - mouse).length
                if screen_dist > pixels:
                    continue
                world_dist = (world - reference).length
                if _better_candidate(screen_dist, world_dist, best_screen_dist, best_world_dist):
                    best_screen_dist = screen_dist
                    best_world_dist = world_dist
                    best_world = Vector(world)
            return best_world
        finally:
            _clear_eval_mesh(eval_obj, is_temp)

    def _snap_other_kdtree(self, context, hit, mouse, pixels):
        ptr = hit.object.as_pointer()
        if self._other_ptr == ptr and self._other_kd is not None:
            kd = self._other_kd
            matrix = self._other_matrix
        else:
            eval_obj, me, is_temp = _eval_object_mesh(context, hit.object)
            try:
                if me is None:
                    return None
                if len(me.vertices) > MAX_EVAL_SNAP_VERTS:
                    return None
                matrix = eval_obj.matrix_world if eval_obj is not None else hit.matrix
                kd, matrix = self._build_kd_from_mesh(me, matrix)
                if kd is None:
                    return None
                self._other_ptr = ptr
                self._other_kd = kd
                self._other_matrix = matrix
            finally:
                _clear_eval_mesh(eval_obj, is_temp)

        probe = Vector(hit.location)
        radius = pixel_to_world(context, probe, max(1.0, float(pixels)) * 2.0)
        try:
            candidates = kd.find_range(probe, radius)
            _index, world = self._best_from_candidates(context, mouse, candidates, pixels, reference=probe)
            return world
        except Exception:
            return None

    def _snap_other(self, context, hit, mouse, pixels):
        if hit is None or hit.object is None:
            return None
        if hit.object.type != "MESH":
            return None
        if _is_same_object(hit.object, self.obj):
            return None
        world = self._snap_other_hit_face(context, hit, mouse, pixels)
        if world is not None:
            return world
        return self._snap_other_kdtree(context, hit, mouse, pixels)


# =====================================================================
# BOUNDS / APPROXIMATE POINT
# =====================================================================

def _object_bounds_world(context, obj):
    try:
        depsgraph = context.evaluated_depsgraph_get()
        eval_obj = obj.evaluated_get(depsgraph)
        matrix = eval_obj.matrix_world
        coords = [matrix @ Vector(c) for c in eval_obj.bound_box]
    except Exception:
        try:
            matrix = obj.matrix_world
            coords = [matrix @ Vector(c) for c in obj.bound_box]
        except Exception:
            return None, None
    if not coords:
        return None, None
    min_v = Vector((min(c.x for c in coords), min(c.y for c in coords), min(c.z for c in coords)))
    max_v = Vector((max(c.x for c in coords), max(c.y for c in coords), max(c.z for c in coords)))
    return min_v, max_v


def _ray_aabb(origin, direction, bmin, bmax):
    tmin = -1e20
    tmax = 1e20
    for i in range(3):
        o = origin[i]
        d = direction[i]
        mn = bmin[i]
        mx = bmax[i]
        if abs(d) < 1e-9:
            if o < mn or o > mx:
                return None
        else:
            t1 = (mn - o) / d
            t2 = (mx - o) / d
            if t1 > t2:
                t1, t2 = t2, t1
            tmin = max(tmin, t1)
            tmax = min(tmax, t2)
            if tmin > tmax:
                return None
    if tmax < 0.0:
        return None
    t = max(tmin, 0.0)
    return origin + direction * t


def _approximate_object_point(context, obj, event):
    origin, direction = _ray_origin_direction(context, event)
    if origin is None or direction is None:
        return None
    bmin, bmax = _object_bounds_world(context, obj)
    if bmin is None or bmax is None:
        try:
            return Vector(context.region_data.view_location)
        except Exception:
            return Vector((0.0, 0.0, 0.0))
    hit = _ray_aabb(origin, direction, bmin, bmax)
    if hit is not None:
        return hit
    try:
        return Vector(context.region_data.view_location)
    except Exception:
        return Vector((0.0, 0.0, 0.0))
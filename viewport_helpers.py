import bpy
import math
from dataclasses import dataclass
from mathutils import Vector, Matrix, kdtree
from mathutils.bvhtree import BVHTree
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
    """Return True when the viewport sees geometry through other geometry.

    Wireframe shading always behaves like X-Ray. In the other shading modes
    the explicit X-Ray toggle controls it. Note that the shading type value
    is "WIREFRAME", not "WIRE".
    """
    try:
        space = context.space_data
        if space is None or space.type != "VIEW_3D":
            return False
        shading = space.shading
        if getattr(shading, "type", "") == "WIREFRAME":
            return True
        return bool(getattr(shading, "show_xray", False))
    except Exception:
        return False


def _object_in_local_view(context, obj):
    """Check whether the object belongs to the current Local View.

    Objects outside Local View are still present in the view layer and can be
    hit by ``scene.ray_cast``, so they have to be filtered out explicitly.
    """
    try:
        space = context.space_data
        if space is None or space.type != "VIEW_3D":
            return True

        local_view = getattr(space, "local_view", None)
        if not local_view:
            return True

        base = getattr(obj, "original", None) or obj

        # Preferred API: asks Blender directly about this object/space pair.
        try:
            return bool(base.local_view_get(space))
        except Exception:
            pass

        try:
            for item in local_view:
                item_base = getattr(item, "original", None) or item
                if item == obj or item_base == base:
                    return True
            return False
        except TypeError:
            # API variant where local_view is not iterable; visible_get()
            # is the only available source of truth in that case.
            return True
    except Exception:
        return True


def _object_is_wire_or_bounds(obj):
    return getattr(obj, "display_type", "SOLID") in {"WIRE", "BOUNDS"}


def is_object_snap_visible(context, obj, ignore_wire_bbox=False):
    """Return True when an object may provide snap targets or hide points.

    Hidden (eye icon), disabled (monitor icon), excluded from the view layer
    and Local-View-isolated objects are ignored completely: they neither give
    snap targets nor block vertices behind them. Wire/Bounds objects are
    ignored as well when the corresponding flag is enabled.
    """
    if obj is None or obj.type != "MESH":
        return False

    try:
        if obj.hide_viewport or obj.hide_get():
            return False
    except Exception:
        pass

    try:
        if not obj.visible_get():
            return False
    except Exception:
        pass

    if not _object_in_local_view(context, obj):
        return False

    if ignore_wire_bbox and _object_is_wire_or_bounds(obj):
        return False

    return True


def _screen_ray(context, screen_pos):
    """Build a world-space camera ray through a region-space 2D point."""
    try:
        region = context.region
        rv3d = context.region_data
        coord = (float(screen_pos[0]), float(screen_pos[1]))
        origin = Vector(view3d_utils.region_2d_to_origin_3d(region, rv3d, coord))
        direction = Vector(view3d_utils.region_2d_to_vector_3d(region, rv3d, coord))
        if direction.length < 1e-9:
            return None, None
        direction.normalize()
        return origin, direction
    except Exception:
        return None, None


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
# SNAP CANDIDATES
# =====================================================================

SNAP_TIE_PIXELS = 0.75


@dataclass
class _SnapCandidate:
    """A single potential snap target found in screen space."""

    screen_dist: float
    camera_dist: float
    world: Vector
    index: object  # int for edit-mesh vertices, None for virtual points
    priority: int  # 0 = edit mesh, 1 = evaluated active mesh, 2 = other object


# =====================================================================
# VIEWPORT SNAPPER
# =====================================================================

class ViewportSnapper:
    """Screen-space vertex snapper with visibility-aware occlusion tests.

    Candidates are collected from every visible mesh independently of the
    object hit by ``scene.ray_cast``. This is what makes snapping work when
    the nearest object is hidden, disabled, excluded or isolated in Local
    View: such objects neither steal the snap nor block the points behind
    them. Occlusion is skipped entirely in X-Ray / Wireframe shading.
    """

    def __init__(self, context, obj, bm, ignore_wire_bbox=False):
        self.obj = obj
        self.bm = bm
        self.matrix_world = obj.matrix_world.copy()
        self.ignore_wire_bbox = bool(ignore_wire_bbox)

        # KD tree for EDIT MODE vertices (the only valid targets).
        self.active_kd = self._build_active_kd(bm)

        # BVH of the edit cage. scene.ray_cast() does not see the mesh that is
        # currently being edited, so self-occlusion has to be tested manually.
        self.active_bvh = self._build_active_bvh(bm)

        # Cache for the EVALUATED active mesh (modifier output, anchor only).
        self._active_eval_ptr = None
        self._active_eval_kd = None
        self._active_eval_matrix = None

        # Per-object caches: object pointer -> (signature, kd, matrix)
        self._other_cache = {}
        # Per-object bounds cache: object pointer -> (key, min, max)
        self._bounds_cache = {}

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

    def _build_active_bvh(self, bm):
        """Build a world-space BVH of the visible edit-cage faces."""
        try:
            bm.verts.ensure_lookup_table()
            polygons = [
                tuple(v.index for v in face.verts)
                for face in bm.faces
                if not face.hide
            ]
            if not polygons:
                return None
            mw = self.matrix_world
            vertices = [mw @ v.co for v in bm.verts]
            return BVHTree.FromPolygons(
                vertices,
                polygons,
                all_triangles=False,
                epsilon=0.0,
            )
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

    # -----------------------------------------------------------------
    # CANDIDATE COLLECTION / RANKING
    # -----------------------------------------------------------------

    @staticmethod
    def _mesh_signature(me, matrix):
        """Cheap cache key for evaluated meshes."""
        return (
            len(me.vertices),
            len(me.polygons),
            tuple(round(value, 6) for row in matrix for value in row),
        )

    def _get_object_kd(self, context, obj):
        """Return a cached world-space KD tree for another object's mesh."""
        ptr = obj.as_pointer()
        matrix = obj.matrix_world.copy()
        try:
            signature = self._mesh_signature(obj.data, matrix)
        except Exception:
            return None, None

        cached = self._other_cache.get(ptr)
        if cached is not None and cached[0] == signature:
            return cached[1], cached[2]

        eval_obj, me, is_temp = _eval_object_mesh(context, obj)
        try:
            if me is None or len(me.vertices) > MAX_EVAL_SNAP_VERTS:
                return None, None

            eval_matrix = eval_obj.matrix_world if eval_obj is not None else matrix
            kd, mat_copy = self._build_kd_from_mesh(me, eval_matrix)
            if kd is None:
                return None, None

            self._other_cache[ptr] = (signature, kd, mat_copy)
            return kd, mat_copy
        finally:
            _clear_eval_mesh(eval_obj, is_temp)

    def _get_bounds(self, context, obj):
        """Cached world-space AABB of the evaluated object."""
        ptr = obj.as_pointer()
        matrix = obj.matrix_world
        data = getattr(obj, "data", None)
        key = (
            len(data.vertices) if data is not None else 0,
            tuple(round(value, 6) for row in matrix for value in row),
        )

        cached = self._bounds_cache.get(ptr)
        if cached is not None and cached[0] == key:
            return cached[1], cached[2]

        bmin, bmax = _object_bounds_world(context, obj)
        self._bounds_cache[ptr] = (key, bmin, bmax)
        return bmin, bmax

    def _surface_reference(self, context, obj, event):
        """Precise world-space surface point under the mouse, or None.

        The active object is edited through its cage, which scene.ray_cast()
        cannot see, so its edit-cage BVH is used instead. Other objects are
        ray-cast through Blender's evaluated geometry.
        """
        origin, direction = _ray_origin_direction(context, event)
        if origin is None or direction is None:
            return None

        if obj == self.obj:
            if self.active_bvh is None:
                return None
            try:
                hit = self.active_bvh.ray_cast(origin, direction)
                if hit is not None and hit[0] is not None:
                    return Vector(hit[0])
            except Exception:
                return None
            return None

        try:
            depsgraph = context.evaluated_depsgraph_get()
            matrix_inv = obj.matrix_world.inverted()
            local_origin = matrix_inv @ origin
            local_dir = matrix_inv.to_3x3() @ direction
            if local_dir.length < 1e-9:
                return None
            local_dir.normalize()
            result, location, _normal, _index = obj.ray_cast(
                local_origin,
                local_dir,
                depsgraph=depsgraph,
            )
            if result:
                return obj.matrix_world @ Vector(location)
        except Exception:
            return None

        return None

    def _ray_reference(self, context, obj, event, pixels):
        """Return (world_point, search_radius) near the object under the mouse.

        Every visible object is searched independently of the single raycast
        hit, so an invisible occluder cannot steal the snap. The reference
        prefers the precise surface; the AABB (with an expanded fallback for
        silhouette vertices) is used when the surface ray misses. The radius
        always spans the snap tolerance so surface vertices are not lost to
        the extra AABB expansion.
        """
        origin, direction = _ray_origin_direction(context, event)
        if origin is None or direction is None:
            return None

        pixels = max(1.0, float(pixels))

        bmin, bmax = self._get_bounds(context, obj)
        if bmin is None or bmax is None:
            return None

        center = (bmin + bmax) * 0.5
        margin = pixel_to_world(context, center, pixels * 2.0)
        expand = Vector((margin, margin, margin))

        # Cheap gate: bail out early when the cursor is nowhere near this
        # object, so we avoid running a surface raycast for every object in
        # the scene on every mouse move.
        expanded = _ray_aabb_interval(origin, direction, bmin - expand, bmax + expand)
        if expanded is None:
            return None

        # Precise surface point under the mouse (active cage or evaluated
        # geometry). Falls back to the bounds below when the surface misses.
        surface = self._surface_reference(context, obj, event)
        if surface is not None:
            return surface, pixel_to_world(context, surface, pixels * 2.0)

        # 1. Exact bounds: the ray normally hits these, and the reference is
        #    then right on the surface, exactly like the previous behaviour.
        interval = _ray_aabb_interval(origin, direction, bmin, bmax)
        if interval is not None:
            tmin, _tmax = interval
            if tmin > 0.0:
                point = origin + direction * tmin
                return point, pixel_to_world(context, point, pixels * 2.0)

        # 2. Expanded bounds: only for vertices whose pixel lies just outside
        #    the projected bounds (silhouette). The reference sits up to one
        #    snap radius in front of the surface, so use a doubled radius.
        tmin, tmax = expanded
        if tmin > 0.0:
            point = origin + direction * tmin
        else:
            # The camera starts inside the expanded bounds (large objects).
            t_center = (center - origin).dot(direction)
            t_center = max(0.0, min(t_center, max(0.0, tmax)))
            point = origin + direction * t_center

        return point, pixel_to_world(context, point, pixels * 4.0)

    def _valid_edit_index(self, index):
        try:
            if index is None or index < 0 or index >= len(self.bm.verts):
                return False
            return not self.bm.verts[index].hide
        except Exception:
            return False

    def _collect_candidates(
        self,
        context,
        kd,
        reference,
        radius,
        mouse,
        pixels,
        camera_origin,
        priority,
        index_filter=None,
        keep_index=True,
    ):
        """Collect screen-space candidates around ``reference``."""
        result = []
        if kd is None or reference is None:
            return result

        pixels = max(1.0, float(pixels))
        radius = max(1e-9, float(radius))

        try:
            entries = kd.find_range(reference, radius)
        except Exception:
            return result

        for co, index, _dist in entries:
            if index_filter is not None and not index_filter(index):
                continue

            co = Vector(co)
            screen = world_to_region_2d(context, co)
            if screen is None:
                continue

            screen_dist = (screen - mouse).length
            if screen_dist > pixels:
                continue

            result.append(
                _SnapCandidate(
                    screen_dist=screen_dist,
                    camera_dist=(co - camera_origin).length,
                    world=co,
                    index=index if keep_index else None,
                    priority=priority,
                )
            )

        return result

    def _pick_candidate(self, context, candidates):
        """Return the closest candidate that is not occluded.

        Screen distance is the primary key. Within a sub-pixel tolerance the
        nearest-to-camera point wins, which resolves front/back vertices that
        project onto the same pixel (important in X-Ray mode).
        """
        if not candidates:
            return None

        candidates.sort(
            key=lambda c: (
                int(c.screen_dist / SNAP_TIE_PIXELS),
                c.camera_dist,
                c.priority,
            )
        )

        for candidate in candidates:
            # Evaluated points of the active object are not drawn in edit
            # mode, so the edit cage must not hide them. Other objects still
            # occlude them normally.
            if self._is_point_visible(
                context,
                candidate.world,
                test_active_cage=(candidate.priority != 1),
            ):
                return candidate

        return None

    # -----------------------------------------------------------------
    # OCCLUSION
    # -----------------------------------------------------------------

    def _is_point_visible(self, context, world, test_active_cage=True):
        """Check whether a world-space point is visible from the viewport."""
        if _is_xray_active(context):
            return True

        screen = world_to_region_2d(context, world)
        if screen is None:
            return False

        origin, direction = _screen_ray(context, screen)
        if origin is None or direction is None:
            return True

        distance = (world - origin).length
        if distance <= 1e-9:
            return True

        # Depth tolerance in world units: geometry closer to the camera by
        # more than a couple of pixels hides the point. Anything within that
        # band is treated as the same surface, so the vertex's own faces and
        # float noise never reject it.
        epsilon = pixel_to_world(context, world, 2.0)
        limit = distance - epsilon
        if limit <= 0.0:
            return True

        # The edited mesh is not part of scene.ray_cast() results, so test
        # the edit cage explicitly (also handles self-occlusion). A Wire or
        # Bounds display never looks solid, so it cannot hide vertices.
        active_cage_opaque = not _object_is_wire_or_bounds(self.obj)
        if test_active_cage and active_cage_opaque and self.active_bvh is not None:
            try:
                hit = self.active_bvh.ray_cast(origin, direction, limit)
                if hit is not None and hit[0] is not None:
                    return False
            except Exception:
                pass

        # Other objects: scene.ray_cast() sees hidden/disabled/isolated
        # objects too, so walk past every ignored hit.
        if self._first_visible_scene_hit(context, origin, direction, limit) is not None:
            return False

        return True

    def _first_visible_scene_hit(self, context, origin, direction, max_distance):
        """First hit on a visible mesh, skipping ignored geometry."""
        if max_distance <= 0.0:
            return None

        try:
            depsgraph = context.evaluated_depsgraph_get()
            scene = context.scene
        except Exception:
            return None

        position = Vector(origin)
        remaining = float(max_distance)
        epsilon = max(1e-6, remaining * 1e-4)

        # Bounded loop: there can be many stacked hidden objects, but not
        # infinitely many.
        for _ in range(64):
            if remaining <= epsilon:
                return None

            try:
                hit, location, _normal, _index, hit_obj, _matrix = scene.ray_cast(
                    depsgraph,
                    position,
                    direction,
                    distance=remaining,
                )
            except Exception:
                return None

            if not hit:
                return None

            location = Vector(location)

            visible_hit = is_object_snap_visible(
                context,
                hit_obj,
                self.ignore_wire_bbox,
            )
            # The active object in Wire/Bounds display is already handled by
            # the explicit edit-cage test above; do not count it twice.
            if (
                visible_hit
                and _is_same_object(hit_obj, self.obj)
                and _object_is_wire_or_bounds(self.obj)
            ):
                visible_hit = False

            if visible_hit:
                return location

            step = (location - position).length
            position = location + direction * epsilon
            remaining -= step + epsilon

        return None

    # -----------------------------------------------------------------
    # ANCHOR SNAP (Supports Evaluated Mesh of Active Object)
    # -----------------------------------------------------------------
    
    def snap_anchor(self, context, event, pixels=24.0):
        """Find the best anchor point near the mouse.

        Returns ``(edit_vertex_index_or_None, world_co_or_None, is_valid)``.
        Candidates come from the edit mesh, the evaluated active mesh
        (Bevel/Subdivision preview) and every other visible mesh. Every
        object is searched independently, so geometry hidden behind an
        invisible occluder remains reachable.
        """
        mouse = _mouse_2d(event)
        camera_origin, _direction = _ray_origin_direction(context, event)
        if camera_origin is None:
            return None, None, False

        candidates = []

        active_hit = self._ray_reference(context, self.obj, event, pixels)
        if active_hit is not None:
            active_reference, active_radius = active_hit
            # 1. Base edit-mesh vertices (real, editable indices).
            candidates.extend(
                self._collect_candidates(
                    context,
                    self.active_kd,
                    active_reference,
                    active_radius,
                    mouse,
                    pixels,
                    camera_origin,
                    priority=0,
                    index_filter=self._valid_edit_index,
                )
            )

            # 2. Evaluated active mesh (post-modifier virtual points).
            kd_eval, _matrix_eval = self._get_active_eval_kd(context)
            candidates.extend(
                self._collect_candidates(
                    context,
                    kd_eval,
                    active_reference,
                    active_radius,
                    mouse,
                    pixels,
                    camera_origin,
                    priority=1,
                    keep_index=False,
                )
            )

        # 3. Every other visible mesh object, independent of the raycast hit.
        for other in context.view_layer.objects:
            if other == self.obj:
                continue
            if not is_object_snap_visible(context, other, self.ignore_wire_bbox):
                continue

            other_hit = self._ray_reference(context, other, event, pixels)
            if other_hit is None:
                continue

            other_reference, other_radius = other_hit
            kd, _matrix = self._get_object_kd(context, other)
            if kd is None:
                continue

            candidates.extend(
                self._collect_candidates(
                    context,
                    kd,
                    other_reference,
                    other_radius,
                    mouse,
                    pixels,
                    camera_origin,
                    priority=2,
                    keep_index=False,
                )
            )

        candidate = self._pick_candidate(context, candidates)
        if candidate is None:
            return None, None, False

        return candidate.index, candidate.world, True

    # -----------------------------------------------------------------
    # TARGET SNAP (Strictly Edit Mesh)
    # -----------------------------------------------------------------

    def snap_active_vertex(self, context, event, pixels=24.0):
        """Find the best visible vertex of the active edit mesh near the mouse."""
        if self.active_kd is None:
            return None, None

        mouse = _mouse_2d(event)
        camera_origin, _direction = _ray_origin_direction(context, event)
        if camera_origin is None:
            return None, None

        active_hit = self._ray_reference(context, self.obj, event, pixels)
        if active_hit is None:
            return None, None

        reference, radius = active_hit
        candidates = self._collect_candidates(
            context,
            self.active_kd,
            reference,
            radius,
            mouse,
            pixels,
            camera_origin,
            priority=0,
            index_filter=self._valid_edit_index,
        )

        candidate = self._pick_candidate(context, candidates)
        if candidate is None:
            return None, None

        return candidate.index, candidate.world


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


def _ray_aabb_interval(origin, direction, bmin, bmax):
    """Return the (t_min, t_max) entry/exit distances of a ray and an AABB."""
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
    return tmin, tmax


def _ray_aabb(origin, direction, bmin, bmax):
    interval = _ray_aabb_interval(origin, direction, bmin, bmax)
    if interval is None:
        return None
    tmin, _tmax = interval
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
    
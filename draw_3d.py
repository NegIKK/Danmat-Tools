# draw_3d.py
import bpy
import gpu
import mathutils

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
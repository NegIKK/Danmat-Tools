import bpy
import bmesh
import mathutils
from . import draw_3d

from mathutils import Vector
from bpy_extras.view3d_utils import location_3d_to_region_2d

def get_closest_axis_2d(context, origin_3d, mx, mouse_2d):

    """
    origin_3d: 3D-центр (например, центроид объекта или точка старта flick)
    mx: Matrix объекта или кастомной системы координат
    mouse_2d: Vector((x, y)) — текущие координаты мыши
    """
    region = context.region
    rv3d = context.space_data.region_3d
    
    # 2D-координата центра
    center_2d = location_3d_to_region_2d(region, rv3d, origin_3d)
    if center_2d is None:
        return 'X', 'POSITIVE' # Фолбэк, если центр за камерой
    
    # Вектор от центра стартового клика до мыши на экране
    mouse_dir = (mouse_2d - center_2d)
    if mouse_dir.length == 0:
        return 'X', 'POSITIVE'
    mouse_dir.normalize()
    
    # Базовые 3D-векторы осей
    axis_vectors = {
        ('X', 'POSITIVE'): Vector((1, 0, 0)),
        ('X', 'NEGATIVE'): Vector((-1, 0, 0)),
        ('Y', 'POSITIVE'): Vector((0, 1, 0)),
        ('Y', 'NEGATIVE'): Vector((0, -1, 0)),
        ('Z', 'POSITIVE'): Vector((0, 0, 1)),
        ('Z', 'NEGATIVE'): Vector((0, 0, -1)),
    }
    
    best_match = None
    max_dot = -float('inf')
    
    # Длина направляющего вектора в 3D для устойчивой проекции
    scale_factor = 1.0 
    
    for (axis_name, direction), local_vec in axis_vectors.items():
        # Переводим локальный вектор оси в мировую 3D-точку
        world_axis_pt = origin_3d + (mx.to_quaternion() @ local_vec) * scale_factor
        axis_2d = location_3d_to_region_2d(region, rv3d, world_axis_pt)
        
        if axis_2d is None:
            continue
            
        # Направление оси на 2D-экране
        screen_axis_dir = (axis_2d - center_2d)
        
        # Если ось направлена строго в/от камеры, 2D-вектор почти нулевой
        if screen_axis_dir.length < 1e-4:
            continue
            
        screen_axis_dir.normalize()
        
        # Скалярное произведение определяет, насколько вектор мыши совпадает с осью
        dot = mouse_dir.dot(screen_axis_dir)
        
        if dot > max_dot:
            max_dot = dot
            best_match = (axis_name, direction)
            
    return best_match if best_match else ('X', 'POSITIVE')


def get_current_transform_matrix_and_info(context, orientation_name=None):
    """
    Возвращает:
        mx (Matrix 4x4): Мировая матрица ориентации
        space_name (str): Имя ориентации (Global, Local, Custom и т.д.)
    """
    scene = context.scene
    slot = scene.transform_orientation_slots[0]

    # Проверка, принято ли имя ориентации в параметре
    if orientation_name is None:
        orient_type = slot.type
        
        if slot.custom_orientation:
            orientation_name = slot.custom_orientation.name
        else:
            orientation_name = orient_type
    else:
        orient_type = orientation_name

    # 1. Custom / Temp ориентации
    if slot.custom_orientation:
        try:
            custom_name = slot.custom_orientation.name
            matrix_3x3 = slot.custom_orientation.matrix
            return matrix_3x3.to_4x4(), f"Custom ({custom_name})"
        except Exception:
            pass

    # 2. Встроенные ориентации Blender
    if orient_type == 'GLOBAL':
        return mathutils.Matrix.Identity(4), "Global"

    elif orient_type == 'LOCAL':
        obj = context.active_object
        mx = obj.matrix_world.copy() if obj else mathutils.Matrix.Identity(4)
        return mx, "Local"

    elif orient_type == 'PARENT':
        obj = context.active_object
        if obj and obj.parent:
            return obj.parent.matrix_world.copy(), "Parent"
        mx = obj.matrix_world.copy() if obj else mathutils.Matrix.Identity(4)
        return mx, "Parent"

    elif orient_type == 'CURSOR':
        return scene.cursor.matrix.copy(), "3D Cursor"

    elif orient_type == 'VIEW':
        rv3d = context.space_data.region_3d if (context.space_data and context.space_data.type == 'VIEW_3D') else None
        if rv3d:
            return rv3d.view_rotation.to_matrix().to_4x4(), "View"

    elif orient_type in {'NORMAL', 'GIMBAL'}:
        obj = context.active_object
        if obj:
            if obj.mode == 'EDIT':
                try:
                    import bmesh
                    bm = bmesh.from_edit_mesh(obj.data)
                    selected_verts = [v for v in bm.verts if v.select]
                    if selected_verts:
                        avg_norm = sum((v.normal for v in selected_verts), mathutils.Vector())
                        if avg_norm.length > 0:
                            avg_norm.normalize()
                            quat = avg_norm.to_track_quat('Z', 'Y')
                            mx = obj.matrix_world.to_quaternion().to_matrix().to_4x4() @ quat.to_matrix().to_4x4()
                            return mx, f"{orient_type.capitalize()} (Selection)"
                except Exception:
                    pass
            return obj.matrix_world.copy(), orient_type.capitalize()

    return mathutils.Matrix.Identity(4), "Global"


def get_selected_axis_data(matrix, axis_name, direction):
    """
    Преобразует строковый выбор осей в технические данные для геометрии:
    
    Возвращает:
        axis_index (int): 0 (X), 1 (Y), 2 (Z)
        dir_sign (int): 1 (POSITIVE), -1 (NEGATIVE)
        world_axis_vector (Vector): Единичный вектор направления оси в мировом пространстве
    """
    axis_map = {'X': 0, 'Y': 1, 'Z': 2}
    axis_index = axis_map.get(axis_name, 0)
    dir_sign = 1 if direction == 'POSITIVE' else -1

    # Локальный вектор оси (1,0,0), (0,1,0) или (0,0,1)
    local_vector = Vector((0.0, 0.0, 0.0))
    local_vector[axis_index] = float(dir_sign)

    # Перевод вектора направления в мировую систему координат текущей ориентации
    world_axis_vector = (matrix.to_quaternion() @ local_vector).normalized()

    return axis_index, dir_sign, world_axis_vector


def align_selected_geometry(context, world_direction_vec, align_per_object=False):
    """
    Выравнивает выделенную геометрию на всех редактируемых объектах.
    
    :param context: Контекст Blender
    :param world_direction_vec: Единичный вектор направления в World Space
    :param align_per_object: False — один общий край для всех объектов, 
                             True — каждый объект выравнивает свои вершины отдельно
    """
    # Получаем все объекты, которые сейчас находятся в режиме редактирования
    edit_objs = context.objects_in_mode_unique_data

    if not edit_objs:
        return

    # Собираем данные по каждому объекту
    objects_data = []
    global_max_proj = -float('inf')

    for obj in edit_objs:
        bm = bmesh.from_edit_mesh(obj.data)
        selected_verts = [v for v in bm.verts if v.select]

        if not selected_verts:
            continue

        # Вектор направления в локальной системе конкретного объекта
        world_to_local_rot = obj.matrix_world.to_quaternion().inverted()
        local_dir_vec = (world_to_local_rot @ world_direction_vec).normalized()

        # Для корректного поиска глобального максимума нужно учитывать позицию объекта в мире
        # (v.co в локальных координатах -> переводим мировое положение для расчета общего Dot Product)
        mat_world = obj.matrix_world
        projections = [(mat_world @ v.co).dot(world_direction_vec) for v in selected_verts]

        obj_max_proj = max(projections)
        if obj_max_proj > global_max_proj:
            global_max_proj = obj_max_proj

        objects_data.append({
            'obj': obj,
            'bm': bm,
            'verts': selected_verts,
            'local_dir': local_dir_vec,
            'projections': projections,
            'obj_max_proj': obj_max_proj
        })

    if not objects_data:
        return

    # Выполняем сдвиг вершин
    for item in objects_data:
        obj = item['obj']
        local_dir = item['local_dir']
        
        # Выбираем целевую плоскость: общую для всех или индивидуальную для объекта
        target_proj = item['obj_max_proj'] if align_per_object else global_max_proj

        for v, proj in zip(item['verts'], item['projections']):
            distance_to_move = target_proj - proj
            # Сдвигаем локальную координату
            v.co += local_dir * distance_to_move

        bmesh.update_edit_mesh(obj.data)


def symmetrize(obj, data, debug=False):
    bm = bmesh.from_edit_mesh(obj.data)

    # 1. Получаем активный UV-слой меша
    uv_layer = bm.loops.layers.uv.active

    # Разбираем направление и ось ("POSITIVE_X" -> dir_str="POSITIVE", axis_str="X")
    dir_str, axis_str = data['direction'].split('_')
    axis_idx = {'X': 0, 'Y': 1, 'Z': 2}[axis_str]

    plane_dir = Vector((0, 0, 0))
    plane_dir[axis_idx] = 1.0 if dir_str == 'POSITIVE' else -1.0

    if data['remove']:
        # Режим Remove: просто удаляем геометрию с указанной стороны
        direction_val = 1.0 if dir_str == 'POSITIVE' else -1.0
        verts_to_delete = [
            v for v in bm.verts 
            if (v.co[axis_idx] * direction_val) > data['threshold']
        ]
        bmesh.ops.delete(bm, geom=verts_to_delete, context='VERTS')
        
        mirror_verts = []
        center_verts = [v for v in bm.verts if abs(v.co[axis_idx]) <= data['threshold']]
    else:
        # 2. Выполняем симметризацию
        ret = bmesh.ops.symmetrize(
            bm,
            input=bm.verts[:] + bm.edges[:] + bm.faces[:],
            direction=plane_dir,
            dist=data['threshold']
        )
        
        geom_out = ret.get('geom', [])
        mirror_verts = [elem for elem in geom_out if isinstance(elem, bmesh.types.BMVert)]
        center_verts = [v for v in bm.verts if abs(v.co[axis_idx]) <= data['threshold']]

        # 3. Смещение UV (UV Offset) для отраженных элементов
        uv_offset = data.get('uv_offset')
        if uv_layer and uv_offset and (uv_offset.x != 0 or uv_offset.y != 0):
            # Извлекаем все новые/отраженные грани
            mirror_faces = [elem for elem in geom_out if isinstance(elem, bmesh.types.BMFace)]
            
            # Применяем offset к UV-координатам лупов новых граней
            for face in mirror_faces:
                for loop in face.loops:
                    loop[uv_layer].uv += uv_offset

    bmesh.update_edit_mesh(obj.data)

    return {
        'custom_normal': None,
        'mirror': [v.index for v in mirror_verts],
        'center': [v.index for v in center_verts]
    }

def get_orientation_matrix(context, orientation_name):
        """
        Детерминированная функция: имя → матрица 4x4.
        """
        scene = context.scene
        obj = context.active_object
        slot = scene.transform_orientation_slots[0]

        # 1. Если запрашиваемая ориентация — текущая кастомная
        if slot.custom_orientation and orientation_name == slot.custom_orientation.name:
            return slot.custom_orientation.matrix.to_4x4()

        # 2. Встроенные
        if orientation_name == 'GLOBAL':
            return mathutils.Matrix.Identity(4)

        if orientation_name == 'LOCAL':
            return obj.matrix_world.copy() if obj else mathutils.Matrix.Identity(4)

        if orientation_name == 'CURSOR':
            return scene.cursor.matrix.copy()

        if orientation_name == 'VIEW':
            rv3d = (context.space_data.region_3d 
                    if context.space_data and context.space_data.type == 'VIEW_3D' 
                    else None)
            if rv3d:
                return rv3d.view_rotation.to_matrix().to_4x4()
            return mathutils.Matrix.Identity(4)

        # Fallback
        return mathutils.Matrix.Identity(4)
import bpy
import bmesh

from mathutils import Vector, Matrix

#region Renaming
def rename():
    # Active Object Cache
    active_object = bpy.context.view_layer.objects.active
    if not active_object:
        return
    
    base_name = active_object.name

    # Renaming active object
    if base_name.endswith("_low"):
        base_name = base_name.removesuffix("_low")
    active_object.name = base_name + "_low"

    # Renaming selected objects
    for obj in bpy.context.selected_objects:
        if obj == active_object:
            continue

        if base_name.endswith("_high"):
            base_name = base_name.removesuffix("_high")

        obj.name = base_name + "_high"


def swap_num_separator(objects_to_rename, separator):  
    for obj in objects_to_rename:
        obj.name = obj.name.replace(".", separator)
            

def set_wire_mode():
    activeObject = bpy.context.view_layer.objects.active
    activeObject.display_type = 'WIRE'


def select_bake_group(obj):
    # obj = bpy.context.object
    if not obj:
        return
    
    base_name = get_base_name(obj.name)

    for o in bpy.data.objects:
        if get_base_name(o.name) == base_name:
            o.select_set(True)

def get_base_name(name: str) -> str:
    """Удаление чисел и суффиксов для получения базового имени"""
    separatorList = "._-,;:'/"

    parts = []
    separators = []

    current = ""
    for ch in name:
        if ch in separatorList:
            parts.append(current)
            separators.append(ch)
            current = ""
        else:
            current += ch
    parts.append(current)

    # Сначала удаляем хвостовые цифры (дубликаты Blender .001, .002)
    while parts:
        last = parts[-1]
        if last.isdigit():
            parts.pop()
            if separators:
                separators.pop()
        else:
            break

    # Затем удаляем только low/high (цифры ПЕРЕД ними НЕ трогаем - это часть имени!)
    while parts:
        last = parts[-1].lower()
        
        if last in {"low", "high"}:
            parts.pop()
            if separators:
                separators.pop()
        else:
            break

    # Склеиваем обратно
    result = parts[0] if parts else ""
    for sep, part in zip(separators, parts[1:]):
        result += sep + part

    return result


# endregion Renaming


#region Collections
def get_scene_collections():
    collections_list = ["Scene Collection"]
    for collection in bpy.data.collections:
        collections_list.insert(-1, collection.name)   
    return collections_list


def get_collection_name_of_object(obj):
    # print(obj.users_collection[0].name)
    return obj.users_collection[0].name


def create_collection(new_collection_name, collection_parent): #работает только когда целевая колекция находится в корне, если она вложена то нет
    def traverse_tree(t):
        yield t
        for child in t.children:
            yield from traverse_tree(child)

    coll = bpy.context.scene.collection

    for c in traverse_tree(coll):
        if c.name == collection_parent: # Specify the name of you main collection here
            my_sub_coll = bpy.data.collections.new(new_collection_name)
            # Add it to the main collection
            c.children.link(my_sub_coll)


def create_helper_collection(suffix):
    colletction_of_selected_obj = get_collection_name_of_object(bpy.context.object)
    # print(colletction_of_selected_obj)

    collection_name_to_create = colletction_of_selected_obj + " " + suffix

    all_scene_collections = get_scene_collections()
    
    is_helper_exist = False
    for collection in all_scene_collections:
        if collection_name_to_create == collection:
            is_helper_exist = True

    if is_helper_exist == False:
        create_collection(collection_name_to_create, colletction_of_selected_obj)
    
    return(collection_name_to_create) 


def move_to_collection(objects_to_move, target_collection):
    for obj in objects_to_move:
        
        current_obj_collection_name = get_collection_name_of_object(obj)
        if current_obj_collection_name != "Scene Collection":
            current_obj_collection = bpy.data.collections[current_obj_collection_name]
            current_obj_collection.objects.unlink(obj)
        else:
            bpy.context.scene.collection.objects.unlink(obj)

        bpy.data.collections[target_collection].objects.link(obj)

#endregion Collections

#region Bool and Objects


def get_unparented_utility(obj):
    mod_objects = set(get_modifier_objects(obj))
    children = set(obj.children)
    unused = mod_objects - children  # объекты из модификаторов, которые не являются дочерними

    return unused


def toggle_utility_visibilty(obj, exclude_mirror=False):
    
    utils = []
    
    for child in obj.children:
        if child.display_type in {'BOUNDS', 'WIRE'}:
            utils.extend([child])
            
    for mod_obj in get_modifier_objects(obj, exclude_mirror):
        utils.extend([mod_obj])
    
    # Если хотя бы один объект видим — выключить все
    if any(not util.hide_get() for util in utils):
        for u in utils:        
            u.hide_set(1)
    else:
        for u in utils:        
            u.hide_set(0)


def set_utility_as_child(obj):
    for ob in get_unparented_utility(obj):
        ob.select_set(True)     # Выделить объекты
    
    bpy.ops.object.parent_set(keep_transform=True)


def to_collection(obj):
    create_helper_collection("Utils")
    objs_to_move = get_modifier_objects(obj)
    move_to_collection(objs_to_move, create_helper_collection("Utils"))


# модальный оператор

def get_modifier_objects(obj, exclude_mirror=False):
    result = set()
    for mod in obj.modifiers:
        if exclude_mirror and mod.type == 'MIRROR':
            continue
        if mod.type == 'NODES':
            # Прямой доступ через keys() + mod[key]
            for key in mod.keys():
                value = mod[key]
                if isinstance(value, bpy.types.Object):
                    result.add(value)
                elif isinstance(value, bpy.types.Collection):
                    result.update(value.objects)
        else:
            # Стандартные POINTER-ссылки
            for prop in mod.bl_rna.properties:
                if prop.type == 'POINTER' and prop.fixed_type.identifier == 'Object':
                    linked_obj = getattr(mod, prop.identifier, None)
                    if linked_obj:
                        result.add(linked_obj)
    return result


def set_active_modifier_for_object(main_obj, target_obj, exclude_mirror=False):
    """Сделать активным модификатор, который использует target_obj (по логике get_modifier_objects)."""
    for mod in main_obj.modifiers:
        # Получаем объекты только для текущего модификатора!
        mod_objects = set()
        if exclude_mirror and mod.type == 'MIRROR':
            continue
        # 1. Стандартные POINTER-ссылки
        for prop in mod.bl_rna.properties:
            if prop.type == 'POINTER' and prop.fixed_type.identifier == 'Object':
                linked_obj = getattr(mod, prop.identifier, None)
                if linked_obj is not None:
                    mod_objects.add(linked_obj)
        # 2. Geometry Nodes: ищем объекты среди пользовательских свойств
        if mod.type == 'NODES':
            for key, value in mod.items():
                if isinstance(value, bpy.types.Object):
                    mod_objects.add(value)
                if isinstance(value, (list, tuple)):
                    for v in value:
                        if isinstance(v, bpy.types.Object):
                            mod_objects.add(v)
                # Если value — ссылка на Collection, добавить все объекты из неё
                if isinstance(value, bpy.types.Collection):
                    for obj_in_col in value.objects:
                        mod_objects.add(obj_in_col)
        # Проверяем только объекты этого модификатора!
        if target_obj in mod_objects:
            main_obj.modifiers.active = mod
            return


def cycle_index(current, delta, length):
    if length == 0:
        return 0
    return (current + delta) % length


def select_object_by_index(self, context, index, initial_active=None, set_active=False):
    bpy.ops.object.select_all(action='DESELECT')
    if not self._items:
        return
    
    # for i, obj in enumerate(self._items):
    #     if isinstance(obj, bpy.types.Object):
    #         if i == index:
    #             # obj.hide_set(False)
    #             # if set_active:
    #                 # context.view_layer.objects.active = obj
    #                 # obj.select_set(True)
    #             if initial_active:
    #                 context.view_layer.objects.active = initial_active
    #         else:
    #             obj.hide_set(True)

def hide_other_objects(self, index, hide_all=False):
    for i, obj in enumerate(self._items):
        if (not hide_all):
            if isinstance(obj, bpy.types.Object):
                if i == index:
                    obj.hide_set(False)
                else:
                    obj.hide_set(True)
        else:
            obj.hide_set(True)
    


#region Remesh
def disable(obj, modifier_type, modifier_name):   
    for modifier in obj.modifiers:
        if modifier.type == modifier_type:
            obj.modifiers[modifier_name].show_viewport = False  

def enable(obj, modifier_type, modifier_name):
    for modifier in obj.modifiers:
        if modifier.type == modifier_type:
            obj.modifiers[modifier_name].show_viewport = True

def remove(modifier_name):
    for obj in bpy.context.selected_objects:
        modifier_to_remove = obj.modifiers.get(modifier_name)
        if modifier_to_remove is not None:
            obj.modifiers.remove(modifier_to_remove)
#endregion Remesh


def debug_modifier_objects(obj):
    """Отладка: вывести информацию об объектах в модификаторах."""
    print(f"\n=== Debug Modifiers for: {obj.name} ===")
    for mod in obj.modifiers:
        print(f"\nModifier: {mod.name} (type={mod.type})")
        
        if mod.type == 'NODES':
            # Проверка всех возможных атрибутов
            print(f"  Has 'node_group': {hasattr(mod, 'node_group')}")
            print(f"  Has 'node_tree': {hasattr(mod, 'node_tree')}")
            print(f"  Has 'mode': {hasattr(mod, 'mode')}")
            
            if hasattr(mod, 'node_group') and mod.node_group:
                print(f"  node_group: {mod.node_group.name}")
            elif hasattr(mod, 'node_tree') and mod.node_tree:
                print(f"  node_tree: {mod.node_tree.name}")
            
            print(f"  keys(): {list(mod.keys())}")
            try:
                print(f"  items(): {list(mod.items())}")
            except Exception as e:
                print(f"  items() error: {e}")
            
            for key in mod.keys():
                try:
                    value = mod[key]
                    print(f"    {key} = {value} ({type(value).__name__})")
                except Exception as e:
                    print(f"    {key} = ERROR: {e}")
        else:
            # Отладка для обычных модификаторов
            print(f"  bl_rna.properties:")
            for prop in mod.bl_rna.properties:
                if prop.type == 'POINTER':
                    val = getattr(mod, prop.identifier, None)
                    print(f"    {prop.identifier}: type={prop.type}, fixed_type={prop.fixed_type}, value={val}")

#region MeshMachine






# Focus ######################

def update_local_view(space_data, states):
    """Обновляет видимость объектов внутри текущего Local View"""
    for obj, visible in states:
        space_data.local_view_set(obj, visible)


def focus_step(context, view_space, selected_objs, history, exclude_modifiers=False):
    """
    Создает новый уровень изоляции объектов с поддержкой перехода из Edit Mode.
    """
    if not selected_objs:
        return False

    # Запоминаем исходный режим
    initial_mode = context.mode
    active_obj = context.active_object

    # Если находимся в Edit Mode — временно переходим в Object Mode
    if initial_mode.startswith('EDIT'):
        bpy.ops.object.mode_set(mode='OBJECT')

    epoch = history.add()
    epoch.name = f"Epoch_{len(history) - 1}"

    # Сохраняем объекты и их выделение
    for obj in selected_objs:
        entry = epoch.objects.add()
        entry.obj = obj

    # Отключение модификаторов MIRROR и ARRAY
    if exclude_modifiers:
        for obj in selected_objs:
            for mod in obj.modifiers:
                if mod.type in {'MIRROR', 'ARRAY'} and mod.show_viewport:
                    mod.show_viewport = False
                    entry = epoch.unmirrored.add()
                    entry.obj = obj

    # Сбрасываем текущий Local View при наличии
    if view_space.local_view:
        bpy.ops.view3d.localview(frame_selected=False)

    # Выделяем только нужные объекты
    bpy.ops.object.select_all(action='DESELECT')
    for obj in selected_objs:
        obj.select_set(True)

    if active_obj and active_obj in selected_objs:
        context.view_layer.objects.active = active_obj

    # Переходим в Local View
    bpy.ops.view3d.localview(frame_selected=False)

    # Возвращаем исходный режим (если был EDIT)
    if initial_mode.startswith('EDIT') and context.active_object:
        bpy.ops.object.mode_set(mode='EDIT')

    return True


def unfocus_step(context, view_space, history):
    """
    Откатывает уровень изоляции назад с корректной обработкой контекста.
    """
    if not history:
        if view_space.local_view:
            bpy.ops.view3d.localview(frame_selected=False)
        return

    initial_mode = context.mode

    # Если перешли в Edit Mode — переключаемся в Object Mode для манипуляций
    if initial_mode.startswith('EDIT'):
        bpy.ops.object.mode_set(mode='OBJECT')

    last_epoch = history[-1]

    # Восстанавливаем модификаторы
    for entry in last_epoch.unmirrored:
        if entry.obj:
            for mod in entry.obj.modifiers:
                if mod.type in {'MIRROR', 'ARRAY'}:
                    mod.show_viewport = True

    history.remove(len(history) - 1)

    if view_space.local_view:
        bpy.ops.view3d.localview(frame_selected=False)

    # Если в истории есть предыдущие шаги
    if len(history) > 0:
        prev_epoch = history[-1]

        bpy.ops.object.select_all(action='DESELECT')
        saved_objs = [entry.obj for entry in prev_epoch.objects if entry.obj]
        
        for obj in saved_objs:
            obj.select_set(True)

        if saved_objs:
            context.view_layer.objects.active = saved_objs[0]

        bpy.ops.view3d.localview(frame_selected=False)

    # Возвращаем режим редактирования, если мы из него выходили
    if initial_mode.startswith('EDIT') and context.active_object:
        bpy.ops.object.mode_set(mode='EDIT')


def clear_focus_history(history):
    """Очищает стек истории изоляции"""
    history.clear()

# Align #############

AXIS_INDEX_MAPPING = {'X': 0, 'Y': 1, 'Z': 2}

def get_matrix_for_space(context, space):
    """Возвращает матрицу трансформации для указанного пространства."""
    if space == 'LOCAL':
        return context.active_object.matrix_world
    elif space == 'CURSOR':
        return context.scene.cursor.matrix
    return Matrix()

def get_selection_groups(bm, select_mode, align_each):
    """Декомпозирует выделение на группы/островки."""
    verts = [v for v in bm.verts if v.select]
    if not verts:
        return [], False

    # Если выделены только вершины или включен выровнять по 0/Cursor
    if select_mode[0]:
        return [verts], False

    # Если выделение ребер (EDGES)
    if select_mode[1]:
        visited = set()
        edges = [e for e in bm.edges if e.select]
        groups = []
        for edge in edges:
            if edge not in visited:
                group_verts = set()
                stack = [edge]
                while stack:
                    curr = stack.pop()
                    if curr not in visited:
                        visited.add(curr)
                        group_verts.update(curr.verts)
                        stack.extend([e for v in curr.verts for e in v.link_edges if e.select and e not in visited])
                groups.append(list(group_verts))
        
        has_multiple = len(groups) > 1
        return (groups if (has_multiple and align_each) else [verts]), has_multiple

    # Если выделение граней (FACES)
    if select_mode[2]:
        visited = set()
        faces = [f for f in bm.faces if f.select]
        islands = []
        for face in faces:
            if face not in visited:
                island_verts = set()
                stack = [face]
                while stack:
                    curr = stack.pop()
                    if curr not in visited:
                        visited.add(curr)
                        island_verts.update(curr.verts)
                        stack.extend([f for e in curr.edges for f in e.link_faces if f.select and f not in visited])
                islands.append(list(island_verts))

        has_multiple = len(islands) > 1
        return (islands if (has_multiple and align_each) else [verts]), has_multiple

    return [verts], False


def align_editmesh_geometry(context, align_type, axis_name, space, align_each=False):
    """
    Основная функция выравнивания. Применяется к активному BMesh.
    """
    active = context.active_object
    bm = bmesh.from_edit_mesh(active.data)
    bm.normal_update()
    bm.verts.ensure_lookup_table()

    axis = AXIS_INDEX_MAPPING[axis_name]
    mx = get_matrix_for_space(context, space)
    select_mode = tuple(context.scene.tool_settings.mesh_select_mode)

    groups, has_multiple = get_selection_groups(bm, select_mode, align_each)
    if not groups:
        return False, False

    for group in groups:
        if space == 'LOCAL':
            axiscoords = [v.co[axis] for v in group]
        elif space == 'WORLD':
            axiscoords = [(active.matrix_world @ v.co)[axis] for v in group]
        elif space == 'CURSOR':
            axiscoords = [(mx.inverted_safe() @ active.matrix_world @ v.co)[axis] for v in group]

        if align_type == "MIN":
            target = min(axiscoords)
        elif align_type == "MAX":
            target = max(axiscoords)
        elif align_type == "ZERO":
            target = 0
        elif align_type == "AVERAGE":
            target = sum(axiscoords) / len(axiscoords)
        elif align_type == "CURSOR":
            if space == 'LOCAL':
                target = (mx.inverted_safe() @ context.scene.cursor.location)[axis]
            elif space == 'WORLD':
                target = context.scene.cursor.location[axis]
            elif space == 'CURSOR':
                target = 0

        for v in group:
            if space == 'LOCAL':
                v.co[axis] = target
            elif space == 'WORLD':
                world_co = active.matrix_world @ v.co
                world_co[axis] = target
                v.co = active.matrix_world.inverted_safe() @ world_co
            elif space == 'CURSOR':
                cursor_co = mx.inverted_safe() @ active.matrix_world @ v.co
                cursor_co[axis] = target
                v.co = active.matrix_world.inverted_safe() @ mx @ cursor_co

    bm.normal_update()
    bmesh.update_edit_mesh(active.data)
    return True, has_multiple


# UTIL ##############

def get_right_and_up_axes(context, mx):
    r3d = context.space_data.region_3d

    view_right = r3d.view_rotation @ Vector((1, 0, 0))
    view_up = r3d.view_rotation @ Vector((0, 1, 0))
    view_back = r3d.view_rotation @ Vector((0, 0, 1)) # Вектор глубины (взгляд)

    axes_right, axes_up, axes_back = [], [], []

    for idx, axis in enumerate([Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))]):
        world_axis = mx.to_3x3() @ axis
        axes_right.append((view_right.dot(world_axis), idx))
        axes_up.append((view_up.dot(world_axis), idx))
        axes_back.append((view_back.dot(world_axis), idx))

    # Сортируем оси по степени совпадения
    axes_right.sort(key=lambda x: abs(x[0]), reverse=True)
    axes_up.sort(key=lambda x: abs(x[0]), reverse=True)

    axis_right = axes_right[0]
    axis_up = axes_up[0]

    # ЗАЩИТА ОТ КОЛЛИЗИЙ: Если правая и верхняя оси совпали, берем для UP вторую по значимости
    if axis_right[1] == axis_up[1]:
        axis_up = axes_up[1]

    flip_right = axis_right[0] < 0
    flip_up = axis_up[0] < 0

    return axis_right[1], axis_up[1], flip_right, flip_up

#endregion

import bpy

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


def ExtendSelectionToHigh():
    obj = bpy.context.object
    if not obj:
        return

    splited_name = obj.name.split("_")
    if len(splited_name) < 2:
        return
    
    del splited_name[-1]

    for o in bpy.data.objects:
        splited_name_high = o.name.split("_")
        del splited_name_high[-1]

        if splited_name == splited_name_high:
            # print(o.name)
            o.select_set(True)

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

# def show_utility_objects(obj):
    
#     if obj.hide_get():
#         obj.hide_set(False)

#     utils = []
    
#     for child in obj.children:
#         if child.display_type in {'BOUNDS', 'WIRE'}:
#             utils.extend([child])
            
#     for mod_obj in get_modifier_objects(obj):
#         utils.extend([mod_obj])

#     for u in utils:        
#         u.hide_set(0)
       

# def hide_utility_objects(obj):

#     utils = []
    
#     for child in obj.children:
#         if child.display_type in {'BOUNDS', 'WIRE'}:
#             utils.extend([child])
            
#     for mod_obj in get_modifier_objects(obj):
#         utils.extend([mod_obj])

#     for u in utils:        
#         u.hide_set(1)


def get_unparented_utility(obj):
    mod_objects = set(get_modifier_objects(obj))
    children = set(obj.children)
    unused = mod_objects - children  # объекты из модификаторов, которые не являются дочерними

    return unused

def toggle_utility_visibilty(obj):
    # Если хотя бы один объект видим — выключить все
    utils = get_utilities(obj)
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


def get_utilities(obj):
    utils = []
    
    for child in obj.children:
        if child.display_type in {'BOUNDS', 'WIRE'}:
            utils.extend([child])
            
    for mod_obj in get_modifier_objects(obj):
        utils.extend([mod_obj])

    return utils


def get_modifier_objects(obj):
    """Возвращает set всех объектов, участвующих в модификаторах объекта obj, включая Geometry Nodes."""
    result = set()
    for mod in obj.modifiers:
        # 1. Стандартные POINTER-ссылки
        for prop in mod.bl_rna.properties:
            if prop.type == 'POINTER' and prop.fixed_type == bpy.types.Object:
                linked_obj = getattr(mod, prop.identifier, None)
                if linked_obj is not None:
                    result.add(linked_obj)
        
        # 2. Geometry Nodes: ищем объекты среди пользовательских свойств
        if mod.type == 'NODES':
            for key, value in mod.items():
                if isinstance(value, bpy.types.Object):
                    result.add(value)
                # Если value — коллекция объектов, добавить их тоже
                if isinstance(value, (list, tuple)):
                    for v in value:
                        if isinstance(v, bpy.types.Object):
                            result.add(v)
        
        if mod.type == 'BOOLEAN' and mod.object:
            result.add(mod.object)

    return result


def set_active_modifier_for_object(main_obj, target_obj):
    """Сделать активным модификатор, который использует target_obj (по логике get_modifier_objects)."""
    for mod in main_obj.modifiers:
        # Получаем объекты только для текущего модификатора!
        mod_objects = set()
        # 1. Стандартные POINTER-ссылки
        for prop in mod.bl_rna.properties:
            if prop.type == 'POINTER' and prop.fixed_type == bpy.types.Object:
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
        # 3. Boolean
        if mod.type == 'BOOLEAN' and mod.object:
            mod_objects.add(mod.object)
        # 4. Curve
        if mod.type == 'CURVE' and mod.object:
            mod_objects.add(mod.object)
        # Проверяем только объекты этого модификатора!
        if target_obj in mod_objects:
            main_obj.modifiers.active = mod
            return


def cycle_index(current, delta, length):
    if length == 0:
        return 0
    return (current + delta) % length


def select_object_by_index(self, context, index, initial_active=None):
    bpy.ops.object.select_all(action='DESELECT')
    if not self._items:
        return
    
    for i, obj in enumerate(self._items):
        if isinstance(obj, bpy.types.Object):
            if i == index:
                obj.hide_set(False)
                if initial_active:
                    # initial_active.select_set(True)
                    context.view_layer.objects.active = initial_active
                    # return
                # obj.select_set(True)
                # context.view_layer.objects.active = obj
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
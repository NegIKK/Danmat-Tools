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

    collection_name_to_create = colletction_of_selected_obj + "_" + suffix

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
def get_bool_objects(obj):
    obj_names = []
    for modifier in obj.modifiers:
        if modifier.type == "BOOLEAN":
            obj_names.insert(-1,modifier.object)
    return(obj_names)


def show_utility_objects(obj):
    if not obj.children:
        return
    
    if obj.hide_get():
        obj.hide_set(False)
    
    for child in obj.children:
        
        if child.display_type in {'BOUNDS', 'WIRE'}:           
            child.hide_set(0)
       

def hide_utility_objects(obj):
    if not obj.children:
        return

    for child in obj.children:

        if child.display_type in {'BOUNDS', 'WIRE'}:
            hide_utility_objects(child)
            child.hide_set(1)
            # print("hide")


def set_children(obj):
    for ob in get_bool_objects(obj):
        ob.select_set(True)     # Выделить объекты
    
    bpy.ops.object.parent_set(keep_transform=True)


def to_collection(obj):
    create_helper_collection("BOOL")
    objs_to_move = get_bool_objects(obj)
    move_to_collection(objs_to_move, create_helper_collection("BOOL"))



# --- Вспомогательная рекурсивная функция ---
def collect_all_children(obj, out):
    for child in obj.children:
        out.add(child)
        collect_all_children(child, out)


# --- Определение детей, участвующих в модификаторах ---
def get_children_used_in_modifiers(active_obj, children):
    used = set()

    for mod in active_obj.modifiers:
        for prop in mod.bl_rna.properties:
            if prop.type == 'POINTER' and prop.fixed_type == bpy.types.Object:
                linked_obj = getattr(mod, prop.identifier, None)
                if linked_obj in children:
                    used.add(linked_obj)

    return used


# --- Главная функция: выделить НЕ участвующих ---
def select_unused_children_utility():
    active = bpy.context.active_object
    if not active:
        return

    # 1. Собираем всех детей
    children = set()
    collect_all_children(active, children)

    if not children:
        return

    # 2. Определяем, какие используются
    used = get_children_used_in_modifiers(active, children)

    # 3. Неиспользуемые = все дети - используемые
    unused = children - used

    # 4. Выделяем
    bpy.ops.object.select_all(action='DESELECT')
    for obj in unused:
        obj.select_set(True)

    # активный остаётся активным
    active.select_set(True)
    bpy.context.view_layer.objects.active = active


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
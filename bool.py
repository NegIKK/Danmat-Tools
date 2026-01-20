import bpy
from . import collections

def get_bool_objects(obj):
    obj_names = []
    for modifier in obj.modifiers:
        if modifier.type == "BOOLEAN":
            obj_names.insert(-1,modifier.object)
    return(obj_names)

# def hide(obj):
#     for ob in get_bool_objects(obj):
#         ob.hide_set(1)


# def show(obj):
#     for ob in get_bool_objects(obj):
#         ob.hide_set(0)

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
    collections.Create_Helper_Collection("BOOL")
    objs_to_move = get_bool_objects(obj)
    collections.Move_To_Collection(objs_to_move, collections.Create_Helper_Collection("BOOL"))



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

import bpy
from . import collections

def get_bool_objects(obj):
    obj_names = []
    for modifier in obj.modifiers:
        if modifier.type == "BOOLEAN":
            obj_names.insert(-1,modifier.object)
    return(obj_names)

# def Get_Bool_Type():

def hide(obj):
    for ob in get_bool_objects(obj):
        # ob.hide_viewport = True
        ob.hide_set(1)


def show (obj):
    for ob in get_bool_objects(obj):
        # ob.hide_viewport = False
        ob.hide_set(0)


def set_children(obj):
    for ob in get_bool_objects(obj):
        ob.select_set(True)     # Выделить объекты
    
    bpy.ops.object.parent_set(keep_transform=True)


def to_collection(obj):
    collections.Create_Helper_Collection("BOOL")
    objs_to_move = get_bool_objects(obj)
    collections.Move_To_Collection(objs_to_move, collections.Create_Helper_Collection("BOOL"))
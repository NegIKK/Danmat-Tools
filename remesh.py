import bpy

# def get_modifier(obj, ):

def disable(obj, modifier_type, modifier_name):   
    for modifier in obj.modifiers:
        if modifier.type == modifier_type:
            obj.modifiers[modifier_name].show_viewport = False  

def enable(obj, modifier_type, modifire_name):           
    for modifier in obj.modifiers:
        if modifier.type == modifier_type:
            obj.modifiers[modifire_name].show_viewport = True

def remove(modifier_name):
    for obj in bpy.context.selected_objects:
        modifier_to_remove = obj.modifiers.get(modifier_name)
        if modifier_to_remove is not None:
            obj.modifiers.remove(modifier_to_remove)
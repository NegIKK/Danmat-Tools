import bpy

def rename():
    # Active Object Cache
    active_object = bpy.context.view_layer.objects.active
    if not active_object:
        return
    
    base_name = active_object.name



    # Renaming active oblect
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
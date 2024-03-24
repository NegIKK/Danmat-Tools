import bpy

def Rename():
    # Active Object Cache
    active_object = bpy.context.view_layer.objects.active
    name = active_object.name

    # Renaming active oblect
    splitNameLow = name.split("_")
    lastPartNameLow = splitNameLow[-1]

    if lastPartNameLow == "low":
        stripped_name_low = name.strip("_low")
        active_object.name = stripped_name_low + "_low"
    else:
        active_object.name = name + "_low"   


    # Renaming selected objects
    for obj in bpy.context.selected_objects:
        
        splitNameHigh = obj.name.split("_")
        lastPartNameHigh = splitNameHigh[-1]
        
        if obj != active_object:
            if lastPartNameHigh == "high":
                obj.name = obj.name.strip("_high")
                obj.name = name.strip("_low") + "_high"
            else:
                obj.name = name.strip("_low") + "_high"                  
            

def SetWireActive():
    activeObject = bpy.context.view_layer.objects.active
    activeObject.display_type = 'WIRE'


def ExtendSelectionToHigh():
    obj = bpy.context.object

    splited_name = obj.name.split("_")
    del splited_name[-1]

    for o in bpy.data.objects:
        splited_name_high = o.name.split("_")
        del splited_name_high[-1]

        if splited_name == splited_name_high:
            print(o.name)
            o.select_set(True)
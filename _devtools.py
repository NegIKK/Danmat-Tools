import bpy

screw_flipped = False

def flip_srew_normals():
    global screw_flipped
    modifiers = bpy.context.object.modifiers

    for mod in modifiers:
        if mod.type == "SCREW":
            if screw_flipped:
                mod.use_normal_flip = False
                screw_flipped = not screw_flipped
            else:
                mod.use_normal_flip = True
                screw_flipped = not screw_flipped
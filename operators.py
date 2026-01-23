import bpy
from . import main_tools

class UV_OT_DebugTestA(bpy.types.Operator):
    bl_idname = "uv.debug_test_a"
    bl_label = "Select non-aligned Edges"
    bl_description = "Description that shows in blender tooltips"
    bl_options = {'UNDO'}

    def execute(self, context):

        return {'FINISHED'}

# BOOL
class OBJECT_OT_BoolHide(bpy.types.Operator):
    """Tooltip"""
    bl_label = "Hide Bools"
    bl_idname = "object.bool_hide"
    bl_options = {'UNDO'}
   
    def execute(self, context):

        for obj in bpy.context.selected_objects:
            main_tools.hide_utility_objects(obj)

        return {'FINISHED'}
    
class OBJECT_OT_BoolShow(bpy.types.Operator):
    """Tooltip"""
    bl_label = "Show Bools"
    bl_idname = "object.bool_show"
    bl_options = {'UNDO'}
   
    def execute(self, context):
        
        for obj in bpy.context.selected_objects:
            main_tools.show_utility_objects(obj)

        return {'FINISHED'}
    
class OBJECT_OT_BoolSetChildren(bpy.types.Operator):
    """Делает бъекты булевых операций дочерними главному, отправляет в отдельную коллекцию и скрывает"""
    bl_label = "Contain and Hide"
    bl_idname = "object.bool_set_children"
    bl_options = {'UNDO'}
   
    def execute(self, context):
        
        obj = bpy.context.object
        main_tools.show_utility_objects(obj)
        main_tools.set_children(obj)
        main_tools.to_collection(obj)
        main_tools.hide_utility_objects(obj)

        return {'FINISHED'}
    
class OBJECT_OT_SelectUnusedUnility(bpy.types.Operator):
    """Делает бъекты булевых операций дочерними главному, отправляет в отдельную коллекцию и скрывает"""
    bl_label = "Select Unused Utility"
    bl_idname = "object.select_unused_utility"
    bl_options = {'UNDO'}
   
    def execute(self, context):
        
        main_tools.select_unused_children_utility()

        return {'FINISHED'}

class OBJECT_OT_RenameSimple(bpy.types.Operator):
    """Set suffixes. Active object - Lowpoly, Other Selected objects - Highpoly
    SHIFT - isolate renamed objects to inspect"""
    bl_label = "Rename"
    bl_idname = "object.rename_simple"
    bl_options = {'UNDO'}
   
    def invoke(self, context, event):
        
        main_tools.rename()
        if getattr(bpy.context.scene.danmat_tools_props, 'use_alt_separator') == True:
            main_tools.swap_num_separator(bpy.context.selected_objects, "_")

        if event.shift:
            main_tools.set_wire_mode()
            bpy.ops.view3d.localview()

        return {'FINISHED'}
    
class OBJECT_OT_ExtendSelection(bpy.types.Operator):
    """Select all objects in bake group
    SHIFT - isolate objects to inspect"""
    bl_label = "Select Bake Group"
    bl_idname = "object.extend_selection"
    bl_options = {'UNDO'}
   
    def invoke(self, context, event):

        main_tools.ExtendSelectionToHigh()

        if event.shift:
            bpy.ops.view3d.localview()

        return {'FINISHED'}   

# class remesh_enable(bpy.types.Operator):
#     """"""
#     bl_label = "Enable Remesh"
#     bl_idname = "object.remesh_enable"
#     bl_options = {'UNDO'}
   
#     def execute(self, context):
        
#         for obj in bpy.context.selected_objects:
#             remesh.enable(obj, "NODES", "SDF")

#         return {'FINISHED'}
    
# class remesh_disable(bpy.types.Operator):
#     """"""
#     bl_label = "Disable Remesh"
#     bl_idname = "object.remesh_disable"
#     bl_options = {'UNDO'}
   
#     def execute(self, context):
        
#         for obj in bpy.context.selected_objects:
#             remesh.disable(obj, "NODES", "SDF")

#         return {'FINISHED'}

classes_to_register = [
    # UV_OT_DebugTestA,
    OBJECT_OT_BoolHide,
    OBJECT_OT_BoolShow,
    OBJECT_OT_BoolSetChildren,
    # OBJECT_OT_SelectUnusedUnility,
    OBJECT_OT_RenameSimple,
    OBJECT_OT_ExtendSelection
]

def register():
    for cls in classes_to_register:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)
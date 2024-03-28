bl_info = {
    "name": "Danmat Tools",
    "author": "Daniel Matus",
    "version": (0, 5),
    "blender": (3, 6, 8),
    "location": "View3D > N-Panel",
    "description": "Quickly rename objects for baking. More structured work with booleans",
    "warning": "",
    "doc_url": "",
    "category": "3D View",
}

import bpy

# from . import collection_ops
from . import bool
from . import rename
from . import remesh
from . import _devtools

from bpy.props import (StringProperty,
                       BoolProperty,
                       IntProperty,
                       FloatProperty,
                       FloatVectorProperty,
                       EnumProperty,
                       PointerProperty,
                       )

# -----------------------
# PROPERTY GROUP
# -----------------------
class MY_PG_SceneProperties(bpy.types.PropertyGroup):
    use_alt_separator: BoolProperty(
        name= "Alternative Separator",
        description="Using '_' instead of '.'",
        default= False
        )

# -----------------------
# OPERATORS
# -----------------------

# BOOL

class bool_hide(bpy.types.Operator):
    """Tooltip"""
    bl_label = "Hide Bools"
    bl_idname = "object.bool_hide"
   
    def execute(self, context):

        for obj in bpy.context.selected_objects:
            bool.hide(obj)

        return {'FINISHED'}
    
class bool_show(bpy.types.Operator):
    """Tooltip"""
    bl_label = "Show Bools"
    bl_idname = "object.bool_show"
   
    def execute(self, context):
        
        for obj in bpy.context.selected_objects:
            bool.show(obj)

        return {'FINISHED'}
    
class bool_set_children(bpy.types.Operator):
    """Делает бъекты булевых операций дочерними главному, отправляет в отдельную коллекцию и скрывает"""
    bl_label = "Contain and Hide"
    bl_idname = "object.bool_set_children"
   
    def execute(self, context):
        
        obj = bpy.context.object
        bool.show(obj)
        bool.to_collection(obj)
        bool.set_children(obj)
        bool.hide(obj)

        return {'FINISHED'}

# REMESH
    
class remesh_enable(bpy.types.Operator):
    """"""
    bl_label = "Enable Remesh"
    bl_idname = "object.remesh_enable"
   
    def execute(self, context):
        
        for obj in bpy.context.selected_objects:
            remesh.enable(obj, "NODES", "SDF")

        return {'FINISHED'}
    
class remesh_disable(bpy.types.Operator):
    """"""
    bl_label = "Disable Remesh"
    bl_idname = "object.remesh_disable"
   
    def execute(self, context):
        
        for obj in bpy.context.selected_objects:
            remesh.disable(obj, "NODES", "SDF")

        return {'FINISHED'}

# RENAME
    
class rename_simple(bpy.types.Operator):
    """Set suffixes. Active object - Lowpoly, Other Selected objects - Highpoly
    SHIFT - isolate renamed objects to inspect"""
    bl_label = "Rename"
    bl_idname = "object.rename_simple"
   
    def invoke(self, context, event):
        
        rename.rename()
        if getattr(bpy.context.scene.my_tool, 'use_alt_separator') == True:
            rename.swap_num_separator(bpy.context.selected_objects, "_")

        if event.shift:
            rename.set_wire_mode()
            bpy.ops.view3d.localview()

        return {'FINISHED'}
    
class extend_selection(bpy.types.Operator):
    """Select all objects in bake group
    SHIFT - isolate objects to inspect"""
    bl_label = "Select Bake Group"
    bl_idname = "object.extend_selection"
   
    def invoke(self, context, event):
        
        rename.ExtendSelectionToHigh()

        if event.shift:
            bpy.ops.view3d.localview()

        return {'FINISHED'}    
    
# DEV
    
class flip_screw(bpy.types.Operator):
    """"""
    bl_label = "flip_screw"
    bl_idname = "object.flip_screw"
   
    def execute(self, context):
        
        _devtools.flip_srew_normals()

        return {'FINISHED'}

# class backup_obj(bpy.types.Operator):
#     """Tooltip"""
#     bl_label = "Backup"
#     bl_idname = "object.backup_obj"
   
#     def execute(self, context):
        
        

#         return {'FINISHED'}
    

# -----------------------
# PANEL
# -----------------------
    

class Danmat_Panel:
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'DAN'
    # bl_options = {"DEFAULT_CLOSED"}
        
class main_panel(Danmat_Panel, bpy.types.Panel):
    bl_idname = "Danmat"
    bl_label = "Danmat Tools"

    def draw(self, context):
        layout = self.layout
        
        # DEBUG
        row = layout.row()
        row.label(text= "DEBUG")

        row = layout.row(align=True)
        row.operator("object.flip_screw")
       

class bool_panel(Danmat_Panel, bpy.types.Panel):
    bl_parent_id = "Danmat"
    bl_label = "Bools"

    def draw(self, context):
        layout = self.layout

        # Bools
        # row = layout.row()
        # row.label(text= "Bools")

        col = layout.column(align=True)
        row = col.row(align=True)
        row.operator("object.bool_hide")
        row.operator("object.bool_show")
        col.operator("object.bool_set_children")

class remesh_panel(Danmat_Panel, bpy.types.Panel):
    bl_parent_id = "Danmat"
    bl_label = "Remesh"

    def draw(self, context):
        layout = self.layout

        row = layout.row(align=True)
        row.operator("object.remesh_enable")
        row.operator("object.remesh_disable")



class naming_panel(Danmat_Panel, bpy.types.Panel):
    bl_parent_id = "Danmat"
    bl_label = "Naming"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        mytool = scene.my_tool

        row = layout.row(align=True)
        row.operator("object.rename_simple")
        row.operator("object.rename_isolate")
        
        row = layout.row(align=True)
        row.prop(mytool, "use_alt_separator")

        row = layout.row(align=True)
        row.operator("object.extend_selection")


# Регистрация для того, чтоб отображалось в интерфейсе, иначе не запашет

classes_to_register = (
    flip_screw,
    
    main_panel,
    bool_panel,
    remesh_panel,
    naming_panel,

    bool_hide,
    bool_show,
    bool_set_children,

    remesh_enable,
    remesh_disable,

    rename_simple,
    extend_selection,

    MY_PG_SceneProperties
    )

def register():
    for cls in classes_to_register:
        bpy.utils.register_class(cls)

    bpy.types.Scene.my_tool = PointerProperty(type=MY_PG_SceneProperties)

def unregister():
    for cls in classes_to_register:
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
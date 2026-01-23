import bpy
from . import operators

def get_panel_category():
    prefs = bpy.context.preferences.addons[__package__].preferences
    return prefs.panel_category


# class UV_PT_CustomPanel(bpy.types.Panel):
#     bl_label = "UV Edge Selector"
#     bl_space_type = 'IMAGE_EDITOR'
#     bl_region_type = 'UI'
#     bl_category = 'TEMP'

#     @classmethod
#     def poll(cls, context):
#         cls.bl_category = get_panel_category()
#         return True

#     def draw(self, context):
#         layout = self.layout
#         scene = context.scene

#         layout.label(text='Debug')
        
#         col = layout.column(align=True)
#         col.operator(operators.UV_OT_DebugTestA.bl_idname)

#         row = col.row(align=True)
#         row.prop(scene.uv_edge_selector, "min_angle")
#         row.prop(scene.uv_edge_selector, "max_angle")


class VIEW3D_PT_DanmatPanel:
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'TEMP'
    # bl_options = {"DEFAULT_CLOSED"}
    
    @classmethod
    def poll(cls, context):
        cls.bl_category = get_panel_category()
        return True

        
class VIEW3D_PT_Main(VIEW3D_PT_DanmatPanel, bpy.types.Panel):
    bl_idname = "VIEW3D_PT_Main"
    bl_label = "Danmat Tools"

    def draw(self, context):
        layout = self.layout
        
        # DEBUG
        # row = layout.row()
        # row.label(text= "DEBUG")

        # row = layout.row(align=True)
        # row.operator("object.flip_screw")
       

class VIEW3D_PT_Bool(VIEW3D_PT_DanmatPanel, bpy.types.Panel):
    bl_parent_id = "VIEW3D_PT_Main"
    bl_label = "Bools"

    def draw(self, context):
        layout = self.layout

        # Bools
        # row = layout.row()
        # row.label(text= "Bools")

        col = layout.column(align=True)
        row = col.row(align=True)
        row.operator(operators.OBJECT_OT_BoolHide.bl_idname)
        row.operator(operators.OBJECT_OT_BoolShow.bl_idname)
        col.operator(operators.OBJECT_OT_BoolSetChildren.bl_idname)
        col.operator(operators.OBJECT_OT_SelectUnusedUnility.bl_idname)


# class VIEW3D_PT_Remesh(VIEW3D_PT_DanmatPanel, bpy.types.Panel):
#     bl_parent_id = "Danmat"
#     bl_label = "Remesh"

#     def draw(self, context):
#         layout = self.layout

#         row = layout.row(align=True)
#         row.operator("object.remesh_enable")
#         row.operator("object.remesh_disable")


class VIEW3D_PT_Naming(VIEW3D_PT_DanmatPanel, bpy.types.Panel):
    bl_parent_id = "VIEW3D_PT_Main"
    bl_label = "Naming"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        col = layout.column(align=True)
        row = col.row(align=True)
        row.operator(operators.OBJECT_OT_RenameSimple.bl_idname)
        # row.operator(operators.OBJECT_OT_RenameIsolate.bl_idname)

        row.operator(operators.OBJECT_OT_ExtendSelection.bl_idname)
        
        row = col.row(align=True)
        row.prop(scene.danmat_tools_props, "use_alt_separator")


classes_to_register = [
    # VIEW3D_PT_DanmatPanel,
    VIEW3D_PT_Main,
    VIEW3D_PT_Bool,
    # PT_Remesh,
    VIEW3D_PT_Naming
]

def register():
    for cls in classes_to_register:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)
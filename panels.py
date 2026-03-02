import bpy
from . import operators

def get_panel_category():
    prefs = bpy.context.preferences.addons[__package__].preferences
    return prefs.panel_category



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
        scene = context.scene

        row = layout.row()
        col = layout.column(align=True)

        col.operator(operators.VIEW3D_OT_MainPieMenu.bl_idname)
        col.separator()
        col.operator(operators.OBJECT_OT_ToggleUtilsVisibility.bl_idname)
        col.operator(operators.VIEW3D_OT_OverlayManageUtils.bl_idname)
        col.separator()
        col.prop(scene.danmat_tools_props, "set_selected_util_obj_active")
        col.prop(scene.danmat_tools_props, "exclude_mirror")
        # col.operator(operators.VIEW3D_OT_ToggleFlippedFaces.bl_idname)
        # col.operator(operators.OBJECT_OT_BoolSetChildren.bl_idname)
        # col.operator(operators.OBJECT_OT_SelectUnusedUtility.bl_idname)

        # DEBUG
        # row = layout.row()
        # row.label(text= "DEBUG")

        # row = layout.row(align=True)
        # row.operator("object.flip_screw")
       


# class VIEW3D_PT_Bool(VIEW3D_PT_DanmatPanel, bpy.types.Panel):
#     bl_parent_id = "VIEW3D_PT_Main"
#     bl_label = "Bools"

#     def draw(self, context):
#         layout = self.layout

#         # Bools
#         # row = layout.row()
#         # row.label(text= "Bools")

#         col = layout.column(align=True)
#         row = col.row(align=True)
#         row.operator(operators.OBJECT_OT_ToggleUtilsVisibility.bl_idname)
#         col.operator(operators.VIEW3D_OT_OverlayManageUtils.bl_idname)
#         col.operator(operators.OBJECT_OT_BoolSetChildren.bl_idname)
#         # col.operator(operators.OBJECT_OT_SelectUnusedUtility.bl_idname)



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

        col = layout.column()
        row = col.row(align=True)
        row.operator(operators.OBJECT_OT_RenameSimple.bl_idname)
        # row.operator(operators.OBJECT_OT_RenameIsolate.bl_idname)

        row.operator(operators.OBJECT_OT_BakeGroupSelect.bl_idname)
        
        row = col.row(align=True)
        # row.prop(scene.danmat_tools_props, "use_alt_separator")
        col.separator()
        col.label(text="Settings")
        col.prop(scene.danmat_tools_props, "wire_after_rename")
        col.prop(scene.danmat_tools_props, "hide_after_rename")
        col.prop(scene.danmat_tools_props, "digits_separator")



class VIEW3D_PT_Testing(VIEW3D_PT_DanmatPanel, bpy.types.Panel):
    bl_parent_id = "VIEW3D_PT_Main"
    bl_label = "Testing"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        col = layout.column(align=True)
        row = col.row(align=True)
        # col.operator(operators.VIEW3D_OT_overlay_example.bl_idname)
        # col.separator()
        # col.operator(operators.VIEW3D_OT_overlay_select_object.bl_idname)
        col.separator()
        
        # col.operator(operators.OBJECT_OT_GetModifiersObjects.bl_idname)



# Pie Menu

# class OBJECT_PT_PieMenuPanel(bpy.types.Panel):
#     bl_idname = "OBJECT_PT_pie_menu_panel"
#     bl_label = "Settings"
#     bl_space_type = "VIEW_3D"
#     bl_region_type = "TOOLS"
#     bl_category = "category"

#     def draw(self, context):
#         layout = self.layout
        

class VIEW3D_MT_MainPieMenu(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_main_pie_menu"
    bl_label = "Danmat Tools"

    def draw(self, context):
        pie = self.layout.menu_pie()
        pie.operator(operators.OBJECT_OT_RenameSimple.bl_idname) # left
        pie.operator(operators.VIEW3D_OT_OverlayManageUtils.bl_idname) # right

        pie.separator()
        # op = pie.operator("wm.call_panel") # bottom
        # op.name = "VIEW3D_PT_Main"
        # op.keep_open = True


        pie.operator(operators.OBJECT_OT_ToggleUtilsVisibility.bl_idname) # top
        pie.separator() # left up
        pie.separator() # right up
        pie.operator(operators.OBJECT_OT_BakeGroupSelect.bl_idname)


classes_to_register = [
    # VIEW3D_PT_DanmatPanel,
    VIEW3D_PT_Main,
    # VIEW3D_PT_Bool,
    # PT_Remesh,
    VIEW3D_PT_Naming,
    # VIEW3D_PT_Testing,
    VIEW3D_MT_MainPieMenu
]

def register():
    for cls in classes_to_register:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)
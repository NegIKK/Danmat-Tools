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
    
# class backup_obj(bpy.types.Operator):
#     """Tooltip"""
#     bl_label = "Backup"
#     bl_idname = "object.backup_obj"
   
#     def execute(self, context):
        
        

#         return {'FINISHED'}

# PANEL

class Danmat_Panel:
    # bl_label = "Danmat Tools"
    # bl_idname = "Panel_PT_DanmatTools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'DAN'
    # bl_options = {"DEFAULT_CLOSED"}

    # # Отрисовка интерфейса панели
    # def draw(self, context):
    #     layout = self.layout
        
        

        

class main_panel(Danmat_Panel, bpy.types.Panel):
    bl_idname = "Danmat"
    bl_label = "Danmat Tools"

    def draw(self, context):
        layout = self.layout
        
        # DEBUG
        row = layout.row()
        row.label(text= "DEBUG")

        row = layout.row(align=True)
        row.operator("object.bool_hide")
        
        # MAIN
        # row = layout.row()
        # row.label(text= "Bake Assistant")

        

        # col = layout.column(align=True)
        # col.operator("otp.renamer_sort_collections")

        # 
        row = layout.row()
        row.label(text= "Remesh Controller")
        
        col = layout.column(align=True)
        row = col.row(align=True)
        row.operator("otp.remesh_enable")
        row.operator("otp.remesh_disable")
        col.operator("otp.remesh_remove")

        

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

class naming_panel(Danmat_Panel, bpy.types.Panel):
    bl_parent_id = "Danmat"
    bl_label = "Naming"

    def draw(self, context):
        layout = self.layout

        row = layout.row(align=True)
        row.operator("object.get_coll_name")
        row.operator("otp.renamer_rename_isolate")

        row = layout.row(align=True)
        row.operator("otp.renamer_extend_selection")
        row.operator("otp.renamer_extend_selection_isolate")

# Регистрация для того, чтоб отображалось в интерфейсе, иначе не запашет

classes_to_register = (
    # Danmat_Panel, 
    main_panel,
    bool_panel,
    naming_panel,
    # Renamer_Rename,
    # Renamer_Rename_Isolate,
    # Renamer_Extend_Selection,
    # Renamer_Extend_Selection_Isolate,
    # Renamer_Sort_Collections,
    # Remesh_Enable,
    # Remesh_Disable,
    # Remesh_Remove,
    bool_hide,
    bool_show,
    bool_set_children
    # get_coll_name
    )

def register():
    for cls in classes_to_register:
        bpy.utils.register_class(cls) 

def unregister():
    for cls in classes_to_register:
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
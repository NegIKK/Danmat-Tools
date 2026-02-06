from multiprocessing import context
import bpy
from . import main_tools
from . import screen_overlay

class UV_OT_DebugTestA(bpy.types.Operator):
    bl_idname = "uv.debug_test_a"
    bl_label = "Select non-aligned Edges"
    bl_description = "Description that shows in blender tooltips"
    bl_options = {'UNDO'}

    def execute(self, context):

        return {'FINISHED'}

# BOOL
class OBJECT_OT_ToggleUtilsVisibility(bpy.types.Operator):
    """Tooltip"""
    bl_label = "Toggle Utils"
    bl_idname = "object.bool_hide"
    bl_options = {'UNDO'}
   
    def execute(self, context):

        for obj in bpy.context.selected_objects:
            main_tools.toggle_utility_visibilty(obj)

        return {'FINISHED'}
    
# class OBJECT_OT_BoolShow(bpy.types.Operator):
#     """Tooltip"""
#     bl_label = "Show Bools"
#     bl_idname = "object.bool_show"
#     bl_options = {'UNDO'}
   
#     def execute(self, context):
        
#         for obj in bpy.context.selected_objects:
#             main_tools.show_utility_objects(obj)

#         return {'FINISHED'}
    
class OBJECT_OT_BoolSetChildren(bpy.types.Operator):
    """Делает бъекты булевых операций дочерними главному, отправляет в отдельную коллекцию и скрывает"""
    bl_label = "Contain and Hide"
    bl_idname = "object.bool_set_children"
    bl_options = {'UNDO'}
   
    def execute(self, context):
        
        obj = bpy.context.object
        main_tools.show_utility_objects(obj)
        main_tools.set_utility_as_child(obj)
        main_tools.to_collection(obj)
        main_tools.hide_utility_objects(obj)

        return {'FINISHED'}
    
class OBJECT_OT_SelectUnusedUtility(bpy.types.Operator):
    """Делает бъекты булевых операций дочерними главному, отправляет в отдельную коллекцию и скрывает"""
    bl_label = "Select Unused Utility"
    bl_idname = "object.select_unused_utility"
    bl_options = {'UNDO'}
   
    def execute(self, context):
        
        main_tools.select_unused_children_utility()

        return {'FINISHED'}

class OBJECT_OT_RenameSimple(bpy.types.Operator):
    """Set suffixes. Active object - Lowpoly, Other Selected objects - Highpoly
    ALT - rename and isolate renamed objects"""
    bl_label = "Rename"
    bl_idname = "object.rename_simple"
    bl_options = {'UNDO'}
   
    def invoke(self, context, event):

        objects = bpy.context.selected_objects
        if len(objects) <= 1:
            self.report({'WARNING'}, "Nothing to rename")
            
            return {'CANCELLED'}
        
        main_tools.rename()
        if getattr(bpy.context.scene.danmat_tools_props, 'use_alt_separator') == True:
            main_tools.swap_num_separator(objects, "_")

        if event.alt:
            main_tools.set_wire_mode()
            bpy.ops.view3d.localview()

        # if event.alt:

        self.report({'INFO'}, "Bake Group Renamed")

        return {'FINISHED'}
    
class OBJECT_OT_BakeGroupSelect(bpy.types.Operator):
    """Select all objects in bake group
    ALT - select and isolate objects"""
    bl_label = "Select Bake Group"
    bl_idname = "object.bake_group_select"
    bl_options = {'UNDO'}
   
    def invoke(self, context, event):

        main_tools.ExtendSelectionToHigh()

        if event.alt:
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

######## TEST ZONE
        

class VIEW3D_OT_overlay_select_object(bpy.types.Operator):
    bl_idname = "view3d.overlay_select_object"
    bl_label = "Overlay Select Object (Modal)"
    bl_options = {'REGISTER'}

    _draw_handler = None
    _items = []
    _active_index = 0

    def invoke(self, context, event):
        # Список объектов — например, все объекты в сцене
        self._items = [obj.name for obj in context.selected_objects]
        if not self._items:
            self._items = ["Nothing selected"]

        self._active_index = 0

        # Сбросить выделение
        bpy.ops.object.select_all(action='DESELECT')

        # Выделить первый объект
        main_tools.select_object_by_index(self, context, self._active_index)

        # Передаём данные в overlay
        screen_overlay.set_header("Scroll selected objects")
        screen_overlay.set_description(["Wheel - Navigatin", "LMB - Confirm", "RMB/ESC - Cancel"])
        screen_overlay.set_lines(self._items)
        screen_overlay.set_active(self._active_index)
        screen_overlay.set_position(event.mouse_region_x, event.mouse_region_y)

        self._draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            screen_overlay.draw, (), 'WINDOW', 'POST_PIXEL'
        )

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            screen_overlay.set_position(event.mouse_region_x, event.mouse_region_y)
            context.area.tag_redraw()

        if event.type == 'WHEELUPMOUSE':
            self._active_index = max(0, self._active_index - 1)
            main_tools.select_object_by_index(self, context, self._active_index)
            screen_overlay.set_active(self._active_index)
            context.area.tag_redraw()
            return {'RUNNING_MODAL'}

        if event.type == 'WHEELDOWNMOUSE':
            self._active_index = min(len(self._items) - 1, self._active_index + 1)
            main_tools.select_object_by_index(self, context, self._active_index)
            screen_overlay.set_active(self._active_index)
            context.area.tag_redraw()
            return {'RUNNING_MODAL'}

        if event.type == 'LEFTMOUSE':
            self.finish(context)
            return {'FINISHED'}

        if event.type in {'ESC', 'RIGHTMOUSE'}:
            self.finish(context)
            return {'CANCELLED'}

        return {'PASS_THROUGH'}


    def finish(self, context):
        if self._draw_handler:
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
            self._draw_handler = None
        screen_overlay.clear()
        context.area.tag_redraw()


class VIEW3D_OT_OverlayManageUtils(bpy.types.Operator):
    bl_idname = "view3d.overlay_manage_utils"
    bl_label = "Manage Utilities"
    bl_description = "Scroll active object utilities and manage"
    bl_options = {'REGISTER', 'UNDO'}

    _draw_handler = None
    _items = []
    _active_index = 0
    _initial_active = None


    def invoke(self, context, event):

        obj = context.active_object
        self._initial_active = context.active_object

        if context.mode != 'OBJECT':
            self.report({'WARNING'}, "Object mode only")
            return {'CANCELLED'}

        # Берем объекты из модификаторов и конвертируем их в имена для верной работы
        self._items = sorted(main_tools.get_modifier_objects(obj), key=lambda o: o.name)
        if not self._items:
            self.report({'WARNING'}, "No Utilities")
            return {'CANCELLED'}

        self._active_index = 0

        # Сбросить выделение
        bpy.ops.object.select_all(action='DESELECT')

        # Выделить первый объект
        main_tools.select_object_by_index(self, context, self._active_index)

        # Передаём данные в overlay
        screen_overlay.set_header("Scroll selected objects") #Назначаем заголовок
        screen_overlay.set_description(["Wheel - Navigatin", "LMB - Confirm"]) # Назначаем описание
        screen_overlay.set_lines([obj.name for obj in self._items]) # Передаем имена объектов
        screen_overlay.set_active(self._active_index) # Делаем активным элемент соответствующий индексу
        screen_overlay.set_position(event.mouse_region_x, event.mouse_region_y)

        self._draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            screen_overlay.draw, (), 'WINDOW', 'POST_PIXEL'
        )

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            screen_overlay.set_position(event.mouse_region_x, event.mouse_region_y)
            context.area.tag_redraw()

        if event.type == 'WHEELUPMOUSE':
            self._active_index = main_tools.cycle_index(self._active_index, -1, len(self._items))
            main_tools.select_object_by_index(self, context, self._active_index, self._initial_active)

            active_obj = self._items[self._active_index]
            main_tools.set_active_modifier_for_object(self._initial_active, active_obj)

            screen_overlay.set_active(self._active_index)
            context.area.tag_redraw()
            
            return {'RUNNING_MODAL'}

        if event.type == 'WHEELDOWNMOUSE':
            self._active_index = main_tools.cycle_index(self._active_index, 1, len(self._items))
            main_tools.select_object_by_index(self, context, self._active_index, self._initial_active)

            active_obj = self._items[self._active_index]
            main_tools.set_active_modifier_for_object(self._initial_active, active_obj)

            screen_overlay.set_active(self._active_index)
            context.area.tag_redraw()
            
            return {'RUNNING_MODAL'}

        if event.type == 'LEFTMOUSE':
            self.finish(context, cancelled=False)
            
            return {'FINISHED'}

        if event.type in {'ESC', 'RIGHTMOUSE'}:
            self.finish(context, cancelled=True)
            
            return {'CANCELLED'}

        return {'PASS_THROUGH'}


    def finish(self, context, cancelled=False):
        if self._draw_handler:
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
            self._draw_handler = None
        screen_overlay.clear()

        if cancelled and self._initial_active:
            bpy.ops.object.select_all(action='DESELECT')
            self._initial_active.hide_set(False)
            self._initial_active.select_set(True)

            utils = main_tools.get_modifier_objects(self._initial_active)
            for u in utils:
                u.hide_set(True)

            context.view_layer.objects.active = self._initial_active
        context.area.tag_redraw()


# class OBJECT_OT_GetModifiersObjects(bpy.types.Operator):
#     bl_idname = "object.get_modifiers_objects"
#     bl_label = "Get Modifiers Objects"
#     bl_description = "Description that shows in blender tooltips"
#     bl_options = {"REGISTER", "UNDO"}

#     @classmethod
#     def poll(cls, context):
#         return True

#     def execute(self, context):
#         obj = context.active_object
#         if not obj:
#             self.report({'WARNING'}, "Нет активного объекта")
#             return {'CANCELLED'}
        
#         objects = main_tools.get_modifier_objects(obj)
#         self.report({'INFO'}, f"Найдено объектов: {len(objects)}")
#         for o in objects:
#             print(o.name)
            
#         return {"FINISHED"}


class VIEW3D_OT_MainPieMenu(bpy.types.Operator):
    bl_idname = "view3d.main_pie_menu"
    bl_label = "Danmat Tools Pie Menu"
    bl_description = "Description that shows in blender tooltips"
    bl_options = {"REGISTER"}


    def execute(self, context):
        if context.mode != 'OBJECT':
            self.report({'WARNING'}, "Object mode only")
            return {'CANCELLED'}

        bpy.ops.wm.call_menu_pie(name="VIEW3D_MT_main_pie_menu")
        return {"FINISHED"}



classes_to_register = [
    # UV_OT_DebugTestA,
    OBJECT_OT_ToggleUtilsVisibility,
    OBJECT_OT_BoolSetChildren,
    # OBJECT_OT_SelectUnusedUnility,
    OBJECT_OT_RenameSimple,
    OBJECT_OT_BakeGroupSelect,
    VIEW3D_OT_OverlayManageUtils,
    VIEW3D_OT_MainPieMenu,
]

def register():
    for cls in classes_to_register:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)
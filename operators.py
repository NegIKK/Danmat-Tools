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

######## TEST ZONE

class VIEW3D_OT_overlay_example(bpy.types.Operator):
    bl_idname = "view3d.overlay_example"
    bl_label = "Overlay Example (Modal)"
    bl_options = {'REGISTER'}

    _draw_handler = None
    _items = []
    _active_index = 0

    # --------------------------------------------------
    # START
    # --------------------------------------------------

    def invoke(self, context, event):
        # Тестовые данные
        self._items = [obj.name for obj in context.selected_objects]
        if not self._items:
            self._items = ["Nothing selected"]

        self._active_index = 0

        # Передаём данные в overlay
        screen_overlay.set_header("Header Example")
        screen_overlay.set_description(["Wheel - Navigatin", "LMB - Confirm"])
        screen_overlay.set_lines(self._items)
        screen_overlay.set_active(self._active_index)
        screen_overlay.set_position(
            event.mouse_region_x,
            event.mouse_region_y
        )

        # Регистрируем draw handler
        self._draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            screen_overlay.draw,
            (),
            'WINDOW',
            'POST_PIXEL'
        )

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    # --------------------------------------------------
    # MODAL LOOP
    # --------------------------------------------------

    def modal(self, context, event):
        # Обновляем позицию overlay каждый кадр
        if event.type == 'MOUSEMOVE':
            screen_overlay.set_position(
                event.mouse_region_x,
                event.mouse_region_y
            )
            context.area.tag_redraw()

        # Переключение активного элемента
        if event.type == 'WHEELUPMOUSE':
            self._active_index = max(0, self._active_index - 1)
            screen_overlay.set_active(self._active_index)
            context.area.tag_redraw()
            return {'RUNNING_MODAL'}

        if event.type == 'WHEELDOWNMOUSE':
            self._active_index = min(
                len(self._items) - 1,
                self._active_index + 1
            )
            screen_overlay.set_active(self._active_index)
            context.area.tag_redraw()
            return {'RUNNING_MODAL'}

        # Подтверждение
        if event.type == 'LEFTMOUSE':
            self.finish(context)
            return {'FINISHED'}

        # Отмена
        if event.type in {'ESC', 'RIGHTMOUSE'}:
            self.finish(context)
            return {'CANCELLED'}

        return {'PASS_THROUGH'}

    # --------------------------------------------------
    # CLEANUP
    # --------------------------------------------------

    def finish(self, context):
        if self._draw_handler:
            bpy.types.SpaceView3D.draw_handler_remove(
                self._draw_handler,
                'WINDOW'
            )
            self._draw_handler = None

        screen_overlay.clear()
        context.area.tag_redraw()


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
        screen_overlay.set_description(["Wheel - Navigatin", "LMB - Confirm"])
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


class VIEW3D_OT_overlay_select_utils(bpy.types.Operator):
    bl_idname = "view3d.overlay_select_utils"
    bl_label = "Overlay Select Utils (Modal)"
    bl_options = {'REGISTER'}

    _draw_handler = None
    _items = []
    _active_index = 0

    def invoke(self, context, event):

        obj = context.active_object

        # Берем объекты из модификаторов и конвертируем их в имена для верной работы
        self._items = sorted(main_tools.get_modifier_objects(obj), key=lambda o: o.name)
        if not self._items:
            self._items = ["Nothing selected"]

        self._active_index = 0

        # Сбросить выделение
        bpy.ops.object.select_all(action='DESELECT')

        # Выделить первый объект
        main_tools.select_object_by_index(self, context, self._active_index)

        # Передаём данные в overlay
        screen_overlay.set_header("Scroll selected objects")
        screen_overlay.set_description(["Wheel - Navigatin", "LMB - Confirm"])
        screen_overlay.set_lines([obj.name for obj in self._items] if self._items else ["Nothing selected"] )
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


class OBJECT_OT_GetModifiersObjects(bpy.types.Operator):
    bl_idname = "object.get_modifiers_objects"
    bl_label = "Get Modifiers Objects"
    bl_description = "Description that shows in blender tooltips"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        obj = context.active_object
        if not obj:
            self.report({'WARNING'}, "Нет активного объекта")
            return {'CANCELLED'}
        
        objects = main_tools.get_modifier_objects(obj)
        self.report({'INFO'}, f"Найдено объектов: {len(objects)}")
        for o in objects:
            print(o.name)
            
        return {"FINISHED"}





classes_to_register = [
    # UV_OT_DebugTestA,
    OBJECT_OT_BoolHide,
    OBJECT_OT_BoolShow,
    OBJECT_OT_BoolSetChildren,
    # OBJECT_OT_SelectUnusedUnility,
    OBJECT_OT_RenameSimple,
    OBJECT_OT_ExtendSelection,
    VIEW3D_OT_overlay_example,
    VIEW3D_OT_overlay_select_object,
    VIEW3D_OT_overlay_select_utils,
    OBJECT_OT_GetModifiersObjects,
    
]

def register():
    for cls in classes_to_register:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)
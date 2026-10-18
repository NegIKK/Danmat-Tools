from multiprocessing import context
import bpy
import bmesh
# import mathutils

# from bpy_extras import view3d_utils
from mathutils import Vector, Matrix

from . import main_tools
from .modules import bridge
from . import dev_tools
from . import screen_overlay
from . import overlay_3d
from . import draw_3d

from bpy.props import EnumProperty, BoolProperty

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
        exclude_mirror = getattr(bpy.context.scene.danmat_tools_props, 'exclude_mirror', False)

        for obj in bpy.context.selected_objects:
            main_tools.toggle_utility_visibilty(obj, exclude_mirror)

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


class OBJECT_OT_DebugModifiers(bpy.types.Operator):
    """Отладка: вывести информацию об объектах в модификаторах"""
    bl_label = "Debug Modifiers"
    bl_idname = "object.debug_modifiers"
    bl_options = {'UNDO'}

    def execute(self, context):
        obj = bpy.context.object
        if obj:
            main_tools.debug_modifier_objects(obj)
        return {'FINISHED'}

#region Rename
class OBJECT_OT_RenameSimple(bpy.types.Operator):
    """Set suffixes. Active object - Lowpoly, Other Selected objects - Highpoly
    ALT - rename and isolate renamed objects"""
    bl_label = "Rename"
    bl_idname = "object.rename_simple"
    bl_options = {'UNDO'}
   
    def invoke(self, context, event):

        active_object = bpy.context.active_object
        objects = bpy.context.selected_objects

        scene = bpy.context.scene

        separator = getattr(scene.danmat_tools_props, 'digits_separator')
        wire_after_rename = getattr(scene.danmat_tools_props, 'wire_after_rename')
        hide_after_rename = getattr(scene.danmat_tools_props, 'hide_after_rename')
        
        if len(objects) <= 1:
            self.report({'WARNING'}, "Nothing to rename")
            
            return {'CANCELLED'}
        
        main_tools.rename()
        main_tools.swap_num_separator(objects, separator)

        if wire_after_rename:
            active_object.display_type = 'WIRE'

        if hide_after_rename:
            for obj in objects:
                obj.hide_set(True)

        # if getattr(scene.danmat_tools_props, 'use_alt_separator') == True:
            

        if event.alt:
            main_tools.set_wire_mode()
            bpy.ops.view3d.localview()

        # if event.alt:

        self.report({'INFO'}, "Bake Group Renamed")

        return {'FINISHED'}

#region BakeGroupSelect
class OBJECT_OT_BakeGroupSelect(bpy.types.Operator):
    """Select all objects in bake group
    ALT - select and isolate objects"""
    bl_label = "Select Bake Group"
    bl_idname = "object.bake_group_select"
    bl_options = {'UNDO'}
   
    def invoke(self, context, event):

        active_object = bpy.context.active_object
        objects = bpy.context.selected_objects
        scene = bpy.context.scene

        for obj in objects:
            main_tools.select_bake_group(obj)

        if event.alt:
            bpy.ops.view3d.localview()

        return {'FINISHED'}   

#region ManageUtils
class VIEW3D_OT_OverlayManageUtils(bpy.types.Operator):
    bl_idname = "object.overlay_manage_utils"
    bl_label = "Manage Utilities"
    bl_description = "Scroll active object utilities and manage"
    bl_options = {'REGISTER', 'UNDO'}

    _draw_handler = None
    _items = []
    _active_index = 0
    _initial_active = None

    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT' and context.active_object:
            return True
        return False

    def invoke(self, context, event):
        obj = context.active_object
        exclude_mirror = getattr(bpy.context.scene.danmat_tools_props, 'exclude_mirror')
        self._initial_active = context.active_object
        self._active_obj = None

        if context.mode != 'OBJECT':
            self.report({'WARNING'}, "Object mode only")
            return {'CANCELLED'}

        self._items = sorted(main_tools.get_modifier_objects(obj, exclude_mirror), key=lambda o: o.name)
        if not self._items:
            self.report({'WARNING'}, "No Utilities")
            return {'CANCELLED'}

        self._active_index = 0

        bpy.ops.object.select_all(action='DESELECT')
        main_tools.select_object_by_index(self, context, self._active_index)

        # Сбрасываем старое состояние и активируем оверлей
        screen_overlay.clear()
        screen_overlay.show()

        screen_overlay.set_header("Scroll selected objects")
        screen_overlay.set_description(["Wheel - Navigation", "LMB - Confirm"])
        screen_overlay.set_lines([o.name for o in self._items])
        screen_overlay.set_active(self._active_index)
        screen_overlay.set_position(event.mouse_region_x, event.mouse_region_y)

        self._draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            screen_overlay.draw, (), 'WINDOW', 'POST_PIXEL'
        )

        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        select_utility = getattr(bpy.context.scene.danmat_tools_props, 'set_selected_util_obj_active')

        if event.type == 'MOUSEMOVE':
            screen_overlay.set_position(event.mouse_region_x, event.mouse_region_y)
            context.area.tag_redraw()

        if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'} and event.value == 'PRESS':
            direction = -1 if event.type == 'WHEELUPMOUSE' else 1
            
            self._active_index = main_tools.cycle_index(self._active_index, direction, len(self._items))
            main_tools.select_object_by_index(self, context, self._active_index, self._initial_active, select_utility)

            self.active_obj = self._items[self._active_index]
            main_tools.set_active_modifier_for_object(self._initial_active, self.active_obj)

            # --- ПОЛУЧЕНИЕ ФЕЙСОВ ПОСЛЕ МОДИФИКАТОРОВ ---
            overlay_3d.clear()

            
            # Список индексов всех полигонов итогового меша
            face_indices = [p.index for p in self.active_obj.to_mesh().polygons]
            edge_indices = [p.index for p in self.active_obj.to_mesh().edges]
            vertex_indices = [p.index for p in self.active_obj.to_mesh().vertices]
            
            overlay_3d.register() # На всякий случай, если не вызван ранее

            # overlay_3d.draw_eval_vertex(
            #     active_obj,
            #     vertex_indices,
            #     fade=0.5,
            #     rest_alpha=0.1,
            #     size=0.2
            # )

            overlay_3d.draw_edge(
                self.active_obj,
                edge_indices,
                fade=0.25,
                rest_alpha=0.2,
                width=1
            )

            # -------------------------------------------------- 

            
            screen_overlay.set_active(self._active_index)
            context.area.tag_redraw()
            return {'RUNNING_MODAL'}

        elif event.type == 'LEFTMOUSE':
            main_tools.hide_other_objects(self, self._active_index)
            self.active_obj.hide_set(False)
            self.active_obj.select_set(True)
            self.finish(context, cancelled=False)
            return {'FINISHED'}

        elif event.type in {'ESC', 'RIGHTMOUSE'}:
            main_tools.hide_other_objects(self, self._active_index, hide_all=True)
            self.finish(context, cancelled=True)
            return {'CANCELLED'}

        return {'PASS_THROUGH'}

    def finish(self, context, cancelled=False):
        # Удаляем хэндлер отрисовки
        if self._draw_handler is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
            self._draw_handler = None

        overlay_3d.clear()
        screen_overlay.clear()

        if cancelled and self._initial_active:
            bpy.ops.object.select_all(action='DESELECT')
            self._initial_active.select_set(True)
            context.view_layer.objects.active = self._initial_active

        if context.area:
            context.area.tag_redraw()


class MESH_OT_AlignGeo(bpy.types.Operator):
    """Align selected geometry to extreme bound along axis"""
    bl_idname = "mesh.align_geo"
    bl_label = "Align Geometry"
    bl_options = {'REGISTER', 'UNDO'}

    mouse_2d = None
    mouse_3d = None
    
    @classmethod
    def poll(cls, context):
        if context.mode == 'EDIT_MESH' and context.active_object:
            return True
        return False

    def invoke(self, context, event):
        self.orientations = self.get_available_orientations(context)
        
        # Получаем текущую ориентацию
        current_name = context.scene.transform_orientation_slots[0].type
        
        # Находим её индекс
        try:
            self.orientation_idx = self.orientations.index(current_name)
        except ValueError:
            self.orientation_idx = 0

        current_name = self.orientations[self.orientation_idx]
        self.mx = dev_tools.get_orientation_matrix(context, current_name)
        self.space_name = current_name

        # 1. Получаем матрицу трансформации и центр выделения
        # self.mx, self.space_name = dev_tools.get_current_transform_matrix_and_info(context)

        obj = context.active_object
        bm = bmesh.from_edit_mesh(obj.data)
        selected_verts = [v for v in bm.verts if v.select]

        if not selected_verts:
            self.report({'WARNING'}, "No vertices selected")
            return {'CANCELLED'}
        
        # Для отрисовки в центре выделения
        # center_local = sum((v.co for v in selected_verts), Vector()) / len(selected_verts)
        # self.start_3d_location = obj.matrix_world @ center_local

        self.mouse_2d = Vector((event.mouse_region_x, event.mouse_region_y))
        self.mouse_3d = draw_3d.get_mouse_3d_pos_camera_offset(context, self.mouse_2d)  # Точка на расстоянии от near plane

        # 2. Первичный просчет осей по текущему положению мыши
        self.selected_axis_name, self.selected_direction = draw_3d.update_overlay_axes(
            context, self.mouse_3d, self.mx, self.mouse_2d
        )

        # 3. Настройка оверлея
        sign_str = "+" if self.selected_direction == 'POSITIVE' else "-"
        
        screen_overlay.update_modal_overlay(
            self.mouse_2d,
            header=f"Align: {sign_str}{self.selected_axis_name}",
            description=f"{self.space_name}",
        )

        screen_overlay.set_offset(30, 30)

        self._handle_2d = bpy.types.SpaceView3D.draw_handler_add(
            screen_overlay.draw, (), 'WINDOW', 'POST_PIXEL'
        )
        
        screen_overlay.show()

        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()

        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        context.area.tag_redraw()

        if event.type == 'MOUSEMOVE':
            self.mouse_2d_this_frame = Vector((event.mouse_region_x, event.mouse_region_y))

            # Обновление осей и выбор направления ОДНОЙ строчкой
            self.selected_axis_name, self.selected_direction = draw_3d.update_overlay_axes(
                context, self.mouse_3d, self.mx, self.mouse_2d_this_frame
            )

            sign_str = "+" if self.selected_direction == 'POSITIVE' else "-"
            
            screen_overlay.update_modal_overlay(
                self.mouse_2d,
                header=f"Align: {sign_str}{self.selected_axis_name}",
                description=f"{self.space_name}",
            )

        elif event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            if event.type == 'WHEELUPMOUSE':
                self.orientation_idx = (self.orientation_idx + 1) % len(self.orientations)
            else:
                self.orientation_idx = (self.orientation_idx - 1) % len(self.orientations)

            new_name = self.orientations[self.orientation_idx]
            self.mx = dev_tools.get_orientation_matrix(context, new_name)
            self.space_name = new_name

            self.selected_axis_name, self.selected_direction = draw_3d.update_overlay_axes(
                context, self.mouse_3d, self.mx, self.mouse_2d_this_frame
            )

            sign_str = "+" if self.selected_direction == 'POSITIVE' else "-"
            
            screen_overlay.update_modal_overlay(
                self.mouse_2d,
                header=f"Align: {sign_str}{self.selected_axis_name}",
                description=f"{self.space_name}",
            )

        elif event.type in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER'}:
            axis_idx, dir_sign, world_vec = dev_tools.get_selected_axis_data(
                self.mx, self.selected_axis_name, self.selected_direction
            )

            dev_tools.align_selected_geometry(context, world_vec)
            self.report({'INFO'}, f"Aligned to {self.space_name} {dir_sign:+d}{self.selected_axis_name}")

            self.finish(context)
            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            self.finish(context)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}
        

    def finish(self, context):
        draw_3d.clear()
        screen_overlay.clear()
        screen_overlay.hide()
        if hasattr(self, "_handle_2d") and self._handle_2d is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle_2d, 'WINDOW')
            self._handle_2d = None
        context.area.tag_redraw()

    def get_available_orientations(self, context):
        base_orientations = ['GLOBAL', 'LOCAL', 'CURSOR']
        
        # Попробовать разные варианты доступа к кастомным ориентациям
        all_orientations = base_orientations
        
        scene = context.scene
        slot = scene.transform_orientation_slots[0]
        if slot.custom_orientation:
            custom_name = slot.custom_orientation.name
            if custom_name not in base_orientations:
                all_orientations.append(custom_name)
        
        return all_orientations


class MESH_OT_Symmetrize(bpy.types.Operator):
    bl_idname = "mesh.mesh_symmetrize"
    bl_label = "Symmetrize Mesh"
    bl_description = "Description that shows in blender tooltips"
    bl_options = {"REGISTER", "UNDO"}

    # Свойства для всплывающего окна (Adjust Last Operation / Redo)
    remove_redundant_center: bpy.props.BoolProperty(
        name="Remove Center Edges",
        description="Dissolve flat edges along the symmetry axis",
        default=True
    )
    redundant_threshold: bpy.props.FloatProperty(
        name="Threshold",
        description="Merge threshold for vertices at center plane",
        default=0.0001,
        precision=5,
        min=0.0
    )

    mouse_2d = None
    mouse_3d = None

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def invoke(self, context, event):
        obj = context.active_object
        bm = bmesh.from_edit_mesh(obj.data)
        
        # Для отрисовки в центре выделения
        # center_local = sum((v.co for v in selected_verts), Vector()) / len(selected_verts)
        # self.start_3d_location = obj.matrix_world @ center_local

        self.mouse_2d = Vector((event.mouse_region_x, event.mouse_region_y))
        self.mouse_3d = draw_3d.get_mouse_3d_pos_camera_offset(context, self.mouse_2d)  # Точка на расстоянии от near plane
        self.mx = dev_tools.get_orientation_matrix(context, orientation_name='LOCAL')

        # 2. Первичный просчет осей по текущему положению мыши
        self.selected_axis_name, self.selected_direction = draw_3d.update_overlay_axes(
            context, self.mouse_3d, self.mx, self.mouse_2d
        )

        # 3. Настройка оверлея
        sign_str = "+" if self.selected_direction == 'POSITIVE' else "-"
        
        screen_overlay.update_modal_overlay(
            self.mouse_2d,
            header=f"Symmetrize: {sign_str}{self.selected_axis_name}",
        )

        screen_overlay.set_offset(30, 30)

        self._handle_2d = bpy.types.SpaceView3D.draw_handler_add(
            screen_overlay.draw, (), 'WINDOW', 'POST_PIXEL'
        )
        
        screen_overlay.show()

        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()

        return {'RUNNING_MODAL'}
    
    def execute(self, context):
        self.symmetrize_mesh(
                context.active_object,
                axis=self.selected_axis_name,
                direction=self.selected_direction,
                redundant_threshold=self.redundant_threshold,
                remove_redundant_center=self.remove_redundant_center,

            )

        self.finish(context)
        return {'FINISHED'}

    def modal(self, context, event):
        context.area.tag_redraw()

        if event.type == 'MOUSEMOVE':
            self.mouse_2d_this_frame = Vector((event.mouse_region_x, event.mouse_region_y))

            # Обновление осей и выбор направления ОДНОЙ строчкой
            self.selected_axis_name, self.selected_direction = draw_3d.update_overlay_axes(
                context, self.mouse_3d, self.mx, self.mouse_2d_this_frame
            )

            sign_str = "+" if self.selected_direction == 'POSITIVE' else "-"
            
            screen_overlay.update_modal_overlay(
                self.mouse_2d,
                header=f"Symmetrize: {sign_str}{self.selected_axis_name}",
            )

        elif event.type in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER'}:
            axis_idx, dir_sign, world_vec = dev_tools.get_selected_axis_data(
                self.mx, self.selected_axis_name, self.selected_direction
            )

            # Инвертируем выбранное направление
            inv_direction = 'NEGATIVE' if self.selected_direction == 'POSITIVE' else 'POSITIVE'
            self.axis_name = self.selected_axis_name
            self.selected_direction = inv_direction

            return self.execute(context)

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            self.finish(context)
            return {'CANCELLED'}
        
        return {'RUNNING_MODAL'}
    
    def finish(self, context):
        draw_3d.clear()
        screen_overlay.clear()
        screen_overlay.hide()
        if hasattr(self, "_handle_2d") and self._handle_2d is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle_2d, 'WINDOW')
            self._handle_2d = None
        context.area.tag_redraw()
    

    def symmetrize_mesh(self, obj, axis='X', direction='POSITIVE', redundant_threshold=0.05, 
                    remove_redundant_center=True, threshold=0.0001, 
                    uv_offset=Vector((1, 0)), debug=False):
        """
        Отражает меш в локальных координатах и обрабатывает UV/стыки.
        """
        axis_map = {'X': 0, 'Y': 1, 'Z': 2}
        axis_idx = axis_map.get(axis, 0)

        # 1. Запуск стандартного оператора симметрии
        # Формат direction для ops: 'POSITIVE_X', 'NEGATIVE_Y' и т.д.
        direction_full = f"{direction}_{axis}"
        
        bpy.ops.mesh.reveal()
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.symmetrize(direction=direction_full, threshold=threshold)
        bpy.ops.mesh.select_all(action='DESELECT')

        # 2. Быстрая работа с BMesh прямо в Edit Mode
        bm = bmesh.from_edit_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        # 3. Компактная сортировка вершин по сторонам
        original, mirror, center = [], [], []

        for v in bm.verts:
            val = v.co[axis_idx]
            
            # Сварка с центром при выходе за threshold
            if -threshold < val < threshold:
                v.co[axis_idx] = 0.0
                val = 0.0

            if val == 0.0:
                center.append(v.index)
            elif (direction == 'POSITIVE' and val > 0) or (direction == 'NEGATIVE' and val < 0):
                original.append(v.index)
            else:
                mirror.append(v.index)

        # 4. Смещение UV для зеркальных граней
        is_uv_offset = bool(obj.data.uv_layers and (uv_offset.x or uv_offset.y))
        if is_uv_offset and mirror:
            mirrored_set = set(mirror)
            mirrored_faces = [f for f in bm.faces if any(v.index in mirrored_set for v in f.verts)]
            
            uv_layer = bm.loops.layers.uv.verify()
            for f in mirrored_faces:
                for loop in f.loops:
                    loop[uv_layer].uv += uv_offset

        # 5. Растворение лишних центральных рёбер
        if remove_redundant_center and center:
            bm.normal_update()
            center_set = set(center)
            
            redundant_edges = [
                e for e in bm.edges 
                if e.is_manifold 
                and all(v.index in center_set for v in e.verts) 
                and round(e.calc_face_angle(), 5) <= redundant_threshold
            ]
            
            if redundant_edges:
                bmesh.ops.dissolve_edges(bm, edges=redundant_edges, use_verts=True, use_face_split=False)
                center = [] # Сбрасываем список центральных, так как геометрия изменилась

        # Запекаем изменения bmesh обратно в Edit Mesh
        bmesh.update_edit_mesh(obj.data)

        return {'original': original, 'mirror': mirror, 'center': center}


class MESH_OT_CustomBridge(bpy.types.Operator):
    bl_idname = "mesh.custom_bridge"
    bl_label = "Custom Bridge"
    bl_options = {"REGISTER", 'UNDO'}

    reverse: bpy.props.BoolProperty(
        name="Reverse",
        description="Reverse bridge",
        default=False
    )
    twist: bpy.props.IntProperty(
        name="Twist",
        default=0
    )

    # def draw(self, context):
    #     """
    #     Метод вызывается Blender'ом для Redo-панели (Adjust Last Operation).
    #     """
    #     layout = self.layout
        
    #     # Проперти action_mode сохраняется между кадрами Redo

    #     box = layout.box()
    #     box.label(text="Bridge Settings:")
    #     box.prop(self, "reverse")
    #     box.prop(self, "twist")

    def execute(self, context):
        obj = context.active_object
        bm = bmesh.from_edit_mesh(obj.data)

        bridge.make_bridge(context, obj, bm, self.reverse, self.twist)

        bmesh.update_edit_mesh(obj.data)
        return {'FINISHED'}


class MESH_OT_SmartEdge(bpy.types.Operator):
    bl_idname = "mesh.smart_edge"
    bl_label = "Smart Edge"
    bl_description = "Description that shows in blender tooltips"
    bl_options = {"REGISTER", 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def invoke(self, context, event):
        obj = context.active_object

        res = self.smart_edge_contextual_action(context)
        bmesh.update_edit_mesh(obj.data)
                
        return {'FINISHED'}
    
    def smart_edge_contextual_action(self, context):
        """
        Главная диспетчерская функция, воспроизводящая «умное» поведение 
        по кнопке 2 в зависимости от текущего режима выделения.
        """
        obj = context.active_object
        if not obj or obj.type != 'MESH' or obj.mode != 'EDIT':
            return False

        bm = bmesh.from_edit_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()

        mode = tuple(context.scene.tool_settings.mesh_select_mode)

        # 1. VERTEX MODE (True, False, False)
        if mode == (True, False, False):
            verts = [v for v in bm.verts if v.select]
            if len(verts) <= 1:
                bpy.ops.mesh.knife_tool('INVOKE_DEFAULT')
                return True
            else:
                if self.star_connect(bm):
                    bmesh.update_edit_mesh(obj.data)
                    return True
                try:
                    bpy.ops.mesh.vert_connect_path()
                    return True
                except RuntimeError:
                    if len(verts) == 2:
                        try:
                            bpy.ops.mesh.edge_face_add()
                            return True
                        except RuntimeError:
                            pass
                    return False

        # 2. EDGE MODE (False, True, False)
        elif mode == (False, True, False):
            edges = [e for e in bm.edges if e.select]
            
            # 0 эджей -> Интерактивный лупкат
            if len(edges) == 0:
                bpy.ops.mesh.loopcut_slide('INVOKE_DEFAULT')
                return True

            # Эджи на границе меша (бордеры) -> Заполнение (Grid Fill / Bridge)
            if all(not e.is_manifold for e in edges):
                try:
                    bpy.ops.mesh.fill_grid()
                except RuntimeError:
                    try:
                        bpy.ops.mesh.bridge_edge_loops()
                    except RuntimeError:
                        return False
                return True

            # ВНУТРЕННИЕ ЭДЖИ: Разделяем Bridge и Rotate через количество лупов
            loops = bridge.get_input(bm, edges)

            # Если есть 2+ раздельные цепочки/эджа -> соединяем внутренними ребрами (Bridge)
            if len(loops) >= 2:
                try:
                    return bpy.ops.mesh.custom_bridge('INVOKE_DEFAULT')
                except Exception:
                    pass

            # Если это 1 эдж или 1 связная цепочка (до 3 эджей) -> вращаем ребро
            if len(edges) < 4:
                try:
                    bpy.ops.mesh.edge_rotate(use_ccw=False)
                    return True
                except RuntimeError:
                    return False

            # Выделено много эджей (>= 4) -> выделяем внутренний полигон
            elif len(edges) >= 4:
                bpy.ops.mesh.loop_to_region()
                bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='FACE')
                return True
        
        elif mode == (False, False, True): # FACE MODE
            bpy.ops.mesh.region_to_loop()

        return False
    
    def star_connect(self, bm):
        """
        Соединяет активную вершину со всеми остальными выделенными в пределах одной грани.
        """
        verts = [v for v in bm.verts if v.select]
        history = list(bm.select_history)
        last = history[-1] if history and isinstance(history[-1], bmesh.types.BMVert) else None

        if not last or len(verts) < 3:
            return False

        faces = [f for v in verts for f in v.link_faces]
        common = next((f for f in faces if all(v in f.verts for v in verts)), None)

        if common:
            verts.remove(last)
            for v in verts:
                bmesh.ops.connect_verts(bm, verts=[last, v])
            return True

        return False


class VIEW3D_OT_Focus(bpy.types.Operator):
    """Deep Isolation mode / Step Back"""
    bl_idname = "view3d.focus"
    bl_label = "Focus / Unfocus"
    bl_options = {'REGISTER', 'UNDO'}

    # 1. Объявляем свойства оператора (появятся в нижнем левом окне)
    exclude_modifiers: bpy.props.BoolProperty(
        name="Hide Mirror & Array",
        description="Hide Mirror and Array modifiers when entering Focus mode",
        default=True
    ) # type: ignore

    # 2. Отрисовка интерфейса нижнего левого окна
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column(align=True)
        col.prop(self, "exclude_modifiers")

    def execute(self, context):
        view = context.space_data
        if view.type != 'VIEW_3D':
            self.report({'WARNING'}, "3D Viewport only")
            return {'CANCELLED'}

        props = context.scene.danmat_tools_props
        history = props.focus_history

        selected_objs = context.selected_objects
        visible_objs = context.visible_objects

        # 1. Шаг углубления в изоляцию объектов
        if selected_objs and (not view.local_view or visible_objs != selected_objs):
            if not view.local_view and history:
                main_tools.clear_focus_history(history)
            
            # Передаем значение свойства self.exclude_modifiers из этого оператора
            main_tools.focus_step(context, view, selected_objs, history, self.exclude_modifiers)

        # 2. Шаг назад из изоляции объектов
        elif view.local_view:
            if history:
                main_tools.unfocus_step(context, view, history)
            else:
                bpy.ops.view3d.localview(frame_selected=False)

        return {'FINISHED'}


class VIEW3D_OT_MainPieMenu(bpy.types.Operator):
    bl_idname = "view3d.main_pie_menu"
    bl_label = "Danmat Tools Pie Menu"
    bl_description = "Description that shows in blender tooltips"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT' and context.active_object:
            return True
        return False

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
    OBJECT_OT_DebugModifiers,
    OBJECT_OT_RenameSimple,
    OBJECT_OT_BakeGroupSelect,
    VIEW3D_OT_OverlayManageUtils,
    MESH_OT_AlignGeo,
    MESH_OT_Symmetrize,
    MESH_OT_CustomBridge,
    MESH_OT_SmartEdge,
    VIEW3D_OT_Focus,
    VIEW3D_OT_MainPieMenu,
    # VIEW3D_OT_ToggleFlippedFaces,
]

def register():
    for cls in classes_to_register:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)
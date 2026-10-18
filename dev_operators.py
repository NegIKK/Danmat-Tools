from multiprocessing import context
import operator
from unittest import result
import bpy
import bmesh
import mathutils

from bpy_extras import view3d_utils
from mathutils import Vector, Matrix

from . import main_tools
from . import dev_tools
from .modules import bridge
from . import screen_overlay
from . import draw_3d
from . import overlay_3d

from . import mesh_set_length_core as core

from bpy.props import EnumProperty, BoolProperty



class OBJECT_OT_testOperator1(bpy.types.Operator):
    bl_idname = "object.test1"
    bl_label = "test1"
    bl_description = "Description that shows in blender tooltips"
    bl_options = {"REGISTER", 'UNDO'}

    def execute(self, context):
        overlay_3d.register()

        obj = context.active_object

        if obj is None or obj.type != 'MESH':
            self.report({'WARNING'}, "Active object is not a mesh")
            return {'CANCELLED'}

        me = obj.data

        # Вершины: первые 10.
        if len(me.vertices):
            overlay_3d.draw_vertex(
                obj,
                list(range(min(10, len(me.vertices)))),
                color=(1.0, 0.2, 0.0, 1.0),
                size=0.05,
                fade=0.8,
                appear=0.05,
                overlay=True,
            )

        # Ребра: первые 5.
        if len(me.edges):
            overlay_3d.draw_edge(
                obj,
                list(range(min(5, len(me.edges)))),
                color=(0.0, 1.0, 0.2, 1.0),
                width=4.0,
                fade=0.8,
                appear=0.05,
                overlay=True,
            )

        # Грани: первые 3.
        if len(me.polygons):
            overlay_3d.draw_face(
                obj,
                list(range(min(3, len(me.polygons)))),
                color=(0.2, 0.5, 1.0, 0.35),
                width=2.0,
                fade=0.8,
                appear=0.05,
                overlay=False,
            )

        # Статичная линия с учетом глубины.
        overlay_3d.draw_line(
            Vector((0.0, 0.0, 0.0)),
            Vector((2.0, 0.0, 0.0)),
            color=(1.0, 1.0, 0.0, 1.0),
            width=3.0,
            overlay=False,
        )

        # Статичная линия поверх всего.
        overlay_3d.draw_line(
            Vector((0.0, 0.0, 0.0)),
            Vector((0.0, 2.0, 0.0)),
            color=(1.0, 0.0, 1.0, 1.0),
            width=3.0,
            overlay=True,
        )

        return {'FINISHED'}
    

    
class MESH_OT_align_editmesh(bpy.types.Operator):
    bl_idname = "mesh.align_editmesh"
    bl_label = "Align Edit Mesh"
    bl_options = {'REGISTER', 'UNDO'}

    mode: EnumProperty(
        name="Mode",
        items=[('VIEW', "View", ""), ('AXIS', "Axis", "")],
        default="VIEW"
    )
    type: EnumProperty(
        name="Type",
        items=[
            ('MIN', "Min", ""), ('MAX', "Max", ""),
            ('AVERAGE', "Average", ""), ('ZERO', "Zero", ""),
            ('CURSOR', "Cursor", "")
        ],
        default="MIN"
    )
    axis: EnumProperty(
        name="Axis",
        items=[('X', "X", ""), ('Y', "Y", ""), ('Z', "Z", "")],
        default="X"
    )
    direction: EnumProperty(
        name="Direction",
        items=[
            ('LEFT', "Left", ""), ('RIGHT', "Right", ""),
            ('TOP', "Top", ""), ('BOTTOM', "Bottom", ""),
            ('HORIZONTAL', "Horizontal", ""), ('VERTICAL', "Vertical", "")
        ],
        default="LEFT"
    )
    space: EnumProperty(
        name="Space",
        items=[('LOCAL', "Local", ""), ('WORLD', "World", ""), ('CURSOR', "Cursor", "")],
        default="LOCAL"
    )
    align_each: BoolProperty(name="Align Each Island", default=False)
    draw_each: BoolProperty(default=False)

    @classmethod
    def poll(cls, context):
        if context.mode == "EDIT_MESH" and context.active_object:
            bm = bmesh.from_edit_mesh(context.active_object.data)
            return any(v.select for v in bm.verts)
        return False

    def invoke(self, context, event):
        self.space = 'WORLD' if event.alt else 'CURSOR' if event.ctrl else 'LOCAL'

        if self.mode == 'VIEW':
            mx = main_tools.get_matrix_for_space(context, self.space)
            axis_right, axis_up, flip_right, flip_up = main_tools.get_right_and_up_axes(context, mx=mx)

            if self.direction in ['LEFT', 'RIGHT', 'TOP', 'BOTTOM']:
                axis_idx = axis_right if self.direction in ['RIGHT', 'LEFT'] else axis_up

                if self.direction == 'RIGHT':
                    self.type = 'MIN' if flip_right else 'MAX'
                elif self.direction == 'LEFT':
                    self.type = 'MAX' if flip_right else 'MIN'
                elif self.direction == 'TOP':
                    self.type = 'MIN' if flip_up else 'MAX'
                elif self.direction == 'BOTTOM':
                    self.type = 'MAX' if flip_up else 'MIN'

            elif self.direction in ['HORIZONTAL', 'VERTICAL']:
                axis_idx = axis_right if self.direction == "HORIZONTAL" else axis_up

            self.axis = 'X' if axis_idx == 0 else 'Y' if axis_idx == 1 else 'Z'

        return self.execute(context)

    def execute(self, context):
        success, has_multiple = main_tools.align_editmesh_geometry(
            context, 
            align_type=self.type, 
            axis_name=self.axis, 
            space=self.space, 
            align_each=self.align_each
        )
        self.draw_each = has_multiple
        return {'FINISHED'} if success else {'CANCELLED'}

class VIEW3D_OT_debug_line_dir(bpy.types.Operator):
    bl_idname = "mesh.debug_line_dir"
    bl_label = "Debug Line Direction"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.area and context.area.type == 'VIEW_3D'

    def invoke(self, context, event):
        # 1. Перед началом работы очищаем реестр отрисовки
        draw_3d.clear()

        # 2. Переводим 2D-координату мыши в 3D-точку на глубине 3D-курсора
        region = context.region
        rv3d = context.space_data.region_3d
        mouse_pos_2d = (event.mouse_region_x, event.mouse_region_y)
        depth_location = context.scene.cursor.location

        self.start_3d_location = view3d_utils.region_2d_to_location_3d(
            region, rv3d, mouse_pos_2d, depth_location
        )

        if self.start_3d_location is None:
            self.start_3d_location = mathutils.Vector((0.0, 0.0, 0.0))

        # 3. Добавляем начальную статичную графику (например, маленькие оси X, Y, Z в точке старта)
        # self._add_axes_to_draw(self.start_3d_location)

        # 4. Переводим оператор в модальный режим
        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def _add_axes_to_draw(self, origin, length=0.3):
        """Вспомогательный метод: добавляет 3 линии осей координат в реестр"""
        draw_3d.add_line(origin, origin + mathutils.Vector((length, 0, 0)), color=(1, 0, 0, 1), width=1.0) # X - Красный
        draw_3d.add_line(origin, origin + mathutils.Vector((0, length, 0)), color=(0, 1, 0, 1), width=1.0) # Y - Зеленый
        draw_3d.add_line(origin, origin + mathutils.Vector((0, 0, length)), color=(0, 0, 1, 1), width=1.0) # Z - Синий

    def modal(self, context, event):
        # При каждом событии запрашиваем перерисовку вьюпорта
        context.area.tag_redraw()

        if event.type == 'MOUSEMOVE':
            # 1. Очищаем старый кадр
            draw_3d.clear()

            # 2. Перерисовываем базовые оси в стартовой точке
            # self._add_axes_to_draw(self.start_3d_location)

            # 3. Считаем текущую 3D-точку под курсором мыши
            region = context.region
            rv3d = context.space_data.region_3d
            mouse_pos_2d = (event.mouse_region_x, event.mouse_region_y)

            current_3d = view3d_utils.region_2d_to_location_3d(
                region, rv3d, mouse_pos_2d, self.start_3d_location
            )

            # 4. Если проекция успешна — рисуем жёлтую линию от старта к мыши
            if current_3d:
                draw_3d.add_line(
                    start=self.start_3d_location,
                    end=current_3d,
                    color=(1.0, 1.0, 0.0, 1.0),  # Жёлтая
                    width=2.5                     # Потолще, чтобы выделялась
                )

        # Завершение по ЛКМ или Enter
        elif event.type in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER'}:
            draw_3d.clear()
            context.area.tag_redraw()
            return {'FINISHED'}

        # Отмена по ПКМ или ESC
        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            draw_3d.clear()
            context.area.tag_redraw()
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}
    
class VIEW3D_OT_debug_choose_axis(bpy.types.Operator):
    bl_idname = "mesh.debug_choose_axis"
    bl_label = "Debug Choose Axis"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.area and context.area.type == 'VIEW_3D'

    def invoke(self, context, event):
        draw_3d.clear()

        # 1. Получаем матрицу и понятное имя текущей Transform Orientation
        self.mx, self.space_name = dev_tools.get_current_transform_matrix_and_info(context)

        # 2. Определяем опорную точку
        self.active = context.active_object
        if self.active:
            self.origin_3d = self.active.location.copy()
        else:
            self.origin_3d = context.scene.cursor.location.copy()

        # 3. Точка клика для отрисовки осей
        region = context.region
        rv3d = context.space_data.region_3d
        mouse_pos_2d = Vector((event.mouse_region_x, event.mouse_region_y))

        start_loc = view3d_utils.region_2d_to_location_3d(
            region, rv3d, mouse_pos_2d, self.origin_3d
        )
        self.start_3d_location = start_loc if start_loc is not None else self.origin_3d.copy()

        # Инициализация свойств выбранной оси (по умолчанию +X)
        self.selected_axis_name = 'X'
        self.selected_direction = 'POSITIVE'

        self.use_x = True
        self.use_y = False
        self.use_z = False
        self.flip_x = False
        self.flip_y = False
        self.flip_z = False

        self._add_axes_to_draw(self.start_3d_location)

        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def _add_axes_to_draw(self, origin, base_length=0.4, active_axis_name='X', active_dir='POSITIVE'):
        axis_map = {'X': 0, 'Y': 1, 'Z': 2}
        active_idx = axis_map.get(active_axis_name, 0)
        dir_sign = 1 if active_dir == 'POSITIVE' else -1

        quat = self.mx.to_quaternion()

        axes_data = [
            (0, quat @ Vector((1, 0, 0)), (1.0, 0.2, 0.2, 1.0)),  # X
            (1, quat @ Vector((0, 1, 0)), (0.2, 1.0, 0.2, 1.0)),  # Y
            (2, quat @ Vector((0, 0, 1)), (0.2, 0.5, 1.0, 1.0)),  # Z
        ]

        for axis_idx, axis_vec, color in axes_data:
            is_active = (active_idx == axis_idx)

            # Положительная полуось
            is_pos_active = is_active and (dir_sign > 0)
            pos_len = base_length * (2.0 if is_pos_active else 1.0)
            pos_width = 3.5 if is_pos_active else 1.0
            draw_3d.add_line(origin, origin + axis_vec * pos_len, color=color, width=pos_width)

            # Отрицательная полуось
            is_neg_active = is_active and (dir_sign < 0)
            neg_len = base_length * (2.0 if is_neg_active else 1.0)
            neg_width = 3.5 if is_neg_active else 1.0
            neg_color = (color[0], color[1], color[2], 0.8 if is_active else 0.4)
            draw_3d.add_line(origin, origin - axis_vec * neg_len, color=neg_color, width=neg_width)

    def modal(self, context, event):
        context.area.tag_redraw()

        if event.type == 'MOUSEMOVE':
            draw_3d.clear()

            mouse_2d = Vector((event.mouse_region_x, event.mouse_region_y))

            axis_name, direction = dev_tools.get_closest_axis_2d(
                context,
                self.start_3d_location,
                self.mx,
                mouse_2d
            )

            # Сохраняем текущий выбор
            self.selected_axis_name = axis_name
            self.selected_direction = direction

            self.use_x = (axis_name == 'X')
            self.use_y = (axis_name == 'Y')
            self.use_z = (axis_name == 'Z')

            self.flip_x = (axis_name == 'X' and direction == 'POSITIVE')
            self.flip_y = (axis_name == 'Y' and direction == 'POSITIVE')
            self.flip_z = (axis_name == 'Z' and direction == 'POSITIVE')

            self._add_axes_to_draw(
                self.start_3d_location, 
                active_axis_name=axis_name, 
                active_dir=direction
            )

        elif event.type in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER'}:
            draw_3d.clear()
            context.area.tag_redraw()

            # Получаем все математические / геометрические данные
            axis_idx, dir_sign, world_vec = dev_tools.get_selected_axis_data(
                self.mx, 
                self.selected_axis_name, 
                self.selected_direction
            )

            # --- ТЕХНИЧЕСКИЙ ВЫХОД ДЛЯ ДАЛЬНЕЙШЕЙ РАБОТЫ С МЕШЕМ ---
            self.result_data = {
                'space_matrix': self.mx,                     # Matrix 4x4 (ориентация)
                'origin_3d': self.start_3d_location.copy(),  # Vector3 (точка плоскости/центр)
                'axis_index': axis_idx,                      # 0, 1 или 2 (X, Y, Z)
                'direction_sign': dir_sign,                  # 1 или -1
                'world_vector': world_vec,                   # Vector3 (нормаль или вектор отражения в World)
                'space_name': self.space_name                # str ("Global", "Local", "Custom" и т.д.)
            }

            # Отладочный вывод
            self.report({'INFO'}, f"{self.result_data['space_name']} {self.result_data['direction_sign']}{self.selected_axis_name}")

            # print(f"[Choose Axis Result]:")
            # print(f"  Axis Index: {self.result_data['axis_index']} ({self.selected_axis_name})")
            # print(f"  Direction Sign: {self.result_data['direction_sign']}")
            # print(f"  World Direction Vector: {self.result_data['world_vector']}")
            # print(f"  Origin 3D: {self.result_data['origin_3d']}")

            # Пример: Допустим, мы хотим применить Bmesh Bisect или плоскость симметрии:
            # plane_co = self.result_data['origin_3d']
            # plane_no = self.result_data['world_vector']

            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            draw_3d.clear()
            context.area.tag_redraw()
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}
    
class VIEW3D_OT_debug_screen_to_world_dir(bpy.types.Operator):
    bl_idname = "mesh.debug_screen_to_world_dir"
    bl_label = "debug_screen_to_world_dir"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.area and context.area.type == 'VIEW_3D'

    def invoke(self, context, event):
        draw_3d.clear()

        region = context.region
        rv3d = context.space_data.region_3d
        mouse_pos_2d = (event.mouse_region_x, event.mouse_region_y)
        depth_location = context.scene.cursor.location

        self.start_3d_location = view3d_utils.region_2d_to_location_3d(
            region, rv3d, mouse_pos_2d, depth_location
        )

        if self.start_3d_location is None:
            self.start_3d_location = Vector((0.0, 0.0, 0.0))

        # Запоминаем исходные параметры оси относительно экрана при старте
        # Если выбран объект — можно передать context.active_object.matrix_world
        matrix = context.active_object.matrix_world if context.active_object else mathutils.Matrix.Identity(4)
        self.right_idx, self.up_idx, self.flip_right, self.flip_up = main_tools.get_right_and_up_axes(context, matrix)

        self._add_axes_to_draw(self.start_3d_location)

        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def _add_axes_to_draw(self, origin, base_length=0.4, active_axis_idx=None, active_dir=1):
        axes_data = [
            (0, Vector((1, 0, 0)), (1.0, 0.2, 0.2, 1.0)), # X
            (1, Vector((0, 1, 0)), (0.2, 1.0, 0.2, 1.0)), # Y
            (2, Vector((0, 0, 1)), (0.2, 0.5, 1.0, 1.0)), # Z
        ]

        for axis_idx, axis_vec, color in axes_data:
            # Положительная полуось
            pos_len = base_length * (2.0 if (active_axis_idx == axis_idx and active_dir > 0) else 1.0)
            pos_width = 3.5 if (active_axis_idx == axis_idx and active_dir > 0) else 1.0
            draw_3d.add_line(origin, origin + axis_vec * pos_len, color=color, width=pos_width)

            # Отрицательная полуось
            neg_len = base_length * (2.0 if (active_axis_idx == axis_idx and active_dir < 0) else 1.0)
            neg_width = 3.5 if (active_axis_idx == axis_idx and active_dir < 0) else 1.0
            neg_color = (color[0], color[1], color[2], 0.4 if active_axis_idx != axis_idx else 0.8)
            draw_3d.add_line(origin, origin - axis_vec * neg_len, color=neg_color, width=neg_width)

    def modal(self, context, event):
        context.area.tag_redraw()

        if event.type == 'MOUSEMOVE':
            draw_3d.clear()

            region = context.region
            rv3d = context.space_data.region_3d
            mouse_pos_2d = (event.mouse_region_x, event.mouse_region_y)

            current_3d = view3d_utils.region_2d_to_location_3d(
                region, rv3d, mouse_pos_2d, self.start_3d_location
            )

            if current_3d:
                delta = current_3d - self.start_3d_location

                if delta.length > 0.001:
                    # 1. Получаем движение мыши в View Space (экране)
                    view_rotation = rv3d.view_rotation
                    # Переводим дельта-вектор мира в координаты камеры
                    view_delta = view_rotation.inverted() @ delta

                    # 2. Смотрим, куда больше сместилась мышь: по горизонтали экрана (X) или вертикали (Y)
                    if abs(view_delta.x) > abs(view_delta.y):
                        # Экранный X -> используем найденную ось Right
                        active_axis_idx = self.right_idx
                        # Учитываем инверсию направления (flip)
                        active_dir = -1 if (view_delta.x < 0) ^ self.flip_right else 1
                    else:
                        # Экранный Y -> используем найденную ось Up
                        active_axis_idx = self.up_idx
                        active_dir = -1 if (view_delta.y < 0) ^ self.flip_up else 1

                    self._add_axes_to_draw(
                        self.start_3d_location,
                        base_length=0.4,
                        active_axis_idx=active_axis_idx,
                        active_dir=active_dir
                    )

                    draw_3d.add_line(
                        start=self.start_3d_location,
                        end=current_3d,
                        color=(1.0, 1.0, 0.0, 0.8),
                        width=2.0
                    )
                else:
                    self._add_axes_to_draw(self.start_3d_location)

        elif event.type in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER'}:
            draw_3d.clear()
            context.area.tag_redraw()
            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            draw_3d.clear()
            context.area.tag_redraw()
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}


MODIFIER_NAME = "Interactive_Symmetry"

class VIEW3D_OT_SymmetryByAxisModal(bpy.types.Operator):
    """Interactive Bisect & Mirror along flicked axis"""
    bl_idname = "object.symmetry_by_axis_modal"
    bl_label = "Mirror Object"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.selected_objects

    def invoke(self, context, event):
        draw_3d.clear()

        # 1. Ориентация и центр активного объекта
        self.mx, self.space_name = dev_tools.get_current_transform_matrix_and_info(context)
        obj = context.active_object or context.selected_objects[0]
        self.start_3d_location = obj.location.copy()

        # 2. Создаем/находим модификатор Mirror на выделенных объектах
        self._created_modifiers = {}
        for o in context.selected_objects:
            if o.type == 'MESH':
                mod = o.modifiers.get(MODIFIER_NAME) or o.modifiers.new(name=MODIFIER_NAME, type='MIRROR')
                mod.show_expanded = False
                self._created_modifiers[o] = mod

        # 3. Вычисляем начальную ось по мыши
        mouse_2d = Vector((event.mouse_region_x, event.mouse_region_y))
        self.selected_axis_name, self.selected_direction = draw_3d.update_overlay_axes(
            context, self.start_3d_location, self.mx, mouse_2d
        )

        self._apply_symmetry_modifier()

        # 4. Настройка оверлея
        sign_str = "+" if self.selected_direction == 'POSITIVE' else "-"
        screen_overlay.set_position(event.mouse_region_x, event.mouse_region_y)
        screen_overlay.set_header(f"Symmetry: {sign_str}{self.selected_axis_name}")
        screen_overlay.set_lines([f"Space: {self.space_name}"])
        screen_overlay.show()

        self._handle_2d = bpy.types.SpaceView3D.draw_handler_add(
            screen_overlay.draw, (), 'WINDOW', 'POST_PIXEL'
        )

        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def _apply_symmetry_modifier(self):
        """Включает нужную ось, Bisect и Flip в модификаторе Mirror"""
        axis_idx_map = {'X': 0, 'Y': 1, 'Z': 2}
        idx = axis_idx_map[self.selected_axis_name]
        is_flip = (self.selected_direction == 'NEGATIVE')

        for obj, mod in self._created_modifiers.items():
            use_axes = [False, False, False]
            use_bisect = [False, False, False]
            use_flip = [False, False, False]

            use_axes[idx] = True
            use_bisect[idx] = True
            use_flip[idx] = is_flip

            mod.use_axis = use_axes
            mod.use_bisect_axis = use_bisect
            mod.use_bisect_flip_axis = use_flip

    def modal(self, context, event):
        context.area.tag_redraw()

        if event.type == 'MOUSEMOVE':
            mouse_2d = Vector((event.mouse_region_x, event.mouse_region_y))

            # Пересчет ближайшей оси и отрисовка через единую функцию
            self.selected_axis_name, self.selected_direction = draw_3d.update_overlay_axes(
                context, self.start_3d_location, self.mx, mouse_2d
            )

            self._apply_symmetry_modifier()

            sign_str = "+" if self.selected_direction == 'POSITIVE' else "-"
            screen_overlay.set_position(event.mouse_region_x, event.mouse_region_y)
            screen_overlay.set_header(f"Symmetry: {sign_str}{self.selected_axis_name}")

        elif event.type in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER'}:
            self._finish(context, cancelled=False)
            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            self._finish(context, cancelled=True)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def _finish(self, context, cancelled=False):
        draw_3d.clear()
        screen_overlay.clear()
        screen_overlay.hide()

        if hasattr(self, "_handle_2d") and self._handle_2d is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle_2d, 'WINDOW')
            self._handle_2d = None

        if cancelled:
            # При отмене убираем временные модификаторы
            for obj, mod in self._created_modifiers.items():
                obj.modifiers.remove(mod)

        context.area.tag_redraw()

class MESH_OT_SetLength(bpy.types.Operator):
    """Set distance between two points.
    Moves single vertex if no selection or whole selected geometry."""

    bl_idname = "mesh.set_length"
    bl_label = "Set Length"
    bl_description = "Set exact distance between two vertices/points"
    bl_options = {"REGISTER", "UNDO"}

    # Fallback, если внешней property нет.
    LIVE_PREVIEW = False

    # Строгий vertex snap в пикселях.
    SNAP_PIXELS = 24.0

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (
            context.mode == "EDIT_MESH"
            and obj is not None
            and obj.type == "MESH"
        )

    def invoke(self, context, event):
        if not core.init(self, context, event, self.report):
            return {"CANCELLED"}

        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        try:
            core.begin_frame(self, context, event)

            # -------------------------------------------------------------
            # GLOBAL CANCEL
            # -------------------------------------------------------------
            if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
                core.finish(self, context, cancel=True)
                return {"CANCELLED"}

            # -------------------------------------------------------------
            # STATE 0: PICK ANCHOR
            # -------------------------------------------------------------
            if self.state == 0:
                core.handle_state0(self, context, event)

            # -------------------------------------------------------------
            # STATE 1: PICK TARGET
            # -------------------------------------------------------------
            elif self.state == 1:
                core.handle_state1(self, context, event)

            # -------------------------------------------------------------
            # STATE 2: INPUT DISTANCE
            # -------------------------------------------------------------
            elif self.state == 2:
                # =========================================================
                # HOTKEYS
                # =========================================================

                # C — center / anchor mode
                if event.type == "C" and event.value == "PRESS":
                    core.toggle_center_mode(self, context)

                # A — cycle axis: FREE -> X -> Y -> Z -> FREE
                elif event.type == "A" and event.value == "PRESS":
                    core.cycle_axis_mode(self, context)

                # F — flip direction, сохраняет введённую длину
                elif event.type == "F" and event.value == "PRESS":
                    core.flip_direction(self, context)

                # Колесо — шаг
                elif event.type == "WHEELUPMOUSE" and event.value == "PRESS":
                    core.nudge_distance(self, context, +1.0, event.shift)

                elif event.type == "WHEELDOWNMOUSE" and event.value == "PRESS":
                    core.nudge_distance(self, context, -1.0, event.shift)

                # Подтверждение
                elif event.type in {"RET", "NUMPAD_ENTER", "LEFTMOUSE"} and event.value == "PRESS":
                    core.finish(self, context, cancel=False)
                    return {"FINISHED"}

                # ---------------------------------------------------------
                # TEXT INPUT
                # ---------------------------------------------------------
                else:
                    char = core.get_input_char(event)

                    if char is not None:
                        if self.reset_input_on_key:
                            self.input_string = char
                            self.reset_input_on_key = False
                        else:
                            self.input_string += char

                        core.parse_input_string(self, context)

                    # BACKSPACE
                    elif event.type == "BACK_SPACE" and event.value in {"PRESS", "REPEAT"}:
                        changed = False

                        if self.reset_input_on_key:
                            self.input_string = ""
                            self.reset_input_on_key = False
                            changed = True
                        elif len(self.input_string) > 0:
                            self.input_string = self.input_string[:-1]
                            changed = True

                        if changed:
                            core.parse_input_string(self, context)

                    # DELETE
                    elif event.type == "DEL" and event.value in {"PRESS", "REPEAT"}:
                        self.input_string = ""
                        self.reset_input_on_key = False
                        core.parse_input_string(self, context)

            # -------------------------------------------------------------
            # PREVIEW / HUD
            # -------------------------------------------------------------
            core.draw_preview(self, context)
            core.update_hud(self, context)

            return {"RUNNING_MODAL"}

        except Exception as exc:
            self.report({"ERROR"}, f"Set Length error: {exc}")

            try:
                core.finish(self, context, cancel=True)
            except Exception:
                pass

            return {"CANCELLED"}
    


classes_to_register = [
    OBJECT_OT_testOperator1,
    # MESH_OT_CustomBridge,
    # MESH_OT_SmartEdge,
    # VIEW3D_OT_Focus,
    MESH_OT_align_editmesh,
    # MESH_OT_align_geo,
    VIEW3D_OT_SymmetryByAxisModal,
    MESH_OT_SetLength,
    # MESH_OT_Symmetrize,
    # VIEW3D_OT_3DOverlay,
    
    VIEW3D_OT_debug_line_dir,
    VIEW3D_OT_debug_screen_to_world_dir,
    VIEW3D_OT_debug_choose_axis,
]

def register():
    for cls in classes_to_register:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)

# class MESH_OT_SetLength(bpy.types.Operator):
#     """Interactive Bisect & Mirror along flicked axis"""
#     bl_idname = "mesh.set_length"
#     bl_label = "Set Length"
#     bl_options = {'REGISTER', 'UNDO'}

#     @classmethod
#     def poll(cls, context):
#         return context.mode == 'EDIT_MESH' and context.selected_objects
    
#     def invoke(self, context, event):
#         self.reset_input_on_key = False

#         self.obj = context.active_object
#         self.bm = bmesh.from_edit_mesh(self.obj.data)
#         self.bm.verts.ensure_lookup_table()
#         self.matrix_world = self.obj.matrix_world

#         self.use_center_mode = False   # Переключатель режима (C)
#         self.center_co_world = Vector() # Фиксированная середина отрезка

#         scene_unit = context.scene.unit_settings.length_unit

#         unit_labels = {
#             'MILLIMETERS': 'mm',
#             'CENTIMETERS': 'cm',
#             'METERS': 'm',
#             'KILOMETERS': 'km',
#             'INCHES': 'in',
#             'FEET': 'ft',
#         }

#         self.unit = unit_labels.get(scene_unit, 'm')

#         # Состояние оператора: 0 = ждем Vert 1, 1 = ждем Vert 2, 2 = ввод значения
#         self.state = 0 
        
#         self.vert_anchor = None # BMVert 1
#         self.vert_target = None # BMVert 2
        
#         self.anchor_co_world = Vector()
#         self.target_co_world = Vector()
#         self.hover_co_world = Vector()
        
#         self.distance = 0.0
#         self.input_string = ""
#         self.mouse_2d = Vector((event.mouse_region_x, event.mouse_region_y))

#         # Включаем текстовый оверлей
#         screen_overlay.clear()
#         screen_overlay.update_modal_overlay(
#             mouse_2d=self.mouse_2d,
#             header="DISTANCE DRIVE",
#             description="LMB: Select vertex" \
#                         "RMB/ESC: Cancel",
#             lines=["Step 1: Pick Base Point (Anchor)"]
#         )

#         # 2. Регистрируем 2D-хэндлер отрисовки
#         self._handle_2d = bpy.types.SpaceView3D.draw_handler_add(
#             screen_overlay.draw, (), 'WINDOW', 'POST_PIXEL'
#         )

#         # 3. Активируем отображение
#         screen_overlay.show()

#         context.window_manager.modal_handler_add(self)
#         context.area.tag_redraw()

#         return {'RUNNING_MODAL'}
    
#     def modal(self, context, event):
#         context.area.tag_redraw()
#         self.mouse_2d = Vector((event.mouse_region_x, event.mouse_region_y))

#         # Очищаем 3D-реестр перед обновлением кадра
#         draw_3d.clear()

#         # --- ОТМЕНА (ESC / RMB) ---
#         if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
#             self.finish(context)
#             return {'CANCELLED'}

#         # --- STATE 0: ВЫБОР ANCHOR (Любая точка сцены / модификаторов) ---
#         if self.state == 0:
#             world_co, bm_v = self.find_snap_target(context, event)
#             if world_co:
#                 self.hover_co_world = world_co
#                 draw_3d.add_point(self.hover_co_world, color=(0.2, 1.0, 0.4, 1.0), size=8.0)

#             screen_overlay.update_modal_overlay(
#                 mouse_2d=self.mouse_2d,
#                 header="DISTANCE DRIVE",
#                 description="Step 1: Pick Base Point (Anchor - Any Object/Modifier)",
#                 lines=["LMB: Select vertex", "RMB/ESC: Cancel"]
#             )

#             if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
#                 if world_co:
#                     self.anchor_co_world = world_co.copy()
#                     # vert_anchor теперь может быть None, если точка взята с другого объекта
#                     self.vert_anchor = bm_v 
#                     self.state = 1
#                 return {'RUNNING_MODAL'}

#         # --- STATE 1: ВЫБОР TARGET (Только вершина редактируемого объекта) ---
#         elif self.state == 1:
#             draw_3d.add_point(self.anchor_co_world, color=(0.0, 1.0, 0.5, 1.0), size=8.0)

#             world_co, bm_v = self.find_snap_target(context, event)
#             # Внимание: целевая вершина обязана принадлежать текущему BMesh!
#             if bm_v:
#                 self.hover_co_world = world_co
#                 draw_3d.add_point(self.hover_co_world, color=(1.0, 0.8, 0.0, 1.0), size=8.0)
#                 draw_3d.add_line(self.anchor_co_world, self.hover_co_world, color=(1.0, 0.8, 0.0, 0.8), width=2.0)

#             screen_overlay.update_modal_overlay(
#                 mouse_2d=self.mouse_2d,
#                 header="DISTANCE DRIVE",
#                 description="Step 2: Pick Target Vertex to Move (Active Object)",
#                 lines=["LMB: Select vertex", "RMB/ESC: Cancel"]
#             )

#             if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
#                 if bm_v and bm_v != self.vert_anchor:
#                     self.vert_target = bm_v
#                     self.target_co_world = world_co.copy()

#                     # РАСЧЕТ ЦЕНТРА: запоминаем середину отрезка
#                     self.center_co_world = (self.anchor_co_world + self.target_co_world) * 0.5

#                     self.distance = (self.target_co_world - self.anchor_co_world).length
#                     self.input_string = ""
#                     self.state = 2
#                 return {'RUNNING_MODAL'}

#         # --- STATE 2: ВВОД ЗНАЧЕНИЯ И ТРАНСФОРМАЦИЯ ---
#         elif self.state == 2:

#             if event.type == 'C' and event.value == 'PRESS':
#                 self.use_center_mode = not self.use_center_mode
#                 self.update_geometry(context)

#             # 1. ОБРАБОТКА ВВОДА И ОБНОВЛЕНИЕ ГЕОМЕТРИИ
#             if event.type == 'WHEELUPMOUSE' and event.value == 'PRESS':
#                 step = 0.005 if event.shift else 0.05
#                 self.distance += step
#                 self.input_string = f"{self.distance:.3f}"
#                 self.reset_input_on_key = True  # Сигнал: следующий ввод с клавы заменяет строку
#                 self.update_geometry(context)

#             elif event.type == 'WHEELDOWNMOUSE' and event.value == 'PRESS':
#                 step = 0.005 if event.shift else 0.05
#                 self.distance = max(0.0, self.distance - step)
#                 self.input_string = f"{self.distance:.3f}"
#                 self.reset_input_on_key = True  # Сигнал: следующий ввод с клавы заменяет строку
#                 self.update_geometry(context)

#             elif event.type == 'BACK_SPACE' and event.value == 'PRESS':
#                 if self.reset_input_on_key:
#                     self.input_string = ""
#                     self.reset_input_on_key = False
#                 elif len(self.input_string) > 0:
#                     self.input_string = self.input_string[:-1]
#                 self.parse_and_apply_input(context)

#             elif event.type in {'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS':
#                 self.finish(context)
#                 return {'FINISHED'}

#             elif event.ascii in "0123456789.," and event.value == 'PRESS':
#                 char = "." if event.ascii == "," else event.ascii
                
#                 # Если до этого крутили колесо — сбрасываем строку и начинаем новый ввод
#                 if self.reset_input_on_key:
#                     self.input_string = char
#                     self.reset_input_on_key = False
#                 else:
#                     self.input_string += char
                    
#                 self.parse_and_apply_input(context)

#             # 2. ПОЛУЧЕНИЕ АКТУАЛЬНОЙ ПОЗИЦИИ (ПОСЛЕ update_geometry!)
#             current_target_world = self.matrix_world @ self.vert_target.co

#             if self.use_center_mode:
#                 # Вычисляем симметричную противоположную точку (виртуальный Anchor)
#                 simulated_anchor_world = self.center_co_world + (self.center_co_world - current_target_world)

#                 # 1. Линия на всю длину (от противоположного края до Target)
#                 draw_3d.add_line(simulated_anchor_world, current_target_world, color=(0.2, 0.6, 1.0, 0.5), width=2.0)
                
#                 # 2. Точки: виртуальная противоположная сторона, зафиксированный Центр и Target
#                 draw_3d.add_point(simulated_anchor_world, color=(0.2, 0.6, 1.0, 0.5), size=6.0) # Отблеск 2-го края
#                 draw_3d.add_point(self.center_co_world, color=(1.0, 0.4, 0.0, 1.0), size=10.0)    # Центр (оранжевый)
#                 draw_3d.add_point(current_target_world, color=(0.2, 0.6, 1.0, 1.0), size=8.0)    # Target (активный)
#             else:
#                 # Обычный Anchor Mode
#                 draw_3d.add_point(self.anchor_co_world, color=(0.0, 1.0, 0.5, 1.0), size=8.0)
#                 draw_3d.add_point(current_target_world, color=(0.2, 0.6, 1.0, 1.0), size=8.0)
#                 draw_3d.add_line(self.anchor_co_world, current_target_world, color=(0.2, 0.6, 1.0, 1.0), width=3.0)

            
#            # 4. ОБНОВЛЕНИЕ ОВЕРЛЕЯ (добавляем плашку с режимом)
#             mode_label = "[CENTER]" if self.use_center_mode else "[ANCHOR]"
#             display_val = self.input_string if self.input_string else f"{self.distance:.2f}"

#             screen_overlay.update_modal_overlay(
#                 mouse_2d=self.mouse_2d,
#                 header=f"{display_val} {self.unit}",
#                 description=f"Target Distance",
#                 lines=[
#                     f"(C) Mode: {mode_label}",
#                 ]
#             )

#         return {'RUNNING_MODAL'}

#     def parse_and_apply_input(self, context):
#         try:
#             val = float(self.input_string)
#             self.distance = max(0.0, val)
#             self.update_geometry(context)
#         except ValueError:
#             pass

#     def update_geometry(self, context):
#         """Смещение целевой вершины вдоль направляющего вектора."""
#         if self.use_center_mode:
#             # Направление от зафиксированного центра к исходной позиции целевой вершины
#             direction = (self.target_co_world - self.center_co_world).normalized()
#             if direction.length == 0:
#                 direction = Vector((1, 0, 0))

#             # Смещаем Target от центра на ПОЛОВИНУ итоговой дистанции
#             new_target_world = self.center_co_world + direction * (self.distance / 2.0)
#         else:
#             # Классический режим: смещение от Anchor на ПОЛНУЮ дистанцию
#             direction = (self.target_co_world - self.anchor_co_world).normalized()
#             if direction.length == 0:
#                 direction = Vector((1, 0, 0))

#             new_target_world = self.anchor_co_world + direction * self.distance

#         # Перевод из World Space в Local Space редактируемого объекта
#         inv_matrix = self.matrix_world.inverted()
#         self.vert_target.co = inv_matrix @ new_target_world
#         bmesh.update_edit_mesh(self.obj.data)

#     def find_snap_target(self, context, event):
#         """Поиск ближайшей вершины с учетом видимости и режима X-Ray."""
#         region = context.region
#         rv3d = context.region_data
#         coord = (event.mouse_region_x, event.mouse_region_y)
#         depsgraph = context.evaluated_depsgraph_get()
#         scene = context.scene

#         # Проверка состояния X-Ray во вьюпорте
#         space = context.space_data
#         is_xray_active = False
#         if space and space.type == 'VIEW_3D':
#             shading = space.shading
#             # X-Ray активен, если включен Wireframe ИЛИ явно взведен флаг show_xray
#             is_xray_active = (shading.type == 'WIRE') or shading.show_xray

#         view_origin = rv3d.view_matrix.inverted().translation

#         best_dist_2d = 25.0
#         best_world_co = None
#         matched_bm_vert = None

#         def is_point_visible(target_co):
#             """Проверяет, не заслонена ли точка другой геометрией (игнорируется в X-Ray)."""
#             if is_xray_active:
#                 return True

#             ray_dir = (target_co - view_origin)
#             dist_to_target = ray_dir.length
#             if dist_to_target < 1e-6:
#                 return True

#             ray_dir.normalize()

#             # Трассировка луча от камеры к вершине (недолетая 0.001 для защиты от самопересечения)
#             hit, loc, norm, face_idx, obj, matrix = scene.ray_cast(
#                 depsgraph, view_origin, ray_dir, distance=dist_to_target - 0.001
#             )
#             return not hit

#         # 1. Проверяем BMesh активного объекта
#         for v in self.bm.verts:
#             v_world = self.matrix_world @ v.co
#             screen_pos = view3d_utils.location_3d_to_region_2d(region, rv3d, v_world)
#             if screen_pos:
#                 dist = (screen_pos - Vector(coord)).length
#                 if dist < best_dist_2d:
#                     if is_point_visible(v_world):
#                         best_dist_2d = dist
#                         best_world_co = v_world
#                         matched_bm_vert = v

#         # 2. Проверяем геометрию остальных объектов
#         if not matched_bm_vert:
#             for obj in context.visible_objects:
#                 if obj.type != 'MESH':
#                     continue

#                 eval_obj = obj.evaluated_get(depsgraph)
#                 mesh = eval_obj.to_mesh()
#                 matrix_world = eval_obj.matrix_world

#                 for v in mesh.vertices:
#                     v_world = matrix_world @ v.co
#                     screen_pos = view3d_utils.location_3d_to_region_2d(region, rv3d, v_world)
#                     if screen_pos:
#                         dist = (screen_pos - Vector(coord)).length
#                         if dist < best_dist_2d:
#                             if is_point_visible(v_world):
#                                 best_dist_2d = dist
#                                 best_world_co = v_world

#                 eval_obj.to_mesh_clear()

#         return best_world_co, matched_bm_vert

#     # def cleanup(self):
#     #     """Очистка всех рисовалщиков и HUD при выходе."""
#     #     draw_3d.clear()
#     #     screen_overlay.clear()
#     #     screen_overlay.hide()

#     def finish(self, context):
#         draw_3d.clear()
#         screen_overlay.clear()
#         screen_overlay.hide()
#         if hasattr(self, "_handle_2d") and self._handle_2d is not None:
#             bpy.types.SpaceView3D.draw_handler_remove(self._handle_2d, 'WINDOW')
#             self._handle_2d = None
#         context.area.tag_redraw()
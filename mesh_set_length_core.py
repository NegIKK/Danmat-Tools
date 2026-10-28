import bpy
import bmesh
from mathutils import Vector

from . import viewport_helpers as vh
from . import screen_overlay


UNIT_CONFIG = {
    "NONE":        ("BU", 1.0),
    "MILLIMETERS": ("mm", 0.001),
    "CENTIMETERS": ("cm", 0.01),
    "METERS":      ("m",  1.0),
    "KILOMETERS":  ("km", 1000.0),
    "INCHES":      ("in", 0.0254),
    "FEET":        ("ft", 0.3048),
    "YARDS":       ("yd", 0.9144),
    "MILES":       ("mi", 1609.344),
}

NUMBER_TYPE_MAP = {
    "ZERO": "0", "ONE": "1", "TWO": "2", "THREE": "3", "FOUR": "4", "FIVE": "5", "SIX": "6", "SEVEN": "7", "EIGHT": "8", "NINE": "9",
    "NUM_0": "0", "NUM_1": "1", "NUM_2": "2", "NUM_3": "3", "NUM_4": "4", "NUM_5": "5", "NUM_6": "6", "NUM_7": "7", "NUM_8": "8", "NUM_9": "9",
    "NUMPAD_0": "0", "NUMPAD_1": "1", "NUMPAD_2": "2", "NUMPAD_3": "3", "NUMPAD_4": "4", "NUMPAD_5": "5", "NUMPAD_6": "6", "NUMPAD_7": "7", "NUMPAD_8": "8", "NUMPAD_9": "9",
    "NUMPAD_PERIOD": ".", "PERIOD": ".", "COMMA": ",",
}

AXIS_MODES = (
    "FREE",
    "X",
    "Y",
    "Z",
)

AXIS_LABELS = {
    "FREE": "FREE",
    "X": "LOCAL X",
    "Y": "LOCAL Y",
    "Z": "LOCAL Z",
}

_AXIS_LOCAL_VECTORS = {
    "X": Vector((1.0, 0.0, 0.0)),
    "Y": Vector((0.0, 1.0, 0.0)),
    "Z": Vector((0.0, 0.0, 1.0)),
}

WHEEL_STEP_METERS = 0.1
WHEEL_STEP_FINE_METERS = 0.01


def _live_preview(op, context):
    try:
        props = getattr(context.scene, "danmat_tools_props", None)
        if props is not None:
            value = getattr(props, "set_length_live_preview", None)
            if value is not None:
                return bool(value)
    except Exception:
        pass
    return bool(getattr(op, "LIVE_PREVIEW", False))


def unit_label(scene_unit):
    return UNIT_CONFIG.get(scene_unit, ("m", 1.0))[0]


def bu_to_display(value_bu, scene_unit, scale_length):
    value_bu = float(value_bu)
    scale_length = max(1e-12, float(scale_length))
    if scene_unit == "NONE":
        return value_bu
    _label, factor = UNIT_CONFIG.get(scene_unit, ("m", 1.0))
    factor = max(1e-12, float(factor))
    return value_bu * scale_length / factor


def display_to_bu(value_display, scene_unit, scale_length):
    value_display = float(value_display)
    scale_length = max(1e-12, float(scale_length))
    if scene_unit == "NONE":
        return value_display
    _label, factor = UNIT_CONFIG.get(scene_unit, ("m", 1.0))
    factor = max(1e-12, float(factor))
    return value_display * factor / scale_length


def meters_to_bu(value_meters, scale_length):
    scale_length = max(1e-12, float(scale_length))
    return float(value_meters) / scale_length


def format_distance(value_bu, scene_unit, scale_length, precision=3):
    precision = max(0, min(6, int(precision)))
    value = bu_to_display(value_bu, scene_unit, scale_length)
    return f"{value:.{precision}f}"


def make_selection_snapshot(bm):
    bm.verts.ensure_lookup_table()
    return {v.index: v.co.copy() for v in bm.verts if v.select}


def ensure_target_in_snapshot(snapshot, bm, index):
    bm.verts.ensure_lookup_table()
    if index < 0 or index >= len(bm.verts):
        return
    if index not in snapshot:
        snapshot[index] = bm.verts[index].co.copy()


def get_move_indices(snapshot, anchor_index):
    if anchor_index is None:
        return list(snapshot.keys())
    return [idx for idx in snapshot.keys() if idx != anchor_index]


def predicted_target_world(anchor_world, center_world, direction_world, distance_bu, use_center_mode):
    direction_world = Vector(direction_world)
    if direction_world.length < 1e-9:
        return Vector(anchor_world)
    direction_world.normalize()
    if use_center_mode:
        return Vector(center_world) + direction_world * (float(distance_bu) * 0.5)
    return Vector(anchor_world) + direction_world * float(distance_bu)


def _update_edit_mesh(mesh):
    try:
        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
    except TypeError:
        bmesh.update_edit_mesh(mesh)


def apply_distance(op, update=True):
    if getattr(op, "target_index", None) is None:
        return
    if op.target_index not in op.selected_snapshot:
        return
    if not op.move_indices:
        return
    if op.direction_world.length < 1e-9:
        return

    new_target_world = predicted_target_world(
        anchor_world=op.anchor_world,
        center_world=op.center_world,
        direction_world=op.direction_world,
        distance_bu=op.distance_bu,
        use_center_mode=op.use_center_mode,
    )

    new_target_local = op.matrix_world_inv @ new_target_world
    delta_local = new_target_local - op.selected_snapshot[op.target_index]

    op.bm.verts.ensure_lookup_table()
    for idx in op.move_indices:
        if 0 <= idx < len(op.bm.verts):
            op.bm.verts[idx].co = op.selected_snapshot[idx] + delta_local

    if update:
        _update_edit_mesh(op.obj.data)


def restore_snapshot(op, update=True):
    if getattr(op, "selected_snapshot", None) is None:
        return
    op.bm.verts.ensure_lookup_table()
    for idx, co in op.selected_snapshot.items():
        if 0 <= idx < len(op.bm.verts):
            op.bm.verts[idx].co = co
    if update:
        _update_edit_mesh(op.obj.data)


def _fallback_direction(op, context):
    try:
        rv3d = context.region_data
        direction = rv3d.view_rotation @ Vector((1.0, 0.0, 0.0))
        if direction.length > 1e-9:
            return direction.normalized()
    except Exception:
        pass
    return Vector((0.0, 0.0, 1.0))

def _local_axis_world(op, context, axis_mode):
    axis_vec = _AXIS_LOCAL_VECTORS.get(axis_mode)

    if axis_vec is None:
        return _fallback_direction(op, context)

    try:
        direction = op.matrix_world.to_3x3() @ axis_vec
    except Exception:
        return _fallback_direction(op, context)

    if direction.length < 1e-9:
        return _fallback_direction(op, context)

    return direction.normalized()


def _apply_axis_mode(op, context, recalc_clean=True):
    """
    Обновляет op.direction_world в зависимости от op.axis_mode.

    FREE:
        направление anchor -> target.

    X/Y/Z:
        направление локальной оси активного объекта.
        Если target находится в отрицательную сторону от anchor,
        направление автоматически разворачивается в -axis.
    """
    if getattr(op, "target_index", None) is None:
        return

    base = Vector(op.target_init_world) - Vector(op.anchor_world)

    if op.axis_mode == "FREE":
        direction = base
        distance = base.length
    else:
        axis = _local_axis_world(op, context, op.axis_mode)
        projection = base.dot(axis)

        if abs(projection) < 1e-9:
            direction = axis
        else:
            direction = axis if projection > 0.0 else -axis

        distance = abs(projection)

    if direction.length < 1e-9:
        direction = _fallback_direction(op, context)

    op.direction_world = direction.normalized()

    # Если пользователь ещё не вводил значение вручную — пересчитываем длину.
    if recalc_clean and not getattr(op, "user_distance_dirty", False):
        op.distance_bu = max(0.0, float(distance))
        op.input_string = format_distance(
            op.distance_bu,
            op.scene_unit,
            op.scale_length,
            op.precision,
        )
        op.reset_input_on_key = True


def set_axis_mode(op, context, axis_mode):
    if axis_mode not in AXIS_MODES:
        return False

    op.axis_mode = axis_mode
    _apply_axis_mode(op, context, recalc_clean=True)

    if _live_preview(op, context):
        apply_distance(op, update=True)

    return True


def cycle_axis_mode(op, context):
    if getattr(op, "target_index", None) is None:
        return False

    try:
        index = AXIS_MODES.index(op.axis_mode)
    except ValueError:
        index = 0

    op.axis_mode = AXIS_MODES[(index + 1) % len(AXIS_MODES)]

    _apply_axis_mode(op, context, recalc_clean=True)

    if _live_preview(op, context):
        apply_distance(op, update=True)

    return True


def toggle_center_mode(op, context):
    op.use_center_mode = not op.use_center_mode

    if _live_preview(op, context):
        apply_distance(op, update=True)


def lock_target(op, context, index, world):
    op.bm.verts.ensure_lookup_table()

    if index < 0 or index >= len(op.bm.verts):
        return False

    vert = op.bm.verts[index]

    op.target_index = index
    op.target_init_world = Vector(world) if world is not None else (op.matrix_world @ vert.co)

    ensure_target_in_snapshot(op.selected_snapshot, op.bm, index)

    # Если anchor — вершина активного объекта, она не должна двигаться.
    op.move_indices = get_move_indices(
        op.selected_snapshot,
        op.anchor_index,
    )

    op.center_world = (op.anchor_world + op.target_init_world) * 0.5

    # При захвате target всегда стартуем в FREE.
    op.axis_mode = "FREE"
    op.user_distance_dirty = False
    op.use_center_mode = False

    _apply_axis_mode(op, context, recalc_clean=True)

    op.initial_distance_bu = op.distance_bu

    return True


def flip_direction(op, context):
    """
    F:
    - В FREE режиме и если anchor — реальная edit-вершина:
      меняем anchor/target местами.
    - В остальных случаях:
      просто инвертируем направление движения.
    - Текущая длина/ввод сохраняются.
    """
    if getattr(op, "target_index", None) is None:
        return False

    old_distance_bu = op.distance_bu
    old_input_string = op.input_string
    old_user_dirty = op.user_distance_dirty

    # Полный swap только для FREE + реальная anchor-вершина.
    if op.anchor_index is not None and op.axis_mode == "FREE":
        old_anchor_index = op.anchor_index
        old_anchor_world = Vector(op.anchor_world)

        old_target_index = op.target_index
        old_target_world = Vector(op.target_init_world)

        ensure_target_in_snapshot(op.selected_snapshot, op.bm, old_anchor_index)
        ensure_target_in_snapshot(op.selected_snapshot, op.bm, old_target_index)

        op.anchor_index = old_target_index
        op.anchor_world = old_target_world

        op.target_index = old_anchor_index
        op.target_init_world = old_anchor_world

        op.center_world = (op.anchor_world + op.target_init_world) * 0.5
        op.move_indices = get_move_indices(
            op.selected_snapshot,
            op.anchor_index,
        )

        direction = op.target_init_world - op.anchor_world

        if direction.length < 1e-9:
            direction = _fallback_direction(op, context)
        else:
            direction.normalize()

        op.direction_world = direction

    else:
        direction = Vector(op.direction_world)

        if direction.length < 1e-9:
            direction = _fallback_direction(op, context)
        else:
            direction = -direction.normalized()

        op.direction_world = direction

    # Сохраняем пользовательское значение.
    op.distance_bu = old_distance_bu
    op.input_string = old_input_string
    op.user_distance_dirty = old_user_dirty
    op.reset_input_on_key = False

    if _live_preview(op, context):
        apply_distance(op, update=True)

    return True


def get_input_char(event):
    if event.value == "TEXTINPUT":
        ch = event.ascii
        if ch in "0123456789":
            return ch
        if ch in ".,":
            return "."
        return None
    if event.value not in {"PRESS", "REPEAT"}:
        return None
    ch = NUMBER_TYPE_MAP.get(event.type)
    if ch == ",":
        ch = "."
    return ch


def nudge_distance(op, context, sign, shift):
    step_meters = WHEEL_STEP_FINE_METERS if shift else WHEEL_STEP_METERS
    step_bu = meters_to_bu(step_meters, op.scale_length)

    op.user_distance_dirty = True
    op.distance_bu = max(0.0, op.distance_bu + step_bu * float(sign))

    op.input_string = format_distance(
        op.distance_bu,
        op.scene_unit,
        op.scale_length,
        op.precision,
    )

    op.reset_input_on_key = True

    if _live_preview(op, context):
        apply_distance(op, update=True)


def parse_input_string(op, context):
    op.user_distance_dirty = True

    if not op.input_string:
        op.distance_bu = 0.0

        if _live_preview(op, context):
            apply_distance(op, update=True)

        return

    try:
        value_display = float(op.input_string)
    except ValueError:
        return

    op.distance_bu = max(
        0.0,
        display_to_bu(
            value_display,
            op.scene_unit,
            op.scale_length,
        ),
    )

    if _live_preview(op, context):
        apply_distance(op, update=True)


def _state0(op, context, event):
    index, world, valid = op.snapper.snap_anchor(context, event, pixels=op.SNAP_PIXELS)
    op.hover_index = index
    op.hover_world = world
    op.hover_valid = valid
    if event.type == "LEFTMOUSE" and event.value == "PRESS":
        if valid and world is not None:
            op.anchor_index = index
            op.anchor_world = Vector(world)
            op.state = 1


def _state1(op, context, event):
    index, world = op.snapper.snap_active_vertex(context, event, pixels=op.SNAP_PIXELS)
    op.hover_index = index
    op.hover_world = world
    op.hover_valid = index is not None
    if event.type == "LEFTMOUSE" and event.value == "PRESS":
        if index is not None and index != op.anchor_index:
            if lock_target(op, context, index, world):
                op.state = 2


def _state2(op, context, event):
    if event.type == "C" and event.value == "PRESS":
        op.use_center_mode = not op.use_center_mode
        if _live_preview(op, context):
            apply_distance(op, update=True)
        return None

    if event.type == "F" and event.value == "PRESS":
        flip_direction(op, context)
        return None

    if event.type == "WHEELUPMOUSE" and event.value == "PRESS":
        nudge_distance(op, context, +1.0, event.shift)
        return None

    if event.type == "WHEELDOWNMOUSE" and event.value == "PRESS":
        nudge_distance(op, context, -1.0, event.shift)
        return None

    if event.type in {"RET", "NUMPAD_ENTER", "LEFTMOUSE"} and event.value == "PRESS":
        return "FINISHED"

    char = get_input_char(event)
    if char is not None:
        if op.reset_input_on_key:
            op.input_string = char
            op.reset_input_on_key = False
        else:
            op.input_string += char
        parse_input_string(op, context)
        return None

    if event.type == "BACK_SPACE" and event.value in {"PRESS", "REPEAT"}:
        changed = False
        if op.reset_input_on_key:
            op.input_string = ""
            op.reset_input_on_key = False
            changed = True
        elif len(op.input_string) > 0:
            op.input_string = op.input_string[:-1]
            changed = True
        if changed:
            parse_input_string(op, context)
        return None

    if event.type == "DEL" and event.value in {"PRESS", "REPEAT"}:
        op.input_string = ""
        op.reset_input_on_key = False
        parse_input_string(op, context)
        return None

    return None


def handle_state0(op, context, event):
    index, world, valid = op.snapper.snap_anchor(
        context,
        event,
        pixels=op.SNAP_PIXELS,
    )

    op.hover_index = index
    op.hover_world = world
    op.hover_valid = valid

    if event.type == "LEFTMOUSE" and event.value == "PRESS":
        if valid and world is not None:
            op.anchor_index = index
            op.anchor_world = Vector(world)
            op.state = 1


def handle_state1(op, context, event):
    index, world = op.snapper.snap_active_vertex(
        context,
        event,
        pixels=op.SNAP_PIXELS,
    )

    op.hover_index = index
    op.hover_world = world
    op.hover_valid = index is not None

    if event.type == "LEFTMOUSE" and event.value == "PRESS":
        if index is not None and index != op.anchor_index:
            if lock_target(op, context, index, world):
                op.state = 2


def init(op, context, event, report):
    obj = context.active_object
    try:
        bm = bmesh.from_edit_mesh(obj.data)
        bm.verts.ensure_lookup_table()
    except Exception as exc:
        report({"ERROR"}, f"BMesh error: {exc}")
        return False

    op.obj = obj
    op.bm = bm
    op.matrix_world = obj.matrix_world.copy()
    op.matrix_world_inv = op.matrix_world.inverted()

    unit_settings = context.scene.unit_settings
    op.scene_unit = unit_settings.length_unit
    op.scale_length = max(1e-12, float(unit_settings.scale_length))
    op.precision = max(0, min(6, int(getattr(unit_settings, "length_precision", 3))))

    op.state = 0
    op.use_center_mode = False
    op.reset_input_on_key = False

    op.anchor_index = None
    op.anchor_world = Vector()
    op.target_index = None
    op.target_init_world = Vector()
    op.center_world = Vector()
    op.direction_world = Vector()
    op.axis_mode = "FREE"
    op.user_distance_dirty = False
    op.distance_bu = 0.0
    op.input_string = ""
    op.initial_distance_bu = 0.0 # Для флипа

    op.hover_index = None
    op.hover_world = None
    op.hover_valid = False
    op.mouse_2d = Vector((event.mouse_region_x, event.mouse_region_y))

    op.selected_snapshot = make_selection_snapshot(bm)
    op.move_indices = []
    op.snapper = vh.ViewportSnapper(
        context,
        obj,
        bm,
        ignore_wire_bbox=bool(getattr(op, "ignore_wire_bbox", False)),
    )
    op._handle_2d = None

    vh.register()
    vh.clear()

    try:
        screen_overlay.clear()
        screen_overlay.show()
    except Exception:
        pass

    update_hud(op, context)

    try:
        op._handle_2d = bpy.types.SpaceView3D.draw_handler_add(
            screen_overlay.draw, (), "WINDOW", "POST_PIXEL",
        )
    except Exception as exc:
        report({"WARNING"}, f"2D overlay failed: {exc}")

    context.area.tag_redraw()
    return True


def begin_frame(op, context, event):
    context.area.tag_redraw()
    op.mouse_2d = Vector((event.mouse_region_x, event.mouse_region_y))
    vh.clear()


def process_event(op, context, event):
    if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
        return "CANCELLED"

    if op.state == 0:
        _state0(op, context, event)
    elif op.state == 1:
        _state1(op, context, event)
    elif op.state == 2:
        result = _state2(op, context, event)
        if result == "FINISHED":
            return "FINISHED"

    return "RUNNING_MODAL"


def finish(op, context, cancel=False):
    try:
        if getattr(op, "target_index", None) is not None:
            if cancel:
                if _live_preview(op, context):
                    restore_snapshot(op, update=True)
            else:
                apply_distance(op, update=True)
    finally:
        vh.clear()
        handle = getattr(op, "_handle_2d", None)
        if handle is not None:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(handle, "WINDOW")
            except Exception:
                pass
            op._handle_2d = None
        try:
            screen_overlay.clear()
            screen_overlay.hide()
        except Exception:
            pass
        try:
            context.area.tag_redraw()
        except Exception:
            pass


def draw_preview(op, context):
    # -------------------------------------------------------------
    # State 0: hover anchor
    # -------------------------------------------------------------
    if op.state == 0:
        if op.hover_valid and op.hover_world is not None:
            # Жёлтый — вершина активного edit mesh.
            # Зелёный — вершина другого объекта или виртуальная evaluated-вершина.
            color = (1.0, 0.8, 0.0, 1.0) if op.hover_index is not None else (0.2, 1.0, 0.4, 1.0)
            vh.draw_point_px(context, op.hover_world, color=color, pixels=10.0, overlay=True)

        return

    # -------------------------------------------------------------
    # State 1: anchor + hover target
    # -------------------------------------------------------------
    if op.state == 1:
        vh.draw_point_px(
            context,
            op.anchor_world,
            color=(0.0, 1.0, 0.5, 1.0),
            pixels=10.0,
            overlay=True,
        )

        if op.hover_valid and op.hover_world is not None:
            vh.draw_point_px(
                context,
                op.hover_world,
                color=(1.0, 0.8, 0.0, 1.0),
                pixels=10.0,
                overlay=True,
            )

            vh.draw_line(
                context,
                op.anchor_world,
                op.hover_world,
                color=(1.0, 0.8, 0.0, 0.75),
                width=2.0,
                overlay=True,
            )

        return

    # -------------------------------------------------------------
    # State 2: final preview
    # -------------------------------------------------------------
    if op.state == 2 and op.target_index is not None:
        # Индикатор выбранной оси.
        if getattr(op, "axis_mode", "FREE") != "FREE" and op.direction_world.length > 1e-9:
            axis_length = vh.pixel_to_world(context, op.anchor_world, 90.0)
            axis_end = op.anchor_world + op.direction_world * axis_length

            vh.draw_line(
                context,
                op.anchor_world,
                axis_end,
                color=(0.75, 0.75, 0.75, 0.45),
                width=1.5,
                overlay=True,
            )

        predicted = predicted_target_world(
            anchor_world=op.anchor_world,
            center_world=op.center_world,
            direction_world=op.direction_world,
            distance_bu=op.distance_bu,
            use_center_mode=op.use_center_mode,
        )

        if op.use_center_mode:
            simulated_anchor = op.center_world - op.direction_world * (op.distance_bu * 0.5)

            vh.draw_line(
                context,
                simulated_anchor,
                predicted,
                color=(0.2, 0.6, 1.0, 0.55),
                width=2.0,
                overlay=True,
            )

            vh.draw_point_px(
                context,
                simulated_anchor,
                color=(0.2, 0.6, 1.0, 0.75),
                pixels=8.0,
                overlay=True,
            )

            vh.draw_point_px(
                context,
                op.center_world,
                color=(1.0, 0.4, 0.0, 1.0),
                pixels=12.0,
                overlay=True,
            )

            vh.draw_point_px(
                context,
                predicted,
                color=(0.2, 0.6, 1.0, 1.0),
                pixels=10.0,
                overlay=True,
            )

        else:
            vh.draw_point_px(
                context,
                op.anchor_world,
                color=(0.0, 1.0, 0.5, 1.0),
                pixels=10.0,
                overlay=True,
            )

            vh.draw_point_px(
                context,
                predicted,
                color=(0.2, 0.6, 1.0, 1.0),
                pixels=10.0,
                overlay=True,
            )

            vh.draw_line(
                context,
                op.anchor_world,
                predicted,
                color=(0.2, 0.6, 1.0, 1.0),
                width=3.0,
                overlay=True,
            )


def _set_screen_overlay(op, header, description, lines):
    so = screen_overlay
    if so is None:
        return
    try:
        if hasattr(so, "update_modal_overlay"):
            so.update_modal_overlay(mouse_2d=op.mouse_2d, header=header, description=description, lines=lines)
            return
        if hasattr(so, "set_header"):
            so.set_header(header)
        if hasattr(so, "set_description"):
            if isinstance(description, str):
                so.set_description([description])
            else:
                so.set_description(list(description))
        if hasattr(so, "set_lines"):
            so.set_lines(lines)
        if hasattr(so, "set_position"):
            so.set_position(op.mouse_2d.x, op.mouse_2d.y)
    except Exception:
        pass


def update_hud(op, context):
    ignore_wire = "ON" if getattr(op, "ignore_wire_bbox", False) else "OFF"

    if op.state == 0:
        header = "DISTANCE DRIVE"
        description = "Step 1: Pick Anchor Vertex"
        lines = [
            "LMB: select anchor",
            "ESC/RMB: cancel",
            "Yellow: active mesh vertex",
            "Green/Cyan: other/virtual vertex",
            f"Ignore Wire/BBox: {ignore_wire}",
        ]

        if not op.hover_valid:
            lines.append("No vertex in snap radius")

    elif op.state == 1:
        header = "DISTANCE DRIVE"
        description = "Step 2: Pick Target Vertex"
        lines = [
            "LMB: select target",
            "ESC/RMB: cancel",
            "Target must be active mesh vertex",
            f"Ignore Wire/BBox: {ignore_wire}",
        ]

        if not op.hover_valid:
            lines.append("No active vertex in snap radius")

    else:
        mode_label = "[CENTER]" if op.use_center_mode else "[ANCHOR]"
        axis_label = AXIS_LABELS.get(getattr(op, "axis_mode", "FREE"), "FREE")
        value_label = unit_label(op.scene_unit)

        if op.input_string:
            value_text = op.input_string
        else:
            value_text = format_distance(
                0.0,
                op.scene_unit,
                op.scale_length,
                op.precision,
            )

        header = f"{value_text} {value_label}"
        description = "Target Distance"
        lines = [
            f"(C) Mode: {mode_label}",
            f"(A) Axis: {axis_label}",
            "(F) Flip Direction",
            "Wheel: +/- Step",
            "Shift+Wheel: Fine Step",
            "Backspace/Del: Edit Input",
            "Enter/LMB: Apply",
            "ESC/RMB: Cancel",
        ]

    _set_screen_overlay(op, header, description, lines)


def register():
    vh.register()


def unregister():
    vh.unregister()
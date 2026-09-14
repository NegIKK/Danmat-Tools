# overlay_text.py
# Blender 5.0.1
import blf
from mathutils import Vector
from .config_visual import OverlayConfig
# ------------------------------------------------------------
# НАСТРОЙКИ ОТРИСОВКИ (можно менять снаружи)
# ------------------------------------------------------------

# FONT_ID = 0
# FONT_SIZE_HEADER = 16
# FONT_SIZE_DESCRIPTION = 12
# FONT_SIZE = 14

# LINE_HEIGHT = 20
# DESCRIPTION_OFFSET = 10

# COLOR_HEADER = (0.9, 0.9, 0.9, 0.9)
# COLOR_ACTIVE = (0.3, 1.0, 0.3, 1.0)
# COLOR_TEXT = (0.8, 0.8, 0.8, 0.8)

# OFFSET = Vector((20, -20))

# ------------------------------------------------------------
# ВНУТРЕННЕЕ СОСТОЯНИЕ OVERLAY
# ------------------------------------------------------------

_state = {
    "position": Vector((0, 0)),   # позиция якоря (обычно мышь)
    "offset": Vector((0, 0)),  # смещение от позиции якоря
    "header": "",
    "description": "",
    "lines": [],                  # список строк
    "active_index": None,         # индекс активной строки
    "visible": True,
}


# ------------------------------------------------------------
# API — ЭТИ ФУНКЦИИ ТЫ БУДЕШЬ ВЫЗЫВАТЬ ИЗ АДДОНА
# ------------------------------------------------------------

def set_header(text):
    _state["header"] = text

def set_description(text):
    if isinstance(text, str):
        _state["description"] = [text]
    elif text is None:
        _state["description"] = []
    else:
        _state["description"] = list(text)


def set_lines(lines):
    """
    lines: list[str]
    """
    _state["lines"] = list(lines)


def set_active(index):
    """
    index: int | None
    """
    _state["active_index"] = index


def set_position(x, y):
    """
    Экранные координаты (px)
    """
    _state["position"] = Vector((x, y))

def set_offset(x, y):
    """
    Смещение от позиции якоря (px)
    """
    _state["offset"] = Vector((x, y))


def show():
    _state["visible"] = True


def hide():
    _state["visible"] = False


def clear():
    """Полный сброс содержимого"""
    _state["header"] = ""
    _state["description"] = []
    _state["lines"].clear()
    _state["active_index"] = None
    # _state["direction_info"] = ""



# ------------------------------------------------------------
# ФУНКЦИЯ ОТРИСОВКИ (передаётся в draw_handler_add)
# ------------------------------------------------------------

def draw():
    if not _state["visible"]:
        return

    lines = _state["lines"]
    # Убираем или меняем проверку "if not lines: return"

    font_id = OverlayConfig.FONT_ID
    if _state["offset"] == Vector((0, 0)):
        base_x, base_y = _state["position"] + OverlayConfig.MOUSE_OFFSET
    else:
        base_x, base_y = _state["position"] + _state["offset"]
        
    # --- Header ---
    blf.size(font_id, OverlayConfig.FONT_SIZE_HEADER)
    y = base_y + OverlayConfig.DESCRIPTION_OFFSET + OverlayConfig.LINE_HEIGHT * (len(_state["description"]) + 1)
    
    if _state["header"]:
        draw_text_with_outline(font_id, str(_state["header"]), base_x, y, 
                               OverlayConfig.COLOR_HEADER, OverlayConfig.COLOR_OUTLINE ,outline_width=2)
        y -= OverlayConfig.LINE_HEIGHT

    # --- Description ---
    blf.size(font_id, OverlayConfig.FONT_SIZE_DESCRIPTION)
    for description in _state["description"]:
        draw_text_with_outline(font_id, str(description), base_x, y, 
                               OverlayConfig.COLOR_DESCRIPTION, OverlayConfig.COLOR_OUTLINE)
        y -= OverlayConfig.LINE_HEIGHT

    # --- Lines ---
    blf.size(font_id, OverlayConfig.FONT_SIZE_MAIN)
    for i, text in enumerate(lines):
        color = OverlayConfig.COLOR_ACTIVE if i == _state["active_index"] else OverlayConfig.COLOR_TEXT
        draw_text_with_outline(font_id, str(text), base_x, base_y - i * OverlayConfig.LINE_HEIGHT, color)

    # --- Direction Info ---
    # if _state["direction_info"]:
    #     blf.size(font_id, OverlayConfig.FONT_SIZE_DESCRIPTION)
    #     draw_text_with_outline(
    #         font_id, 
    #         f"3D Dir: {_state['direction_info']}", 
    #         base_x, 
    #         base_y - len(lines) * OverlayConfig.LINE_HEIGHT - 5, 
    #         OverlayConfig.COLOR_ACTIVE
    #     )

def update_modal_overlay(mouse_2d, header=None, description=None, lines=None, active_index=0):
    """
    Универсальное обновление позиционирования и контента оверлея.
    Принимает 2D-координаты мыши и опциональные текстовые блоки.
    """
    # 1. Двигаем оверлей за мышью
    set_position(mouse_2d.x, mouse_2d.y)

    # 2. Обновляем заголовок, если передан
    if header is not None:
        set_header(header)

    # 3. Обновляем дополнительную инфу/режим, если передано
    if description is not None:
        set_description(description)

    # 4. Обновляем список пунктов, если передан
    if lines is not None:
        set_lines(lines)

    # 5. Подсвечиваем активный элемент списка, если указан индекс
    if active_index is not None:
        set_active(active_index)


# Вспомогательнфая функция для обводки тектса

def draw_text_with_outline(font_id, text, x, y, color, outline_color=(0, 0, 0, 1), outline_width=1):
    # Обводка (рисуем текст вокруг основного положения)
    for dx in (-outline_width, 0, outline_width):
        for dy in (-outline_width, 0, outline_width):
            if dx == 0 and dy == 0:
                continue
            blf.color(font_id, *outline_color)
            blf.position(font_id, x + dx, y + dy, 0)
            blf.draw(font_id, text)
    # Основной текст
    blf.color(font_id, *color)
    blf.position(font_id, x, y, 0)
    blf.draw(font_id, text)
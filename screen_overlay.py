# overlay_text.py
# Blender 5.0.1
import blf
from mathutils import Vector

# ------------------------------------------------------------
# НАСТРОЙКИ ОТРИСОВКИ (можно менять снаружи)
# ------------------------------------------------------------

FONT_ID = 0
FONT_SIZE_HEADER = 16
FONT_SIZE_DESCRIPTION = 12
FONT_SIZE = 14

LINE_HEIGHT = 20
DESCRIPTION_OFFSET = 10

COLOR_HEADER = (0.9, 0.9, 0.9, 0.9)
COLOR_ACTIVE = (0.3, 1.0, 0.3, 1.0)
COLOR_TEXT = (0.8, 0.8, 0.8, 0.8)

OFFSET = Vector((20, -20))


# ------------------------------------------------------------
# ВНУТРЕННЕЕ СОСТОЯНИЕ OVERLAY
# ------------------------------------------------------------

_state = {
    "position": Vector((0, 0)),   # позиция якоря (обычно мышь)
    "header": "",
    "description": [],
    "lines": [],                  # список строк
    "active_index": None,         # индекс активной строки
    "visible": True,
}


# ------------------------------------------------------------
# API — ЭТИ ФУНКЦИИ ТЫ БУДЕШЬ ВЫЗЫВАТЬ ИЗ АДДОНА
# ------------------------------------------------------------

def set_header(text):
    _state["header"] = text

def set_description(description_line):
    _state["description"] = list(description_line)


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


def show():
    _state["visible"] = True


def hide():
    _state["visible"] = False


def clear():
    """
    Полный сброс содержимого
    """
    _state["lines"].clear()
    _state["active_index"] = None


# ------------------------------------------------------------
# ФУНКЦИЯ ОТРИСОВКИ (передаётся в draw_handler_add)
# ------------------------------------------------------------

def draw():
    if not _state["visible"]:
        return

    lines = _state["lines"]
    if not lines:
        return

    font_id = FONT_ID
    

    base_x, base_y = _state["position"] + OFFSET

    # --- Header ---
    blf.size(font_id, FONT_SIZE_HEADER)
    
    y = base_y + DESCRIPTION_OFFSET + LINE_HEIGHT * (len(_state["description"]) + 1)
    
    if _state["header"]:
        # blf.color(font_id, *COLOR_HEADER)
        # blf.position(font_id, base_x, y, 0)
        # blf.draw(font_id, str(_state["header"]))
        draw_text_with_outline(font_id, str(_state["header"]), base_x, y, COLOR_HEADER)
        y -= LINE_HEIGHT

    # --- Description ---
    blf.size(font_id, FONT_SIZE_DESCRIPTION)

    for description in _state["description"]:
        # blf.color(font_id, *COLOR_TEXT)
        # blf.position(font_id, base_x, y, 0)
        # blf.draw(font_id, str(description))
        draw_text_with_outline(font_id, str(description), base_x, y, COLOR_TEXT)
        y -= LINE_HEIGHT

    # Lines
    blf.size(font_id, FONT_SIZE)

    y = base_y
    for i, text in enumerate(lines):
        color = COLOR_ACTIVE if i == _state["active_index"] else COLOR_TEXT
        draw_text_with_outline(font_id, str(text), base_x, base_y - i * LINE_HEIGHT, color)


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
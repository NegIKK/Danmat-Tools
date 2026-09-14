# Единый конфигурационный файл визуальных стилей и дефолтов
import mathutils

def hex_to_rgba(hex_str, default_alpha=1.0):
    """
    Конвертирует HEX-строку ("#RRGGBB" или "#RRGGBBAA") в кортеж float (0.0 - 1.0) для Blender API.
    """
    hex_str = hex_str.lstrip('#')
    
    # 6 символов: RRGGBB
    if len(hex_str) == 6:
        r, g, b = (int(hex_str[i:i+2], 16) / 255.0 for i in (0, 2, 4))
        return (r, g, b, default_alpha)
    
    # 8 символов: RRGGBBAA
    elif len(hex_str) == 8:
        r, g, b, a = (int(hex_str[i:i+2], 16) / 255.0 for i in (0, 2, 4, 6))
        return (r, g, b, a)
        
    return (1.0, 1.0, 1.0, default_alpha)

# ============================================================
# 2D SCREEN OVERLAY STYLES
# ============================================================
class OverlayConfig:
    # Шрифты и размеры
    FONT_ID = 0
    FONT_SIZE_HEADER = 22
    FONT_SIZE_DESCRIPTION = 12
    FONT_SIZE_MAIN = 16

    # Верстка
    LINE_HEIGHT = 20
    DESCRIPTION_OFFSET = 10
    MOUSE_OFFSET = mathutils.Vector((20.0, -20.0))

    # Цветовая палитра (R, G, B, A)
    COLOR_HEADER_HEX = "#ACE4BD"
    COLOR_DESCRIPTION_HEX = "#eeeeee"
    COLOR_TEXT_HEX = "#C2C2C2"
    COLOR_ACTIVE_HEX = "#61F88E"
    COLOR_OUTLINE_HEX = "#222E25"
    COLOR_INFO_HEX = "#9BCEAA"

    COLOR_HEADER = hex_to_rgba(COLOR_HEADER_HEX)
    COLOR_DESCRIPTION = hex_to_rgba(COLOR_DESCRIPTION_HEX)
    COLOR_TEXT = hex_to_rgba(COLOR_TEXT_HEX)
    COLOR_ACTIVE = hex_to_rgba(COLOR_ACTIVE_HEX)
    COLOR_OUTLINE = hex_to_rgba(COLOR_OUTLINE_HEX)
    COLOR_INFO = hex_to_rgba(COLOR_INFO_HEX)

    OUTLINE_WIDTH = 1


# ============================================================
# 3D VIEWPORT DRAWING STYLES
# ============================================================
class Draw3DConfig:
    # Базовые параметры линий
    DEFAULT_LINE_WIDTH = 1.5
    ACTIVE_LINE_WIDTH = 4.0
    AXIS_LINE_WIDTH = 2.0

    AXIS_ACTIVE_LINE_LENGTH = 0.4
    AXIS_LINE_LENGTH = 0.3

    # Стандартные цвета осей (RGB + Alpha)
    COLOR_X_AXIS = (1.0, 0.2, 0.2, 1.0)
    COLOR_Y_AXIS = (0.2, 1.0, 0.2, 1.0)
    COLOR_Z_AXIS = (0.2, 0.4, 1.0, 1.0)

    # Состояния подсветок и направлений
    COLOR_DEFAULT_LINE = (1.0, 1.0, 1.0, 0.8)
    COLOR_ACTIVE_LINE = (0.3, 1.0, 0.3, 1.0)
    COLOR_INACTIVE_LINE = (0.5, 0.5, 0.5, 0.4)
    COLOR_HIGHLIGHT = (1.0, 0.8, 0.2, 1.0)

    # Вспомогательная палитра для кастомных векторов
    COLOR_RAYCAST = (1.0, 0.0, 0.5, 0.8)
    COLOR_NORMAL = (0.0, 0.8, 1.0, 0.9)


# Быстрые пресеты для подсистем (при необходимости)
AXIS_COLORS = {
    'X': Draw3DConfig.COLOR_X_AXIS,
    'Y': Draw3DConfig.COLOR_Y_AXIS,
    'Z': Draw3DConfig.COLOR_Z_AXIS,
}


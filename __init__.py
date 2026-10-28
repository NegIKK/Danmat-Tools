bl_info = {
    "name": "DNMTools",
    "description": "Handy naming for bake and better modifier utilities control",
    "author": "Daniel Matus",
    "version": (0, 7, 2),
    "blender": (5, 0, 1),
    "location": "View3D > N-Panel",
    "category": "Tool (by Default)",
}

from . import properties
from . import preferences
from . import operators
from . import panels
from . import draw_3d

from . import dev_operators


def register():
    properties.register()
    preferences.register()

    draw_3d.register()

    # preferences.apply_panel_category()

    operators.register()
    dev_operators.register()
    panels.register()

def unregister(): # Выгружается все в обратном порядке
    panels.unregister()
    operators.unregister()
    dev_operators.unregister()
    draw_3d.unregister()
    preferences.unregister()
    properties.unregister()


if __name__ == "__main__":
    register()
    
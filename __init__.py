bl_info = {
    "name": "Danmat Tools",
    "description": "Quick Bake Naming and Boolean Utilities",
    "author": "Daniel Matus",
    "version": (0, 6),
    "blender": (5, 0, 1),
    "location": "View3D > N-Panel",
    "category": "Tool (by Default)",
}

from . import properties
from . import preferences
from . import operators
from . import panels


def register():
    properties.register()
    preferences.register()

    preferences.apply_panel_category()

    operators.register()
    panels.register()

def unregister(): # Выгружается все в обратном порядке
    panels.unregister()
    operators.unregister()
    preferences.unregister()
    properties.unregister()


if __name__ == "__main__":
    register()

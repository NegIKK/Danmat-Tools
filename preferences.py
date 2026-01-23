import bpy

class DanmatPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__ # Нужно чтоб в принципе это работало

    panel_category: bpy.props.StringProperty(
        name="N-Panel Category",
        description="Category name",
        default="Tool"
    ) # type: ignore

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "panel_category")


def apply_panel_category():
    """Применяет сохранённую категорию панели из настроек"""
    import bpy
    try:
        prefs = bpy.context.preferences.addons[__package__].preferences
        # Импортируем панель здесь, чтобы избежать циклических импортов
        from . import panels
        if hasattr(panels, 'VIEW3D_PT_DanmatPanel'):
            panels.VIEW3D_PT_DanmatPanel.bl_category = prefs.panel_category
    except Exception:
        pass


classes_to_register = [
    DanmatPreferences
]

def register():
    for cls in classes_to_register:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)
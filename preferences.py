import bpy


def make_update_func(panel_class_name: str):
    def update_category(self, context):

        from . import panels

        panel_class = getattr(panels, panel_class_name, None)
        if not panel_class:
            return

        try:
            bpy.utils.unregister_class(panel_class)
        except RuntimeError:
            pass

        new_cat = self.panel_category.strip() or "Tool"
        panel_class.bl_category = new_cat
        bpy.utils.register_class(panel_class)

    return update_category


class DNMTools_prefs(bpy.types.AddonPreferences):
    bl_idname = __package__

    panel_category: bpy.props.StringProperty(
        name="N-Panel Category",
        description="Category name",
        default="Tool",
        # Передаем результат вызова фабрики — это обычная функция
        update=make_update_func("VIEW3D_PT_DanmatPanel"),
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "panel_category")


classes_to_register = [
    DNMTools_prefs
]

def register():
    for cls in classes_to_register:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)
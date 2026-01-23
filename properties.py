import bpy

# Отдельный класс для хранения свойств. В нем задаются свойства аддона
class DanmatToolsProps(bpy.types.PropertyGroup):
    test: bpy.props.FloatProperty( # type: ignore
        name="Min Angle",
        description="Minimum deviation from axis (degrees)",
        default=0.01,
        min=0.00001,
        max=45.0,
    )
    use_alt_separator: bpy.props.BoolProperty( # type: ignore
        name= "Alternative Separator",
        description="Using '_' instead of '.'",
        default= False
    )



def register():
    bpy.utils.register_class(DanmatToolsProps)
    bpy.types.Scene.danmat_tools_props = bpy.props.PointerProperty(
        type=DanmatToolsProps
    )


def unregister():
    del bpy.types.Scene.danmat_tools_props
    bpy.utils.unregister_class(DanmatToolsProps)
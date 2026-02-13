import bpy

props = bpy.props

# Отдельный класс для хранения свойств. В нем задаются свойства аддона
class DanmatToolsProps(bpy.types.PropertyGroup):
    # test: bpy.props.FloatProperty( # type: ignore
    #     name="Min Angle",
    #     description="Minimum deviation from axis (degrees)",
    #     default=0.01,
    #     min=0.00001,
    #     max=45.0,
    # )
    use_alt_separator: props.BoolProperty( # type: ignore
        name= "Alternative Separator",
        description="Using '_' instead of '.'",
        default= False
    )
    digits_separator: props.StringProperty( # type: ignore
        name="Digits Separator",
        description="Separator for digits",
        default="."
    )


def register():
    bpy.utils.register_class(DanmatToolsProps)
    bpy.types.Scene.danmat_tools_props = props.PointerProperty(
        type=DanmatToolsProps
    )


def unregister():
    del bpy.types.Scene.danmat_tools_props
    bpy.utils.unregister_class(DanmatToolsProps)
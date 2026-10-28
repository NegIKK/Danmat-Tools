import bpy

props = bpy.props

class FocusObjectEntry(bpy.types.PropertyGroup):
    obj: props.PointerProperty(type=bpy.types.Object) # type: ignore

class FocusEpoch(bpy.types.PropertyGroup):
    objects: props.CollectionProperty(type=FocusObjectEntry) # type: ignore
    unmirrored: props.CollectionProperty(type=FocusObjectEntry) # type: ignore

# Отдельный класс для хранения свойств. В нем задаются свойства аддона
class DanmatToolsProps(bpy.types.PropertyGroup):
    # test: bpy.props.FloatProperty( # type: ignore
    #     name="Min Angle",
    #     description="Minimum deviation from axis (degrees)",
    #     default=0.01,
    #     min=0.00001,
    #     max=45.0,
    # )
    set_selected_util_obj_active: props.BoolProperty( # type: ignore
        name= "Set Utility Object Active",
        description="Set the selected utility object as active while scrolling through the list",
        default= False
    )
    exclude_mirror: props.BoolProperty( # type: ignore
        name= "Exclude Mirror Objects",
        description="Exclude objects from Mirror modifiers when scrolling through utilities",
        default= False
    )

    use_alt_separator: props.BoolProperty( # type: ignore
        name= "Alternative Separator",
        description="Using '_' instead of '.'",
        default= False
    )
    wire_after_rename: props.BoolProperty( # type: ignore
        name= "Set LP to Wire",
        description="Set LowPoly Object to Wireframe after renaming",
        default= False
    )
    hide_after_rename: props.BoolProperty( # type: ignore
        name= "Hide After Rename",
        description="Hide Bake Group after renaming",
        default= False
    )
    digits_separator: props.StringProperty( # type: ignore
        name="Digits Separator",
        description="Separator for digits",
        default="."
    )
    # Флаг выключения модификаторов Mirror и Array при входе в изоляцию
    exclude_modifiers: props.BoolProperty(
        name="Exclude Mirror & Array",
        description="Hide Mirror and Array modifiers when entering Focus mode",
        default=True
    ) # type: ignore

    focus_history: props.CollectionProperty(type=FocusEpoch) # type: ignore

    set_length_ignore_wire_bbox: props.BoolProperty(
        name="Ignore Wire/Bounds Objects",
        description=(
            "Set Length: do not snap to objects displayed as Wire or Bounds "
            "and do not let them block snapped points"
        ),
        default=False
    ) # type: ignore

classes = (
    FocusObjectEntry,
    FocusEpoch,
    DanmatToolsProps,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.danmat_tools_props = props.PointerProperty(
        type=DanmatToolsProps
    )


def unregister():
    del bpy.types.Scene.danmat_tools_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
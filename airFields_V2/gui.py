import bpy
import os


class FLOWFIELD_PT_Panel(bpy.types.Panel):
    bl_label = "Flow Fields"
    bl_idname = "FLOWFIELD_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'airFields'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        box = layout.box()
        box.label(text="Flow Field Settings", icon='SETTINGS')

        box = layout.box()
        box.label(text="Directories", icon='FILE_FOLDER')
        box.prop(scene, "flowfield_openfoam_dir", text="OpenFOAM Case")
        box.prop(scene, "flowfield_paraview_dir", text="ParaView Install")

        box = layout.box()
        box.label(text="Image Type", icon='IMAGE_DATA')
        box.prop(scene, "flowfield_image_type", text="")

        box = layout.box()
        box.label(text="Properties", icon='PROPERTIES')
        self._draw_properties(context, box)

        box = layout.box()
        row = box.row(align=True)
        row.scale_y = 1.5
        row.operator("flowfield.generate", text="Generate", icon='PLAY')

    def _draw_properties(self, context, box):
        scene = context.scene
        img_type = scene.flowfield_image_type

        if img_type == 'COUNTER':
            self._draw_counter_properties(context, box)
        elif img_type == '2DVECTOR':
            self._draw_vector_properties(context, box)
        elif img_type == 'STREAMLINE':
            self._draw_streamline_properties(context, box)

    def _draw_counter_properties(self, context, box):
        scene = context.scene
        col = box.column(align=True)

        col.label(text="Field")
        col.prop(scene, "flowfield_field_type", text="")

        col.separator()
        col.label(text="Location (X, Y, Z)")
        col.prop(scene, "flowfield_location", text="")

        col.separator()
        col.label(text="Normal")
        col.prop(scene, "flowfield_normal", text="")

        col.separator()
        col.label(text="Range")
        range_row = col.row(align=True)
        range_row.prop(scene, "flowfield_range_min", text="Min")
        range_row.prop(scene, "flowfield_range_max", text="Max")

    def _draw_vector_properties(self, context, box):
        scene = context.scene
        col = box.column(align=True)

        col.label(text="Field")
        col.prop(scene, "flowfield_field_type", text="")

        col.separator()
        col.label(text="Location (X, Y, Z)")
        col.prop(scene, "flowfield_location", text="")

        col.separator()
        col.label(text="Normal")
        col.prop(scene, "flowfield_normal", text="")

        col.separator()
        col.label(text="Range")
        range_row = col.row(align=True)
        range_row.prop(scene, "flowfield_range_min", text="Min")
        range_row.prop(scene, "flowfield_range_max", text="Max")

        col.separator()
        col.label(text="Scale Factor")
        col.prop(scene, "flowfield_scale_factor", text="")

    def _draw_streamline_properties(self, context, box):
        scene = context.scene
        col = box.column(align=True)

        col.label(text="Inlet Patches")
        col.prop(scene, "flowfield_inlet_patches", text="")
        col.label(text="(Space-separated, e.g. inlet inlet1)")

        col.separator()
        col.label(text="Outlet Patches")
        col.prop(scene, "flowfield_outlet_patches", text="")
        col.label(text="(Space-separated, e.g. outlet outlet1)")

        col.separator()
        col.label(text="Range")
        range_row = col.row(align=True)
        range_row.prop(scene, "flowfield_range_min", text="Min")
        range_row.prop(scene, "flowfield_range_max", text="Max")

        col.separator()
        col.label(text="Tube Radius")
        col.prop(scene, "flowfield_tube_radius", text="")

        col.separator()
        col.label(text="Seed Points")
        col.prop(scene, "flowfield_seed_points", text="")
        col.label(text="(Number of sub-areas on inlet/outlet surface)")


def prop_openfoam_dir_update(self, context):
    pass


def prop_paraview_dir_update(self, context):
    pass


def register():
    bpy.types.Scene.flowfield_openfoam_dir = bpy.props.StringProperty(
        name="OpenFOAM Case",
        description="Path to the OpenFOAM case directory",
        subtype='DIR_PATH',
        default="",
        update=prop_openfoam_dir_update,
    )
    bpy.types.Scene.flowfield_paraview_dir = bpy.props.StringProperty(
        name="ParaView Install",
        description="Path to the ParaView installation directory (contains pvpython)",
        subtype='DIR_PATH',
        default="",
        update=prop_paraview_dir_update,
    )

    bpy.types.Scene.flowfield_image_type = bpy.props.EnumProperty(
        name="Image Type",
        description="Select the visualization image type",
        items=[
            ('COUNTER', "Counter", "Counter / contour plot on slice"),
            ('2DVECTOR', "2D Vector", "2D vector field on slice"),
            ('STREAMLINE', "Streamline", "Streamlines / pathlines"),
        ],
        default='COUNTER',
    )

    bpy.types.Scene.flowfield_field_type = bpy.props.EnumProperty(
        name="Field",
        description="Select the physical field to visualize",
        items=[
            ('U', "Velocity", "Velocity field"),
            ('p', "Pressure", "Pressure field"),
            ('T', "Temperature", "Temperature field"),
        ],
        default='U',
    )

    bpy.types.Scene.flowfield_location = bpy.props.FloatVectorProperty(
        name="Location",
        description="X, Y, Z coordinates of the slice center",
        subtype='XYZ',
        default=(0.0, 0.0, 0.0),
        precision=4,
    )

    bpy.types.Scene.flowfield_normal = bpy.props.EnumProperty(
        name="Normal",
        description="Normal direction of the slice plane",
        items=[
            ('X+', "X+", "Positive X axis"),
            ('X-', "X-", "Negative X axis"),
            ('Y+', "Y+", "Positive Y axis"),
            ('Y-', "Y-", "Negative Y axis"),
            ('Z+', "Z+", "Positive Z axis"),
            ('Z-', "Z-", "Negative Z axis"),
        ],
        default='Z+',
    )

    bpy.types.Scene.flowfield_range_min = bpy.props.FloatProperty(
        name="Min",
        description="Minimum value of the color map range (0 = auto range)",
        default=0.0,
        precision=4,
    )
    bpy.types.Scene.flowfield_range_max = bpy.props.FloatProperty(
        name="Max",
        description="Maximum value of the color map range (0 = auto range)",
        default=0.0,
        precision=4,
    )

    bpy.types.Scene.flowfield_scale_factor = bpy.props.FloatProperty(
        name="Scale Factor",
        description="Scale factor for the arrow glyphs in 2D Vector mode",
        default=1.0,
        min=0.01,
        soft_max=10.0,
        precision=3,
    )

    bpy.types.Scene.flowfield_inlet_patches = bpy.props.StringProperty(
        name="Inlet Patches",
        description="Space-separated inlet patch names (STL files in constant/triSurface/)",
        default="",
    )
    bpy.types.Scene.flowfield_outlet_patches = bpy.props.StringProperty(
        name="Outlet Patches",
        description="Space-separated outlet patch names (STL files in constant/triSurface/)",
        default="",
    )

    bpy.types.Scene.flowfield_tube_radius = bpy.props.FloatProperty(
        name="Tube Radius",
        description="Radius of the tube around streamlines in Streamline mode",
        default=0.1,
        min=0.001,
        soft_max=2.0,
        precision=4,
    )

    bpy.types.Scene.flowfield_seed_points = bpy.props.IntProperty(
        name="Seed Points",
        description="Number of equal-area subdivisions on each inlet/outlet surface for seed generation",
        default=100,
        min=1,
        soft_max=500,
    )

    bpy.utils.register_class(FLOWFIELD_PT_Panel)


def unregister():
    try: bpy.utils.unregister_class(FLOWFIELD_PT_Panel)
    except Exception: pass

    for prop in ['flowfield_openfoam_dir','flowfield_paraview_dir','flowfield_image_type','flowfield_field_type','flowfield_location','flowfield_normal','flowfield_range_min','flowfield_range_max','flowfield_scale_factor','flowfield_inlet_patches','flowfield_outlet_patches','flowfield_tube_radius','flowfield_seed_points']:
        try: delattr(bpy.types.Scene, prop)
        except Exception: pass


if __name__ == "__main__":
    register()

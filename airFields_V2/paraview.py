import os


COUNTER_TEMPLATE = r'''
from paraview.simple import *
paraview.simple._DisableFirstRenderCameraReset()

import os, glob

case_path = r"{case_dir}"
foam_files = glob.glob(os.path.join(case_path, "*.foam"))
if not foam_files:
    raise FileNotFoundError("No .foam file found in case directory: " + case_path)
foam_file = foam_files[0]

reader = OpenFOAMReader(registrationName="case.foam", FileName=foam_file)
reader.SkipZeroTime = 1
reader.CaseType = 'Reconstructed Case'
reader.MeshRegions = ["internalMesh"]
reader.CellArrays = ["{field_name}"]
reader.UpdatePipeline()

animationScene1 = GetAnimationScene()
animationScene1.UpdateAnimationUsingDataTimeSteps()

renderView1 = GetActiveViewOrCreate("RenderView")
display = Show(reader, renderView1, "UnstructuredGridRepresentation")
{u_colorby}
renderView1.ResetCamera(False)
renderView1.Update()

slice1 = Slice(registrationName="Slice1", Input=reader)
slice1.SliceType = "Plane"
slice1.SliceType.Origin = {origin}
slice1.SliceType.Normal = {normal}

sliceDisplay = Show(slice1, renderView1, "GeometryRepresentation")
{u_colorby_slice}
Hide(reader, renderView1)
renderView1.Update()

{range_setup}

output_path = os.path.join(r"{output_dir}", "flowfield_output.x3d")
ExportView(output_path, view=renderView1)
print("EXPORT_DONE:" + output_path)
'''


VECTOR_TEMPLATE = r'''
from paraview.simple import *
paraview.simple._DisableFirstRenderCameraReset()

import os, glob

case_path = r"{case_dir}"
foam_files = glob.glob(os.path.join(case_path, "*.foam"))
if not foam_files:
    raise FileNotFoundError("No .foam file found in case directory: " + case_path)
foam_file = foam_files[0]

reader = OpenFOAMReader(registrationName="case.foam", FileName=foam_file)
reader.SkipZeroTime = 1
reader.CaseType = 'Reconstructed Case'
reader.MeshRegions = ["internalMesh"]
reader.CellArrays = ["{field_name}"]
reader.UpdatePipeline()

animationScene1 = GetAnimationScene()
animationScene1.UpdateAnimationUsingDataTimeSteps()

renderView1 = GetActiveViewOrCreate("RenderView")
display = Show(reader, renderView1, "UnstructuredGridRepresentation")
{u_colorby}
renderView1.ResetCamera(False)
renderView1.Update()

slice1 = Slice(registrationName="Slice1", Input=reader)
slice1.SliceType = "Plane"
slice1.SliceType.Origin = {origin}
slice1.SliceType.Normal = {normal}

sliceDisplay = Show(slice1, renderView1, "GeometryRepresentation")
{u_colorby_slice}
Hide(reader, renderView1)
renderView1.Update()

glyph1 = Glyph(registrationName="Glyph1", Input=slice1, GlyphType="Arrow")
glyph1.OrientationArray = ["POINTS", "U"]
glyph1.ScaleArray = ["POINTS", "No scale array"]
glyph1.ScaleFactor = {scale_factor}
glyph1.GlyphTransform = "Transform2"

glyphDisplay = Show(glyph1, renderView1, "GeometryRepresentation")
{u_colorby_glyph}
renderView1.Update()

{range_setup}

Hide(slice1, renderView1)
Render()

output_path = os.path.join(r"{output_dir}", "flowfield_output.x3d")
ExportView(output_path, view=renderView1)
print("EXPORT_DONE:" + output_path)
'''


STREAMLINE_TEMPLATE = r'''
from paraview.simple import *
paraview.simple._DisableFirstRenderCameraReset()

import os, glob

case_path = r"{case_dir}"
foam_files = glob.glob(os.path.join(case_path, "*.foam"))
if not foam_files:
    raise FileNotFoundError("No .foam file found in case directory: " + case_path)
foam_file = foam_files[0]

reader = OpenFOAMReader(registrationName="case.foam", FileName=foam_file)
reader.SkipZeroTime = 1
reader.CaseType = 'Reconstructed Case'
reader.MeshRegions = ["internalMesh"]
reader.CellArrays = ["U"]
reader.UpdatePipeline()

animationScene1 = GetAnimationScene()
animationScene1.UpdateAnimationUsingDataTimeSteps()

renderView1 = GetActiveViewOrCreate("RenderView")
display = Show(reader, renderView1, "UnstructuredGridRepresentation")
ColorBy(display, ("POINTS", "{field_name}"{vector_suffix}))
renderView1.ResetCamera(False)
renderView1.Update()

{stl_loaders}

{stream_tracers}

all_seeds = {stl_var_list}
Hide(reader, renderView1)

{stl_hide_block}

{range_setup}

output_path = os.path.join(r"{output_dir}", "flowfield_output.x3d")
ExportView(output_path, view=renderView1)
print("EXPORT_DONE:" + output_path)
'''


STL_LOADER_SNIPPET = r'''
stl_{idx} = STLReader(registrationName='stl_{patch_name}', FileNames=[os.path.join(r"{stl_dir}", "{patch_name}.stl")])
stl_{idx}Display = Show(stl_{idx}, renderView1, "GeometryRepresentation")
'''

STREAM_TRACER_SNIPPET = r'''
streamTracer_{idx} = StreamTracerWithCustomSource(registrationName='StreamTracer_{idx}', Input=reader, SeedSource=stl_{idx})
streamTracer_{idx}.Vectors = ["POINTS", "U"]
streamTracer_{idx}.MaximumStreamlineLength = 20.0

streamTracer_{idx}Display = Show(streamTracer_{idx}, renderView1, "GeometryRepresentation")
ColorBy(streamTracer_{idx}Display, ("POINTS", "{field_name}"{vector_suffix}))

tube_{idx} = Tube(registrationName='Tube_{idx}', Input=streamTracer_{idx})
tube_{idx}.Radius = {tube_radius}

tube_{idx}Display = Show(tube_{idx}, renderView1, "GeometryRepresentation")
ColorBy(tube_{idx}Display, ("POINTS", "{field_name}"{vector_suffix}))
Hide(streamTracer_{idx}, renderView1)
'''

STL_HIDE_SNIPPET = r'Hide(stl_{idx}, renderView1)'


def _colorby_str(field_name):
    if field_name == 'U':
        return 'ColorBy(display, ("POINTS", "U", "Magnitude"))'
    return f'ColorBy(display, ("POINTS", "{field_name}"))'


def _colorby_slice_str(field_name, var):
    if field_name == 'U':
        return f'ColorBy({var}, ("POINTS", "U", "Magnitude"))'
    return f'ColorBy({var}, ("POINTS", "{field_name}"))'


def _vector_suffix(field_name):
    if field_name == 'U':
        return ', "Magnitude"'
    return ''


def _range_setup_str(field_name, range_min, range_max):
    if range_min == 0.0 and range_max == 0.0:
        return '# Auto range (both min and max are 0)\n# display.RescaleTransferFunctionToDataRange(True, False)'
    field_display = field_name
    if field_name == 'U':
        field_display = 'U'

    return f'''# Manual range: [{range_min}, {range_max}]
{field_display}LUT = GetColorTransferFunction("{field_display}")
{field_display}LUT.AutomaticRescaleRangeMode = "Never"
mid = ({range_min} + {range_max}) / 2.0
{field_display}LUT.RGBPoints = [{range_min}, 0.231373, 0.298039, 0.752941, mid, 0.865003, 0.865003, 0.865003, {range_max}, 0.705882, 0.0156863, 0.14902]'''


def generate_paraview_script(
    case_dir,
    image_type,
    field_name,
    origin,
    normal,
    output_dir,
    range_min=0.0,
    range_max=0.0,
    scale_factor=1.0,
    inlet_patches="",
    outlet_patches="",
    tube_radius=0.1,
    stl_subdivided_dir=None,
):
    esc = lambda p: p.replace("\\", "\\\\")

    range_setup = _range_setup_str(field_name, range_min, range_max)
    u_colorby = _colorby_str(field_name)
    u_colorby_slice = _colorby_slice_str(field_name, "sliceDisplay")
    u_colorby_glyph = _colorby_slice_str(field_name, "glyphDisplay")
    vec_suffix = _vector_suffix(field_name)

    if image_type == 'COUNTER':
        template = COUNTER_TEMPLATE
        return template.format(
            case_dir=esc(case_dir),
            field_name=field_name,
            origin=tuple(origin),
            normal=tuple(normal),
            output_dir=esc(output_dir),
            range_setup=range_setup,
            u_colorby=u_colorby,
            u_colorby_slice=u_colorby_slice,
        )

    elif image_type == '2DVECTOR':
        template = VECTOR_TEMPLATE
        return template.format(
            case_dir=esc(case_dir),
            field_name=field_name,
            origin=tuple(origin),
            normal=tuple(normal),
            output_dir=esc(output_dir),
            scale_factor=scale_factor,
            range_setup=range_setup,
            u_colorby=u_colorby,
            u_colorby_slice=u_colorby_slice,
            u_colorby_glyph=u_colorby_glyph,
        )

    elif image_type == 'STREAMLINE':
        inlet_list = [n.strip() for n in inlet_patches.split() if n.strip()]
        outlet_list = [n.strip() for n in outlet_patches.split() if n.strip()]
        all_patches = inlet_list + outlet_list

        if stl_subdivided_dir:
            stl_dir = stl_subdivided_dir
        else:
            stl_dir = os.path.join(case_dir, "constant", "triSurface").replace("\\", "\\\\")

        stl_loaders = ""
        stream_tracers = ""
        stl_hide = ""
        stl_var_list = []
        for i, patch in enumerate(all_patches):
            stl_loaders += STL_LOADER_SNIPPET.format(idx=i, patch_name=patch, stl_dir=esc(stl_dir))
            stream_tracers += STREAM_TRACER_SNIPPET.format(
                idx=i,
                field_name=field_name,
                tube_radius=tube_radius,
                vector_suffix=vec_suffix,
            )
            stl_hide += STL_HIDE_SNIPPET.format(idx=i) + "\n"
            stl_var_list.append(f"stl_{i}")

        template = STREAMLINE_TEMPLATE
        return template.format(
            case_dir=esc(case_dir),
            field_name=field_name,
            output_dir=esc(output_dir),
            range_setup=range_setup,
            stl_loaders=stl_loaders,
            stream_tracers=stream_tracers,
            stl_var_list=str(stl_var_list),
            stl_hide_block=stl_hide,
            vector_suffix=vec_suffix,
            tube_radius=tube_radius,
        )

    raise ValueError(f"Unknown image_type: {image_type}")


def write_script(script_content, output_path):
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(script_content)
    return os.path.abspath(output_path)


def normal_to_vector(normal_str):
    mapping = {
        'X+': (1.0, 0.0, 0.0),
        'X-': (-1.0, 0.0, 0.0),
        'Y+': (0.0, 1.0, 0.0),
        'Y-': (0.0, -1.0, 0.0),
        'Z+': (0.0, 0.0, 1.0),
        'Z-': (0.0, 0.0, -1.0),
    }
    return mapping.get(normal_str, (0.0, 0.0, 1.0))

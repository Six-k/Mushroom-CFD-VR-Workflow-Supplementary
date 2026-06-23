import bpy
import bmesh
import os
import sys
import math


def _ensure_vtk():
    try:
        import vtk
        return vtk
    except ImportError:
        raise ImportError(
            "vtk Python package is required. "
            "Install it via: pip install vtk==9.5.0 (into Blender's Python)"
        )


# ParaView "Cool to Warm" colormap (8 key colors)
_COLORMAP_COOLWARM = [
    (0.231373, 0.298039, 0.752941),
    (0.552941, 0.537255, 0.823529),
    (0.823529, 0.741176, 0.823529),
    (0.945098, 0.901961, 0.823529),
    (0.945098, 0.823529, 0.650980),
    (0.898039, 0.623529, 0.356863),
    (0.823529, 0.321569, 0.176471),
    (0.705882, 0.015686, 0.149020),
]


def _sample_colormap(t):
    n = len(_COLORMAP_COOLWARM) - 1
    idx = t * n
    i0 = min(int(idx), n - 1)
    i1 = i0 + 1
    f = idx - i0
    c0 = _COLORMAP_COOLWARM[i0]
    c1 = _COLORMAP_COOLWARM[i1]
    return (
        c0[0] + (c1[0] - c0[0]) * f,
        c0[1] + (c1[1] - c0[1]) * f,
        c0[2] + (c1[2] - c0[2]) * f,
    )


def vtk_to_blender_mesh(filepath, object_name=None, smooth=True,
                        field_name=None, range_min=0.0, range_max=0.0):
    vtk = _ensure_vtk()

    if not os.path.exists(filepath):
        print(f"[v3] VTK file not found: {filepath}")
        return None

    # Step 1: Read VTK file
    ext = os.path.splitext(filepath)[1].lower()
    if ext == '.vtp':
        reader = vtk.vtkXMLPolyDataReader()
    elif ext == '.vtm':
        reader = vtk.vtkXMLMultiBlockDataReader()
    elif ext == '.vtu':
        reader = vtk.vtkXMLUnstructuredGridReader()
    elif ext == '.vtk':
        reader = vtk.vtkGenericDataObjectReader()
    else:
        reader = vtk.vtkXMLGenericDataObjectReader()

    reader.SetFileName(filepath)
    reader.Update()
    data = reader.GetOutput()

    if data is None:
        print(f"[v3] Failed to read VTK file: {filepath}")
        return None

    # Step 2: Extract PolyData, preprocess
    polydata_list = _extract_polydata(vtk, data)
    if not polydata_list:
        print(f"[v3] No PolyData found in: {filepath}")
        return None
    print(f"[v3] Found {len(polydata_list)} PolyData block(s) in {filepath}")

    processed_blocks = []
    data_vmin = float('inf')
    data_vmax = float('-inf')

    for pd in polydata_list:
        tf = vtk.vtkTriangleFilter()
        tf.SetInputData(pd)
        tf.Update()
        pd_tri = tf.GetOutput()

        vals = []
        if field_name:
            vals = _extract_field_values(vtk, pd_tri, field_name)
            if vals:
                data_vmin = min(data_vmin, min(vals))
                data_vmax = max(data_vmax, max(vals))

        processed_blocks.append((pd_tri, vals))

    if range_min == 0.0 and range_max == 0.0 and field_name:
        range_min, range_max = data_vmin, data_vmax
    if field_name:
        print(f"[v3] Field '{field_name}' range: [{data_vmin:.3f}, {data_vmax:.3f}] → mapped [{range_min}, {range_max}]")

    # Step 3: Create Blender Mesh
    if object_name is None:
        object_name = os.path.splitext(os.path.basename(filepath))[0]

    me = bpy.data.meshes.new(object_name)
    ob = bpy.data.objects.new(object_name, me)
    bpy.context.collection.objects.link(ob)

    bm = bmesh.new()
    total_verts = 0
    vert_to_color = {}

    for block_idx, (pd, fvals) in enumerate(processed_blocks):
        n_points = pd.GetNumberOfPoints()
        n_cells = pd.GetNumberOfCells()
        if n_points == 0:
            continue
        print(f"[v3]   Block {block_idx}: {n_points} points, {n_cells} cells")

        base_idx = len(bm.verts)
        verts = [bm.verts.new(pd.GetPoint(i)) for i in range(n_points)]

        for i in range(n_cells):
            pts = pd.GetCell(i).GetPointIds()
            n_pts = pts.GetNumberOfIds()
            if n_pts >= 3:
                try:
                    f = bm.faces.new([verts[pts.GetId(j)] for j in range(n_pts)])
                    f.smooth = smooth
                except ValueError:
                    pass

        if field_name and fvals:
            for i in range(min(n_points, len(fvals))):
                v = fvals[i]
                if range_max != range_min:
                    t = max(0.0, min(1.0, (v - range_min) / (range_max - range_min)))
                else:
                    t = 0.5
                vert_to_color[base_idx + i] = _sample_colormap(t)

        total_verts += n_points

    if total_verts == 0:
        bm.free()
        return None

    # Step 4: Write mesh
    bm.to_mesh(me)
    bm.free()

    # Step 5: Apply vertex colors
    if vert_to_color and len(me.vertices) > 0:
        try:
            vc = me.vertex_colors.new(name="field_color")
            for poly in me.polygons:
                for loop_idx in poly.loop_indices:
                    v_idx = me.loops[loop_idx].vertex_index
                    if v_idx in vert_to_color:
                        r, g, b = vert_to_color[v_idx]
                    else:
                        r, g, b = 0.5, 0.5, 0.5
                    vc.data[loop_idx].color = (r, g, b, 1.0)
            print(f"[v3] Vertex colors applied from field '{field_name}' ({len(vc.data)} loops, legacy API)")
        except Exception as e:
            print(f"[v3] Vertex color creation failed: {e}")

    me.update()

    # Step 6: Create material
    _create_vertex_color_material(ob, field_name)

    print(f"[v3] Mesh: {len(me.vertices)}v, {len(me.edges)}e, {len(me.polygons)}f")
    return ob


def _extract_field_values(vtk, polydata, field_name):
    pd = polydata.GetPointData()
    n = polydata.GetNumberOfPoints()

    arr = None
    if pd.HasArray(field_name):
        arr = pd.GetArray(field_name)
    if arr is None:
        for suffix in ('_Magnitude', '_magnitude', ' Magnitude', ' magnitude'):
            if pd.HasArray(field_name + suffix):
                arr = pd.GetArray(field_name + suffix)
                break
    if arr is None:
        for i in range(pd.GetNumberOfArrays()):
            name = pd.GetArrayName(i)
            if name and name.lower().startswith(field_name.lower()):
                arr = pd.GetArray(i)
                break

    if arr is None:
        return []

    n_comp = arr.GetNumberOfComponents()
    vals = []
    for i in range(min(n, arr.GetNumberOfTuples())):
        if n_comp == 1:
            vals.append(arr.GetValue(i))
        elif n_comp == 3:
            t = arr.GetTuple(i)
            vals.append(math.sqrt(t[0]**2 + t[1]**2 + t[2]**2))
        else:
            vals.append(arr.GetComponent(i, 0))
    return vals


def _create_vertex_color_material(ob, field_name):
    if not field_name:
        return

    mat_name = f"v3_field_{field_name}"
    mat = bpy.data.materials.get(mat_name)
    if mat is None:
        mat = bpy.data.materials.new(mat_name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    vcol_node = nodes.new('ShaderNodeVertexColor')
    vcol_node.layer_name = "field_color"

    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    output = nodes.new('ShaderNodeOutputMaterial')

    links.new(vcol_node.outputs['Color'], bsdf.inputs['Base Color'])
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    if ob.data.materials:
        ob.data.materials[0] = mat
    else:
        ob.data.materials.append(mat)


def _extract_polydata(vtk, data):
    result = []
    if isinstance(data, vtk.vtkPolyData) and data.GetNumberOfPoints() > 0:
        result.append(data)
    elif isinstance(data, vtk.vtkMultiBlockDataSet):
        it = data.NewIterator()
        while not it.IsDoneWithTraversal():
            block = it.GetCurrentDataObject()
            if block:
                result.extend(_extract_polydata(vtk, block))
            it.GoToNextItem()
    elif isinstance(data, vtk.vtkDataSet):
        gf = vtk.vtkGeometryFilter()
        gf.SetInputData(data)
        gf.Update()
        pd = gf.GetOutput()
        if pd and pd.GetNumberOfPoints() > 0:
            result.append(pd)
    return result

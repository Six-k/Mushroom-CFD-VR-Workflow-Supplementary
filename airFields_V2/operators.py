import bpy
import os
import subprocess
import sys
import shutil
import time
import math

from .paraview import generate_paraview_script, write_script, normal_to_vector
from .stl_tools import subdivide_stl


def _ensure_vertex_color_material(obj):
    if not obj.data.vertex_colors:
        return
    vc_name = obj.data.vertex_colors[0].name

    mat_name = f"v2_{vc_name}"
    mat = bpy.data.materials.get(mat_name)
    if mat is None:
        mat = bpy.data.materials.new(mat_name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    vcol = nodes.new('ShaderNodeVertexColor')
    vcol.layer_name = vc_name
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    out = nodes.new('ShaderNodeOutputMaterial')
    links.new(vcol.outputs['Color'], bsdf.inputs['Base Color'])
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])

    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)


class FLOWFIELD_OT_Generate(bpy.types.Operator):
    bl_idname = "flowfield.generate"
    bl_label = "Generate Flow Field"
    bl_description = "Generate flow field visualization via ParaView and import into Blender"
    bl_options = {'REGISTER', 'UNDO'}

    def _find_pvpython(self, paraview_dir):
        candidates = []
        bin_dir = os.path.join(paraview_dir, "bin")
        if os.path.isdir(bin_dir):
            for fname in os.listdir(bin_dir):
                base = os.path.splitext(fname)[0].lower()
                if base in ("pvpython", "pvpython.exe"):
                    candidates.append(os.path.join(bin_dir, fname))
        for root, _, files in os.walk(paraview_dir):
            for fname in files:
                base = os.path.splitext(fname)[0].lower()
                if base == "pvpython":
                    candidates.append(os.path.join(root, fname))
        return candidates[0] if candidates else None

    def _validate_inputs(self, context):
        scene = context.scene
        errors = []

        openfoam_dir = scene.flowfield_openfoam_dir.strip()
        paraview_dir = scene.flowfield_paraview_dir.strip()

        if not openfoam_dir:
            errors.append("OpenFOAM case directory is not set.")
        elif not os.path.isdir(openfoam_dir):
            errors.append("OpenFOAM case directory does not exist.")

        if not paraview_dir:
            errors.append("ParaView installation directory is not set.")
        elif not os.path.isdir(paraview_dir):
            errors.append("ParaView installation directory does not exist.")

        return errors, openfoam_dir, paraview_dir

    def _run_paraview(self, pvpython_path, script_path):
        cmd = [pvpython_path, script_path]
        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            startupinfo=startupinfo,
        )
        stdout, stderr = proc.communicate(timeout=300)

        export_path = None
        for line in stdout.splitlines():
            if line.startswith("EXPORT_DONE:"):
                export_path = line[len("EXPORT_DONE:"):].strip()
                break

        return export_path, stdout, stderr

    def _import_x3d(self, filepath):
        abs_path = os.path.abspath(filepath)
        if not os.path.exists(abs_path):
            return abs_path, False, "X3D output file not found after ParaView execution."

        if abs_path.lower().endswith(".x3d") or abs_path.lower().endswith(".x3dv"):
            pre_objects = set(bpy.context.scene.objects)

            bpy.ops.import_scene.x3d(filepath=abs_path)
            bpy.context.view_layer.update()

            post_objects = set(bpy.context.scene.objects)
            new_objects = post_objects - pre_objects

            for obj in new_objects:
                if obj.parent is None or obj.parent not in new_objects:
                    obj.rotation_euler = (math.radians(0), 0, math.radians(0))

                if obj.type == 'MESH' and obj.data.vertex_colors:
                    _ensure_vertex_color_material(obj)

            return abs_path, True, None
        else:
            return abs_path, False, f"Unexpected output file type: {abs_path}"

    def execute(self, context):
        scene = context.scene

        errors, openfoam_dir, paraview_dir = self._validate_inputs(context)
        if errors:
            for err in errors:
                self.report({'ERROR'}, err)
            return {'CANCELLED'}

        pvpython_path = self._find_pvpython(paraview_dir)
        if not pvpython_path:
            self.report({'ERROR'}, "Could not locate pvpython in the ParaView directory.")
            return {'CANCELLED'}

        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        vr_blender_root = os.path.join(openfoam_dir, "VR_blender")
        work_dir = os.path.join(vr_blender_root, timestamp)
        os.makedirs(work_dir, exist_ok=True)
        self.report({'INFO'}, f"Working directory: {work_dir}")

        normal_vec = normal_to_vector(scene.flowfield_normal)
        origin = (
            scene.flowfield_location[0],
            scene.flowfield_location[1],
            scene.flowfield_location[2],
        )

        subdivided_stl_dir = None
        if scene.flowfield_image_type == 'STREAMLINE':
            subdivided_stl_dir = os.path.join(work_dir, "stl_subdivided")
            os.makedirs(subdivided_stl_dir, exist_ok=True)
            seed_points = max(1, scene.flowfield_seed_points)

            inlet_list = [n.strip() for n in scene.flowfield_inlet_patches.split() if n.strip()]
            outlet_list = [n.strip() for n in scene.flowfield_outlet_patches.split() if n.strip()]
            all_patches = inlet_list + outlet_list

            for patch_name in all_patches:
                src_stl = os.path.join(openfoam_dir, "constant", "triSurface", f"{patch_name}.stl")
                dst_stl = os.path.join(subdivided_stl_dir, f"{patch_name}.stl")
                if not os.path.exists(src_stl):
                    self.report({'WARNING'}, f"STL not found for patch '{patch_name}': {src_stl}")
                    continue
                ok, msg = subdivide_stl(src_stl, dst_stl, N=seed_points)
                if ok:
                    self.report({'INFO'}, f"Subdivided STL: {patch_name} -> {msg}")
                else:
                    self.report({'ERROR'}, f"STL subdivision failed for '{patch_name}': {msg}")
                    return {'CANCELLED'}

        script_content = generate_paraview_script(
            case_dir=openfoam_dir,
            image_type=scene.flowfield_image_type,
            field_name=scene.flowfield_field_type,
            origin=origin,
            normal=normal_vec,
            output_dir=work_dir,
            range_min=scene.flowfield_range_min,
            range_max=scene.flowfield_range_max,
            scale_factor=scene.flowfield_scale_factor,
            inlet_patches=scene.flowfield_inlet_patches,
            outlet_patches=scene.flowfield_outlet_patches,
            tube_radius=scene.flowfield_tube_radius,
            stl_subdivided_dir=subdivided_stl_dir,
        )

        script_path = os.path.join(work_dir, "flowfield_pvscript.py")
        write_script(script_content, script_path)

        self.report({'INFO'}, f"Running ParaView script: {script_path}")
        export_path, stdout, stderr = self._run_paraview(pvpython_path, script_path)

        if export_path:
            abs_export, success, error_msg = self._import_x3d(export_path)
            if success:
                self.report({'INFO'}, f"X3D imported successfully from: {abs_export}")
            else:
                self.report({'WARNING'}, error_msg)
        else:
            self.report({'WARNING'}, "ParaView completed but no X3D output was detected.")

        try:
            shutil.rmtree(work_dir)
        except Exception:
            pass

        return {'FINISHED'}


def register():
    bpy.utils.register_class(FLOWFIELD_OT_Generate)


def unregister():
    bpy.utils.unregister_class(FLOWFIELD_OT_Generate)

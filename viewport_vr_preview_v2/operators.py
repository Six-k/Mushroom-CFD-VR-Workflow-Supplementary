# SPDX-FileCopyrightText: 2021-2023 Blender Foundation
#
# SPDX-License-Identifier: GPL-2.0-or-later

if "bpy" in locals():
    import importlib
    importlib.reload(properties)
else:
    from . import properties

import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from bpy.app.translations import pgettext_data as data_
from bpy.types import (
    Gizmo,
    GizmoGroup,
    Operator,
)
import math
from math import radians
from mathutils import Euler, Matrix, Quaternion, Vector


# ---------------------------------------------------------------------------
# Cached matrices — allocated once, reused every frame to reduce GC pressure.
# ---------------------------------------------------------------------------
_IDENTITY_4X4 = Matrix.Identity(4)
_SCALE_01 = Matrix.Scale(0.1, 4)
_SCALE_05 = Matrix.Scale(0.5, 4)


### Landmarks.
class VIEW3D_OT_vr_landmark_add(Operator):
    bl_idname = "view3d.vr_landmark_add"
    bl_label = "Add VR Landmark"
    bl_description = "Add a new VR landmark to the list and select it"
    bl_options = {'UNDO', 'REGISTER'}

    def execute(self, context):
        scene = context.scene
        landmarks = scene.vr_landmarks

        landmarks.add()

        scene.vr_landmarks_selected = len(landmarks) - 1

        return {'FINISHED'}


class VIEW3D_OT_vr_landmark_from_camera(Operator):
    bl_idname = "view3d.vr_landmark_from_camera"
    bl_label = "Add VR Landmark from Camera"
    bl_description = "Add a new VR landmark from the active camera object to the list and select it"
    bl_options = {'UNDO', 'REGISTER'}

    @classmethod
    def poll(cls, context):
        cam_selected = False

        vl_objects = bpy.context.view_layer.objects
        if vl_objects.active and vl_objects.active.type == 'CAMERA':
            cam_selected = True
        return cam_selected

    def execute(self, context):
        scene = context.scene
        landmarks = scene.vr_landmarks
        cam = context.view_layer.objects.active
        lm = landmarks.add()
        lm.type = 'OBJECT'
        lm.base_pose_object = cam
        lm.name = "LM_" + cam.name

        scene.vr_landmarks_selected = len(landmarks) - 1

        return {'FINISHED'}


class VIEW3D_OT_vr_landmark_from_session(Operator):
    bl_idname = "view3d.vr_landmark_from_session"
    bl_label = "Add VR Landmark from Session"
    bl_description = "Add VR landmark from the viewer pose of the running VR session to the list and select it"
    bl_options = {'UNDO', 'REGISTER'}

    @classmethod
    def poll(cls, context):
        return bpy.types.XrSessionState.is_running(context)

    def execute(self, context):
        scene = context.scene
        landmarks = scene.vr_landmarks
        wm = context.window_manager

        lm = landmarks.add()
        lm.type = "CUSTOM"
        scene.vr_landmarks_selected = len(landmarks) - 1

        loc = wm.xr_session_state.viewer_pose_location
        rot = wm.xr_session_state.viewer_pose_rotation.to_euler()

        lm.base_pose_location = loc
        lm.base_pose_angle = rot[2]

        return {'FINISHED'}


class VIEW3D_OT_vr_camera_landmark_from_session(Operator):
    bl_idname = "view3d.vr_camera_landmark_from_session"
    bl_label = "Add Camera and VR Landmark from Session"
    bl_description = "Create a new Camera and VR Landmark from the viewer pose of the running VR session and select it"
    bl_options = {'UNDO', 'REGISTER'}

    @classmethod
    def poll(cls, context):
        return bpy.types.XrSessionState.is_running(context)

    def execute(self, context):
        scene = context.scene
        landmarks = scene.vr_landmarks
        wm = context.window_manager

        lm = landmarks.add()
        lm.type = 'OBJECT'
        scene.vr_landmarks_selected = len(landmarks) - 1

        loc = wm.xr_session_state.viewer_pose_location
        rot = wm.xr_session_state.viewer_pose_rotation.to_euler()

        cam = bpy.data.cameras.new(data_("Camera") + "_" + lm.name)
        new_cam = bpy.data.objects.new(data_("Camera") + "_" + lm.name, cam)
        scene.collection.objects.link(new_cam)
        new_cam.location = loc
        new_cam.rotation_euler = rot

        lm.base_pose_object = new_cam

        return {'FINISHED'}


class VIEW3D_OT_update_vr_landmark(Operator):
    bl_idname = "view3d.update_vr_landmark"
    bl_label = "Update Custom VR Landmark"
    bl_description = "Update the selected landmark from the current viewer pose in the VR session"
    bl_options = {'UNDO', 'REGISTER'}

    @classmethod
    def poll(cls, context):
        selected_landmark = properties.VRLandmark.get_selected_landmark(context)
        return bpy.types.XrSessionState.is_running(context) and selected_landmark.type == 'CUSTOM'

    def execute(self, context):
        wm = context.window_manager

        lm = properties.VRLandmark.get_selected_landmark(context)

        loc = wm.xr_session_state.viewer_pose_location
        rot = wm.xr_session_state.viewer_pose_rotation.to_euler()

        lm.base_pose_location = loc
        lm.base_pose_angle = rot

        properties.vr_landmark_active_update(None, context)

        return {'FINISHED'}


class VIEW3D_OT_vr_landmark_remove(Operator):
    bl_idname = "view3d.vr_landmark_remove"
    bl_label = "Remove VR Landmark"
    bl_description = "Delete the selected VR landmark from the list"
    bl_options = {'UNDO', 'REGISTER'}

    def execute(self, context):
        scene = context.scene
        landmarks = scene.vr_landmarks

        if len(landmarks) > 1:
            landmark_selected_idx = scene.vr_landmarks_selected
            landmarks.remove(landmark_selected_idx)

            scene.vr_landmarks_selected -= 1

        return {'FINISHED'}


class VIEW3D_OT_cursor_to_vr_landmark(Operator):
    bl_idname = "view3d.cursor_to_vr_landmark"
    bl_label = "Cursor to VR Landmark"
    bl_description = "Move the 3D Cursor to the selected VR Landmark"
    bl_options = {'UNDO', 'REGISTER'}

    @classmethod
    def poll(cls, context):
        lm = properties.VRLandmark.get_selected_landmark(context)
        if lm.type == 'SCENE_CAMERA':
            return context.scene.camera is not None
        elif lm.type == 'OBJECT':
            return lm.base_pose_object is not None

        return True

    def execute(self, context):
        scene = context.scene
        lm = properties.VRLandmark.get_selected_landmark(context)
        if lm.type == 'SCENE_CAMERA':
            lm_pos = scene.camera.location
        elif lm.type == 'OBJECT':
            lm_pos = lm.base_pose_object.location
        else:
            lm_pos = lm.base_pose_location
        scene.cursor.location = lm_pos

        return{'FINISHED'}


class VIEW3D_OT_add_camera_from_vr_landmark(Operator):
    bl_idname = "view3d.add_camera_from_vr_landmark"
    bl_label = "New Camera from VR Landmark"
    bl_description = "Create a new Camera from the selected VR Landmark"
    bl_options = {'UNDO', 'REGISTER'}

    def execute(self, context):
        scene = context.scene
        lm = properties.VRLandmark.get_selected_landmark(context)

        cam = bpy.data.cameras.new(data_("Camera") + "_" + lm.name)
        new_cam = bpy.data.objects.new(data_("Camera") + "_" + lm.name, cam)
        scene.collection.objects.link(new_cam)
        angle = lm.base_pose_angle
        new_cam.location = lm.base_pose_location
        new_cam.rotation_euler = (math.pi / 2, 0, angle)

        return {'FINISHED'}


class VIEW3D_OT_camera_to_vr_landmark(Operator):
    bl_idname = "view3d.camera_to_vr_landmark"
    bl_label = "Scene Camera to VR Landmark"
    bl_description = "Position the scene camera at the selected landmark"
    bl_options = {'UNDO', 'REGISTER'}

    @classmethod
    def poll(cls, context):
        return context.scene.camera is not None

    def execute(self, context):
        scene = context.scene
        lm = properties.VRLandmark.get_selected_landmark(context)

        cam = scene.camera
        angle = lm.base_pose_angle
        cam.location = lm.base_pose_location
        cam.rotation_euler = (math.pi / 2, 0, angle)

        return {'FINISHED'}


class VIEW3D_OT_vr_landmark_activate(Operator):
    bl_idname = "view3d.vr_landmark_activate"
    bl_label = "Activate VR Landmark"
    bl_description = "Change to the selected VR landmark from the list"
    bl_options = {'UNDO', 'REGISTER'}

    index: bpy.props.IntProperty(
        name="Index",
        options={'HIDDEN'},
    )

    def execute(self, context):
        scene = context.scene

        if self.index >= len(scene.vr_landmarks):
            return {'CANCELLED'}

        scene.vr_landmarks_active = (
            self.index if self.properties.is_property_set(
                "index") else scene.vr_landmarks_selected
        )

        return {'FINISHED'}


### VR Visibility Overlay — multiple solid-color meshes parented to empty.
import time, traceback as _tb

_vr_visibility_modal_running = False
_vr_panel_scroll_offset = 0
_vr_panel_hit = {"panel_w": 0.35, "panel_h": 0.35, "row_h": 0.035,
                 "header_h": 0.06, "scroll_btn_h": 0.028,
                 "count": 0, "n": 0, "scroll_offset": 0}
_vr_panel_parent_name = "__VR_PANEL__"
_vr_panel_names = []  # list of child mesh names
_vr_panel_objects = []  # cached filtered object list for index stability
_vr_update_handle = None
_vr_flash_row = -1
_vr_flash_offset = -1
_vr_cursor_hover_row = -1
_vr_cursor_obj = None
_vr_cursor_handle = None
_vr_mat_cache = {}

def _vr_log(msg):
    try:
        with open("C:\\Users\\Administrator\\VR\\opencode_vr_log.txt", "a") as f:
            f.write(f"[{time.time():.1f}] {msg}\n")
    except Exception:
        pass

def _vr_haptic_pulse(context):
    try:
        ss = context.window_manager.xr_session_state
        if ss:
            am = ss.actionmaps.find(ss, "blender_default")
            if am:
                ss.haptic_action_apply(context, am.name, "haptic",
                                       0.08, 2000.0, 0.4, 'PRESS', 'ANY')
    except Exception:
        pass

def _vr_get_or_create_mat(name, r, g, b, a=1.0):
    if name in _vr_mat_cache:
        return _vr_mat_cache[name]
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = (r, g, b, a)
    emit.inputs["Strength"].default_value = 3.0
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    if a < 1.0:
        mat.blend_method = 'BLEND'
    mat.use_backface_culling = False
    _vr_mat_cache[name] = mat
    return mat

def _vr_make_quad_mesh(name, x, y, z, w, h):
    mesh = bpy.data.meshes.new(name)
    verts = [(x, y, z), (x+w, y, z), (x+w, y+h, z), (x, y+h, z)]
    faces = [(0, 1, 2, 3)]
    mesh.from_pydata(verts, [], faces)
    return mesh

def _vr_make_tri_mesh(name, x1, y1, x2, y2, x3, y3, z):
    mesh = bpy.data.meshes.new(name)
    verts = [(x1, y1, z), (x2, y2, z), (x3, y3, z)]
    faces = [(0, 1, 2)]
    mesh.from_pydata(verts, [], faces)
    return mesh

def _vr_get_viewer_pose():
    try:
        ss = bpy.context.window_manager.xr_session_state
        if not ss:
            return None, None
        return ss.viewer_pose_location.copy(), ss.viewer_pose_rotation.copy()
    except Exception:
        return None, None

def _vr_get_controller_pose(context, idx=0):
    try:
        ss = context.window_manager.xr_session_state
        if not ss:
            return None, None
        loc = ss.controller_aim_location_get(context, idx)
        rot = ss.controller_aim_rotation_get(context, idx)
        if not isinstance(loc, Vector):
            loc = Vector(loc)
        if not isinstance(rot, Quaternion):
            rot = Quaternion(rot)
        return loc, rot
    except Exception:
        return None, None

def _vr_ray_intersects_plane(ray_origin, ray_dir, plane_point, plane_normal):
    denom = ray_dir.dot(plane_normal)
    if abs(denom) < 1e-6:
        return None
    t = (plane_point - ray_origin).dot(plane_normal) / denom
    if t <= 0:
        return None
    return ray_origin + ray_dir * t

def _vr_update_panel_position():
    p = bpy.data.objects.get(_vr_panel_parent_name)
    if p is None:
        return
    loc, rot = _vr_get_viewer_pose()
    if loc is None:
        return
    fwd = rot @ Vector((0.0, 0.0, -1.0))
    down = rot @ Vector((0.0, -1.0, 0.0))
    pos = loc + fwd * 0.5 + down * 0.05
    mat = rot.to_matrix().to_4x4()
    mat.translation = pos
    p.matrix_world = mat

def _vr_pick_panel_row(context):
    global _vr_panel_hit
    p = bpy.data.objects.get(_vr_panel_parent_name)
    if p is None:
        _vr_log("  PICK: parent not found")
        return -1
    hit = _vr_panel_hit
    if hit.get("n", 0) == 0:
        _vr_log("  PICK: n=0, no objects in panel")
        return -1

    for controller_idx in (0, 1):
        loc, rot = _vr_get_controller_pose(context, controller_idx)
        if loc is None or rot is None:
            _vr_log(f"  PICK: controller[{controller_idx}] pose=None")
            continue

        ray_origin = loc
        ray_dir = rot @ Vector((0.0, 0.0, -1.0))
        panel_mat = p.matrix_world
        panel_center = panel_mat @ Vector((0.0, 0.0, 0.0))
        panel_normal_vec = panel_mat @ Vector((0.0, 0.0, 1.0)) - panel_center
        panel_right = panel_mat @ Vector((1.0, 0.0, 0.0)) - panel_center
        panel_up = panel_mat @ Vector((0.0, 1.0, 0.0)) - panel_center
        panel_normal_n = panel_normal_vec.normalized()
        panel_right_n = panel_right.normalized()
        panel_up_n = panel_up.normalized()

        hit_pt = _vr_ray_intersects_plane(ray_origin, ray_dir, panel_center, panel_normal_n)
        if hit_pt is None:
            dist_to_center = (ray_origin - panel_center).length
            _vr_log(f"  PICK: ctrl[{controller_idx}] miss plane, dist={dist_to_center:.2f}m, ray_dot_n={ray_dir.dot(panel_normal_n):.3f}")
            continue

        local_pt = hit_pt - panel_center
        lx = local_pt.dot(panel_right_n)
        ly = local_pt.dot(panel_up_n)
        hw = hit["panel_w"] / 2.0
        hh = hit["panel_h"] / 2.0
        if not (-hw <= lx <= hw and -hh <= ly <= hh):
            _vr_log(f"  PICK: ctrl[{controller_idx}] outside bounds, lx={lx:.3f} ly={ly:.3f}")
            continue

        row_h = hit["row_h"]
        header_h = hit["header_h"]
        scroll_btn_h = hit["scroll_btn_h"]

        top = hh
        if ly > top - header_h:
            _vr_log(f"  PICK: ctrl[{controller_idx}] header hit -> close")
            return -2
        items_bottom = hh - header_h - hit["count"] * row_h
        arrow_h = hit["scroll_btn_h"] * 1.5
        if ly < items_bottom:
            btn_base = -hh + 0.005
            has_down = hit["scroll_offset"] + hit["count"] < hit["n"]
            has_up = hit["scroll_offset"] > 0
            if has_down:
                if btn_base <= ly <= btn_base + arrow_h:
                    _vr_log(f"  PICK: ctrl[{controller_idx}] pgdn hit")
                    return -3
            up_start = btn_base + (arrow_h + 0.008 if has_down else 0)
            if has_up and up_start <= ly <= up_start + arrow_h:
                _vr_log(f"  PICK: ctrl[{controller_idx}] pgup hit")
                return -4
            _vr_log(f"  PICK: ctrl[{controller_idx}] below items, no scroll hit")
            return -1

        dist_from_top = top - header_h - ly
        row = int(dist_from_top // row_h)
        if row < 0 or row >= hit["count"]:
            continue
        _vr_log(f"  PICK: ctrl[{controller_idx}] row={row} hit")
        return row
    _vr_log("  PICK: no controller hit panel")
    return -1

def _vr_flash_clear(context):
    global _vr_flash_row, _vr_flash_offset
    _vr_flash_row = -1
    if _vr_flash_offset >= 0:
        _vr_build_panel_mesh(context, _vr_flash_offset)
        _vr_flash_offset = -1

def _vr_cursor_cleanup():
    global _vr_cursor_obj
    if _vr_cursor_obj is not None:
        try:
            mesh = _vr_cursor_obj.data
            bpy.data.objects.remove(_vr_cursor_obj, do_unlink=True)
            bpy.data.meshes.remove(mesh)
        except Exception:
            pass
        _vr_cursor_obj = None
    mat = bpy.data.materials.get("__VR_MAT_CURSOR")
    if mat:
        try:
            bpy.data.materials.remove(mat)
        except Exception:
            pass

def _vr_cursor_update(context):
    global _vr_cursor_obj, _vr_cursor_hover_row
    if _vr_cursor_obj and _vr_cursor_obj.name not in bpy.data.objects:
        _vr_cursor_obj = None
    parent = bpy.data.objects.get(_vr_panel_parent_name)
    if parent is None:
        _vr_cursor_cleanup()
        return
    row = _vr_pick_panel_row(context)
    _vr_cursor_hover_row = row

    if row < 0 or row >= _vr_panel_hit["count"]:
        if _vr_cursor_obj:
            _vr_cursor_obj.hide_viewport = True
        return

    hw = _vr_panel_hit["panel_w"] / 2.0
    hh = _vr_panel_hit["panel_h"] / 2.0
    row_h = _vr_panel_hit["row_h"]
    header_h = _vr_panel_hit["header_h"]
    pad = 0.015
    cb_s = 0.025
    y = hh - header_h - row_h - row * row_h

    if _vr_cursor_obj is None:
        mesh = _vr_make_quad_mesh("__VR_PANEL_CURSOR", -hw + pad - 0.003, y, 0.008, cb_s + 0.01, row_h + 0.006)
        mat = _vr_get_or_create_mat("__VR_MAT_CURSOR", 1.0, 0.9, 0.2, 0.45)
        mesh.materials.append(mat)
        _vr_cursor_obj = bpy.data.objects.new("__VR_PANEL_CURSOR", mesh)
        _vr_cursor_obj.parent = parent
        _vr_cursor_obj.hide_select = True
        _vr_cursor_obj.hide_viewport = False
        context.scene.collection.objects.link(_vr_cursor_obj)
    else:
        _vr_cursor_obj.hide_viewport = False
        mesh = _vr_cursor_obj.data
        mesh.vertices[0].co = (-hw + pad - 0.003, y, 0.008)
        mesh.vertices[1].co = (-hw + pad - 0.003 + cb_s + 0.01, y, 0.008)
        mesh.vertices[2].co = (-hw + pad - 0.003 + cb_s + 0.01, y + row_h + 0.006, 0.008)
        mesh.vertices[3].co = (-hw + pad - 0.003, y + row_h + 0.006, 0.008)

def _vr_cursor_poll():
    global _vr_cursor_handle
    try:
        ctx = bpy.context
        if not ctx or not ctx.scene.get("vr_show_visibility_panel", False):
            _vr_cursor_cleanup()
            _vr_cursor_handle = None
            return None
        _vr_cursor_update(ctx)
        return 0.08
    except Exception:
        return 0.08

def _vr_build_panel_mesh(context, offset=0):
    global _vr_panel_hit, _vr_panel_parent_name, _vr_panel_names, _vr_panel_objects, _vr_update_handle
    _vr_clear_panel_mesh()
    try:
        scene = context.scene
        collection = scene.collection
        _vr_panel_objects = [obj for obj in scene.objects
                             if obj.name != _vr_panel_parent_name
                             and not obj.name.startswith("__VR_PANEL_")
                             and getattr(obj, "vr_show_in_panel", True)]
        objects = _vr_panel_objects
        n = len(objects)
        panel_w = _vr_panel_hit["panel_w"]
        panel_h = _vr_panel_hit["panel_h"]
        row_h = _vr_panel_hit["row_h"]
        header_h = _vr_panel_hit["header_h"]
        scroll_btn_h = _vr_panel_hit["scroll_btn_h"]
        pad = 0.015
        cb_s = 0.025
        max_visible = int((panel_h - header_h - scroll_btn_h * 2 - 0.03) / row_h)
        if offset >= n or offset < 0:
            offset = 0
        if max_visible < 1:
            max_visible = 1
        count = min(max_visible, n - offset)
        hw, hh = panel_w / 2, panel_h / 2

        parent = bpy.data.objects.new(_vr_panel_parent_name, None)
        parent.empty_display_type = 'PLAIN_AXES'
        parent.empty_display_size = hw
        collection.objects.link(parent)

        names = []
        def add_quad(name, x, y, z, w, h, mat_name, r, g, b, a=1.0):
            mesh = _vr_make_quad_mesh(name, x, y, z, w, h)
            mat = _vr_get_or_create_mat(mat_name, r, g, b, a)
            mesh.materials.append(mat)
            obj = bpy.data.objects.new(name, mesh)
            obj.parent = parent
            collection.objects.link(obj)
            names.append(name)

        def add_tri(name, x1, y1, x2, y2, x3, y3, z, mat_name, r, g, b):
            mesh = _vr_make_tri_mesh(name, x1, y1, x2, y2, x3, y3, z)
            mat = _vr_get_or_create_mat(mat_name, r, g, b)
            mesh.materials.append(mat)
            obj = bpy.data.objects.new(name, mesh)
            obj.parent = parent
            collection.objects.link(obj)
            names.append(name)

        def add_text(name, x, y, text, r, g, b):
            curve = bpy.data.curves.new(name, 'FONT')
            curve.body = text
            curve.extrude = 0.0  # perfectly flat: eliminates stereo ghosting
            curve.resolution_u = 5
            mat = _vr_get_or_create_mat(name + "_mat", r, g, b, 1.0)
            mat.use_backface_culling = False
            curve.materials.append(mat)
            obj = bpy.data.objects.new(name, curve)
            obj.parent = parent
            obj.location = (x, y, 0.01)  # far in front of all quads
            obj.scale = (0.022, 0.022, 1.0)
            obj.rotation_euler = (0, 0, 0)
            collection.objects.link(obj)
            names.append(name)

        total_pages = (n + count - 1) // count if count > 0 else 1
        cur_page = offset // count + 1 if count > 0 else 1
        header_text = f"Objects ({n} total)  pg {cur_page}/{total_pages}"

        add_quad("__VR_PANEL_BG", -hw, -hh, -0.004, panel_w, panel_h, "__VR_MAT_BG", 0.06, 0.06, 0.1, 0.85)
        add_text("__VR_PANEL_TITLE", -hw + pad, hh - header_h * 0.8, header_text, 0.8, 0.8, 0.85)

        y_top = hh - header_h - row_h
        for i in range(count):
            obj = objects[offset + i]
            cy = y_top - i * row_h
            is_flash = (_vr_flash_row >= 0 and offset == _vr_flash_offset and i == _vr_flash_row)
            if is_flash:
                add_quad(f"__VR_PANEL_CB_{i}", -hw + pad, cy, -0.001, cb_s, cb_s, "__VR_MAT_FLASH", 1.0, 0.9, 0.15)
            elif obj.hide_viewport:
                add_quad(f"__VR_PANEL_CB_{i}", -hw + pad, cy, -0.001, cb_s, cb_s, "__VR_MAT_CB_OFF", 0.85, 0.15, 0.15)
            else:
                add_quad(f"__VR_PANEL_CB_{i}", -hw + pad, cy, -0.001, cb_s, cb_s, "__VR_MAT_CB_ON", 0.1, 0.9, 0.1)
            tx = -hw + pad + cb_s + 0.01
            add_text(f"__VR_PANEL_TXT_{i}", tx, cy + cb_s * 0.5, obj.name[:25], 0.75, 0.75, 0.8)

        arrow_h = scroll_btn_h * 1.5
        arrow_w = 0.04
        btn_bottom = -hh + 0.005
        if offset + count < n:
            add_tri("__VR_PANEL_SCDN", 0, btn_bottom, -arrow_w, btn_bottom + arrow_h, arrow_w, btn_bottom + arrow_h, 0, "__VR_MAT_SCROLL", 0.9, 0.7, 0.2)
            add_text("__VR_PANEL_SCDN_LBL", arrow_w + 0.005, btn_bottom + arrow_h * 0.3, "PgDn", 0.9, 0.7, 0.2)
            btn_bottom += arrow_h + 0.008
        if offset > 0:
            add_tri("__VR_PANEL_SCUP", 0, btn_bottom, -arrow_w, btn_bottom + arrow_h, arrow_w, btn_bottom + arrow_h, 0, "__VR_MAT_SCROLL", 0.3, 0.9, 0.3)
            add_text("__VR_PANEL_SCUP_LBL", arrow_w + 0.005, btn_bottom + arrow_h * 0.3, "PgUp", 0.3, 0.9, 0.3)

        _vr_panel_names = names

        loc, rot = _vr_get_viewer_pose()
        if loc is not None:
            fwd = rot @ Vector((0.0, 0.0, -1.0))
            down = rot @ Vector((0.0, -1.0, 0.0))
            pos = loc + fwd * 0.5 + down * 0.05
            rmat = rot.to_matrix().to_4x4()
            rmat.translation = pos
            parent.matrix_world = rmat
            _vr_log(f"PANEL BUILD: positioned at viewer+0.5m down+0.05m")
        else:
            parent.location = (0, 0, -2)
            _vr_log("PANEL BUILD: no viewer pose, placed at (0,0,-2)")

        if _vr_update_handle is None:
            _vr_update_handle = bpy.types.SpaceView3D.draw_handler_add(
                _vr_update_panel_position, (), 'WINDOW', 'POST_PIXEL')
            _vr_log("PANEL BUILD: position update handler registered")

        _vr_panel_hit["count"] = count
        _vr_panel_hit["n"] = n
        _vr_panel_hit["scroll_offset"] = offset
        pnames = ", ".join(f"[{offset+i}]={obj.name}" for i, obj in enumerate(objects[offset:offset+count]))
        _vr_log(f"PANEL: {len(names)} meshes, {count}/{n} items, offset={offset}")
        _vr_log(f"PANEL objs: {pnames}")
        return parent
    except Exception:
        _vr_log(f"PANEL BUILD ERROR:\n{_tb.format_exc()}")
        return None


def _vr_clear_panel_mesh():
    global _vr_update_handle, _vr_panel_parent_name, _vr_panel_names, _vr_mat_cache, _vr_cursor_handle
    _vr_cursor_cleanup()
    if _vr_cursor_handle is not None:
        try:
            bpy.app.timers.unregister(_vr_cursor_handle)
        except Exception:
            pass
        _vr_cursor_handle = None
    if _vr_update_handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_vr_update_handle, 'WINDOW')
        except Exception:
            pass
        _vr_update_handle = None

    parent = bpy.data.objects.get(_vr_panel_parent_name)
    if parent:
        for child in list(parent.children):
            try:
                bpy.data.objects.remove(child, do_unlink=True)
            except Exception:
                pass
        try:
            bpy.data.objects.remove(parent, do_unlink=True)
        except Exception:
            pass

    for name in list(_vr_panel_names):
        mesh = bpy.data.meshes.get(name)
        if mesh:
            try:
                bpy.data.meshes.remove(mesh)
            except Exception:
                pass
        curve = bpy.data.curves.get(name)
        if curve:
            try:
                bpy.data.curves.remove(curve)
            except Exception:
                pass
    _vr_panel_names = []

    for mat_name in list(_vr_mat_cache.keys()):
        mat = bpy.data.materials.get(mat_name)
        if mat:
            try:
                bpy.data.materials.remove(mat)
            except Exception:
                pass
    _vr_mat_cache = {}
    _vr_log("PANEL: cleared")


class VIEW3D_OT_vr_toggle_visibility(Operator):
    bl_idname = "view3d.vr_toggle_visibility"
    bl_label = "Toggle VR Visibility Panel"
    bl_description = "Open/close the object visibility overlay in the VR view"
    bl_options = {'REGISTER'}

    def execute(self, context):
        global _vr_visibility_modal_running, _vr_panel_scroll_offset, _vr_cursor_handle
        scene = context.scene
        if scene.vr_show_visibility_panel:
            scene.vr_show_visibility_panel = False
            _vr_visibility_modal_running = False
            _vr_cursor_cleanup()
            if _vr_cursor_handle:
                try:
                    bpy.app.timers.unregister(_vr_cursor_handle)
                except Exception:
                    pass
                _vr_cursor_handle = None
            _vr_clear_panel_mesh()
            _vr_log("OP: panel closed (toggle)")
            return {'FINISHED'}
        try:
            _vr_panel_scroll_offset = 0
            scene.vr_show_visibility_panel = True
            _vr_visibility_modal_running = True
            _vr_build_panel_mesh(context)
            if _vr_cursor_handle is None:
                _vr_cursor_handle = bpy.app.timers.register(_vr_cursor_poll, first_interval=0.05)
            _vr_log("OP: panel opened (toggle)")
            return {'FINISHED'}
        except Exception:
            _vr_log(f"OP execute ERROR:\n{_tb.format_exc()}")
            return {'CANCELLED'}

    def invoke(self, context, event):
        return self.execute(context)


class VIEW3D_OT_vr_select_item(Operator):
    bl_idname = "view3d.vr_select_item"
    bl_label = "Select VR Panel Item"
    bl_description = "Toggle visibility of the object the VR controller is pointing at"
    bl_options = {'REGISTER'}

    def execute(self, context):
        global _vr_panel_scroll_offset
        scene = context.scene
        if not scene.vr_show_visibility_panel:
            return {'CANCELLED'}

        try:
            row = _vr_cursor_hover_row
            _vr_log(f"OP select: hover row={row}")
            if row == -2:
                _vr_log("OP select: header — close panel")
                scene.vr_show_visibility_panel = False
                _vr_visibility_modal_running = False
                _vr_clear_panel_mesh()
                _vr_haptic_pulse(context)
                return {'FINISHED'}

            if row == -3:
                new_offset = _vr_panel_hit["scroll_offset"] + _vr_panel_hit["count"]
                if new_offset < _vr_panel_hit["n"]:
                    _vr_panel_scroll_offset = new_offset
                    _vr_build_panel_mesh(context, _vr_panel_scroll_offset)
                _vr_haptic_pulse(context)
                return {'FINISHED'}

            if row == -4:
                new_offset = max(0, _vr_panel_hit["scroll_offset"] - _vr_panel_hit["count"])
                _vr_panel_scroll_offset = new_offset
                _vr_build_panel_mesh(context, _vr_panel_scroll_offset)
                _vr_haptic_pulse(context)
                return {'FINISHED'}

            if row < 0 or row >= _vr_panel_hit["count"]:
                return {'PASS_THROUGH'}

            oi = _vr_panel_hit["scroll_offset"] + row
            if oi < len(_vr_panel_objects):
                global _vr_flash_row, _vr_flash_offset
                _vr_flash_row = row
                _vr_flash_offset = _vr_panel_hit["scroll_offset"]
                _vr_panel_objects[oi].hide_viewport ^= True
                _vr_log(f"OP select: toggled '{_vr_panel_objects[oi].name}'")
                _vr_build_panel_mesh(context, _vr_panel_hit["scroll_offset"])
                _vr_haptic_pulse(context)
                bpy.app.timers.register(lambda: _vr_flash_clear(bpy.context), first_interval=0.15)
            return {'FINISHED'}
        except Exception:
            _vr_log(f"OP select ERROR:\n{_tb.format_exc()}")
            return {'CANCELLED'}


class VIEW3D_OT_vr_select_all(Operator):
    bl_idname = "view3d.vr_select_all"
    bl_label = "Select VR Panel Objects"
    bl_description = "Select all, none, or currently selected objects for VR panel"
    bl_options = {'REGISTER', 'UNDO'}

    action: bpy.props.StringProperty(name="Action",
        options={'HIDDEN'}, default='ALL')

    def execute(self, context):
        scene = context.scene
        val = True if self.action == 'ALL' else False
        for obj in scene.objects:
            if self.action == 'SELECTED':
                if obj.select_get():
                    obj.vr_show_in_panel = True
            else:
                obj.vr_show_in_panel = val
        return {'FINISHED'}


### Gizmos.
class VIEW3D_GT_vr_camera_cone(Gizmo):
    bl_idname = "VIEW_3D_GT_vr_camera_cone"

    aspect = 1.0, 1.0

    def draw(self, context):
        if not hasattr(self, "frame_shape"):
            aspect = self.aspect

            frame_shape_verts = (
                (-aspect[0], -aspect[1], -1.0),
                (aspect[0], -aspect[1], -1.0),
                (aspect[0], aspect[1], -1.0),
                (-aspect[0], aspect[1], -1.0),
            )
            lines_shape_verts = (
                (0.0, 0.0, 0.0),
                frame_shape_verts[0],
                (0.0, 0.0, 0.0),
                frame_shape_verts[1],
                (0.0, 0.0, 0.0),
                frame_shape_verts[2],
                (0.0, 0.0, 0.0),
                frame_shape_verts[3],
            )

            self.frame_shape = self.new_custom_shape(
                'LINE_LOOP', frame_shape_verts)
            self.lines_shape = self.new_custom_shape(
                'LINES', lines_shape_verts)

        gpu.state.line_width_set(1.0)
        gpu.state.blend_set('ALPHA')

        self.draw_custom_shape(self.frame_shape)
        self.draw_custom_shape(self.lines_shape)


class VIEW3D_GT_vr_controller_grip(Gizmo):
    bl_idname = "VIEW_3D_GT_vr_controller_grip"

    def draw(self, context):
        gpu.state.line_width_set(1.0)
        gpu.state.blend_set('ALPHA')

        self.color = 0.422, 0.438, 0.446
        self.draw_preset_circle(self.matrix_basis, axis='POS_X')
        self.draw_preset_circle(self.matrix_basis, axis='POS_Y')
        self.draw_preset_circle(self.matrix_basis, axis='POS_Z')


class VIEW3D_GT_vr_controller_aim(Gizmo):
    bl_idname = "VIEW_3D_GT_vr_controller_aim"

    def draw(self, context):
        gpu.state.line_width_set(1.0)
        gpu.state.blend_set('ALPHA')

        self.color = 1.0, 0.2, 0.322
        self.draw_preset_arrow(self.matrix_basis, axis='POS_X')
        self.color = 0.545, 0.863, 0.0
        self.draw_preset_arrow(self.matrix_basis, axis='POS_Y')
        self.color = 0.157, 0.565, 1.0
        self.draw_preset_arrow(self.matrix_basis, axis='POS_Z')


class VIEW3D_GGT_vr_viewer_pose(GizmoGroup):
    bl_idname = "VIEW3D_GGT_vr_viewer_pose"
    bl_label = "VR Viewer Pose Indicator"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'3D', 'PERSISTENT', 'SCALE', 'VR_REDRAWS'}

    @classmethod
    def poll(cls, context):
        view3d = context.space_data
        return (
            view3d.shading.vr_show_virtual_camera and
            bpy.types.XrSessionState.is_running(context) and
            not view3d.mirror_xr_session
        )

    @staticmethod
    def _get_viewer_pose_matrix(context):
        wm = context.window_manager
        loc = wm.xr_session_state.viewer_pose_location
        rot = wm.xr_session_state.viewer_pose_rotation
        rotmat = rot.to_matrix().to_4x4()
        rotmat.translation = loc
        return rotmat

    def setup(self, context):
        gizmo = self.gizmos.new(VIEW3D_GT_vr_camera_cone.bl_idname)
        gizmo.aspect = 1 / 3, 1 / 4

        gizmo.color = gizmo.color_highlight = 0.2, 0.6, 1.0
        gizmo.alpha = 1.0

        self.gizmo = gizmo

    def draw_prepare(self, context):
        self.gizmo.matrix_basis = self._get_viewer_pose_matrix(context)


class VIEW3D_GGT_vr_controller_poses(GizmoGroup):
    bl_idname = "VIEW3D_GGT_vr_controller_poses"
    bl_label = "VR Controller Poses Indicator"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'3D', 'PERSISTENT', 'SCALE', 'VR_REDRAWS'}

    @classmethod
    def poll(cls, context):
        view3d = context.space_data
        return (
            view3d.shading.vr_show_controllers and
            bpy.types.XrSessionState.is_running(context) and
            not view3d.mirror_xr_session
        )

    @staticmethod
    def _get_controller_pose_matrix(context, idx, is_grip, scale_mat):
        wm = context.window_manager
        if is_grip:
            loc = wm.xr_session_state.controller_grip_location_get(context, idx)
            rot = wm.xr_session_state.controller_grip_rotation_get(context, idx)
        else:
            loc = wm.xr_session_state.controller_aim_location_get(context, idx)
            rot = wm.xr_session_state.controller_aim_rotation_get(context, idx)

        rotmat = rot.to_matrix().to_4x4()
        rotmat.translation = loc
        return rotmat @ scale_mat

    def setup(self, context):
        self._grip_gizmos = []
        self._aim_gizmos = []
        for idx in range(2):
            g = self.gizmos.new(VIEW3D_GT_vr_controller_grip.bl_idname)
            g.aspect = 1 / 3, 1 / 4
            g.color_highlight = 1.0, 1.0, 1.0
            g.alpha = 1.0
            self._grip_gizmos.append(g)

            a = self.gizmos.new(VIEW3D_GT_vr_controller_aim.bl_idname)
            a.aspect = 1 / 3, 1 / 4
            a.color_highlight = 1.0, 1.0, 1.0
            a.alpha = 1.0
            self._aim_gizmos.append(a)

    def draw_prepare(self, context):
        for idx, gizmo in enumerate(self._grip_gizmos):
            gizmo.matrix_basis = self._get_controller_pose_matrix(
                context, idx, True, _SCALE_01)
        for idx, gizmo in enumerate(self._aim_gizmos):
            gizmo.matrix_basis = self._get_controller_pose_matrix(
                context, idx, False, _SCALE_05)


class VIEW3D_GGT_vr_landmarks(GizmoGroup):
    bl_idname = "VIEW3D_GGT_vr_landmarks"
    bl_label = "VR Landmark Indicators"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'3D', 'PERSISTENT', 'SCALE'}

    @classmethod
    def poll(cls, context):
        view3d = context.space_data
        return (
            view3d.shading.vr_show_landmarks
        )

    def setup(self, context):
        self._landmark_gizmos = []
        self._landmark_count = -1

    def draw_prepare(self, context):
        scene = context.scene
        landmarks = scene.vr_landmarks

        # Only rebuild gizmo list when landmarks actually change.
        if len(landmarks) != self._landmark_count:
            for g in self._landmark_gizmos:
                self.gizmos.remove(g)
            self._landmark_gizmos.clear()

            for lm in landmarks:
                gizmo = self.gizmos.new(VIEW3D_GT_vr_camera_cone.bl_idname)
                gizmo.aspect = 1 / 3, 1 / 4
                gizmo.color = gizmo.color_highlight = 0.2, 1.0, 0.6
                gizmo.alpha = 1.0
                self._landmark_gizmos.append(gizmo)

            self._landmark_count = len(landmarks)
            if self._landmark_count == 0:
                return

        for lm, gizmo in zip(landmarks, self._landmark_gizmos):
            if ((lm.type == 'SCENE_CAMERA' and not scene.camera) or
                    (lm.type == 'OBJECT' and not lm.base_pose_object)):
                gizmo.hide = True
                continue
            gizmo.hide = False

            if lm.type == 'SCENE_CAMERA':
                cam = scene.camera
                gizmo.matrix_basis = cam.matrix_world if cam else _IDENTITY_4X4
            elif lm.type == 'OBJECT':
                gizmo.matrix_basis = lm.base_pose_object.matrix_world
            else:
                angle = lm.base_pose_angle
                raw_rot = Euler((radians(90.0), 0, angle))
                rotmat = raw_rot.to_matrix().to_4x4()
                rotmat.translation = lm.base_pose_location
                gizmo.matrix_basis = rotmat


classes = (
    VIEW3D_OT_vr_landmark_add,
    VIEW3D_OT_vr_landmark_remove,
    VIEW3D_OT_vr_landmark_activate,
    VIEW3D_OT_vr_landmark_from_session,
    VIEW3D_OT_vr_camera_landmark_from_session,
    VIEW3D_OT_add_camera_from_vr_landmark,
    VIEW3D_OT_camera_to_vr_landmark,
    VIEW3D_OT_vr_landmark_from_camera,
    VIEW3D_OT_cursor_to_vr_landmark,
    VIEW3D_OT_update_vr_landmark,
    VIEW3D_OT_vr_toggle_visibility,
    VIEW3D_OT_vr_select_item,
    VIEW3D_OT_vr_select_all,

    VIEW3D_GT_vr_camera_cone,
    VIEW3D_GT_vr_controller_grip,
    VIEW3D_GT_vr_controller_aim,
    VIEW3D_GGT_vr_viewer_pose,
    VIEW3D_GGT_vr_controller_poses,
    VIEW3D_GGT_vr_landmarks,
)


def _register_safe(cls):
    try:
        bpy.utils.register_class(cls)
    except ValueError:
        print(f"VR: class {cls.__name__} already registered, skipping")


def _unregister_safe(cls):
    try:
        bpy.utils.unregister_class(cls)
    except Exception:
        pass


def register():
    for cls in classes:
        _register_safe(cls)


def unregister():
    _vr_clear_panel_mesh()
    for cls in classes:
        _unregister_safe(cls)

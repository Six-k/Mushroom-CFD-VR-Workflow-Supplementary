# SPDX-FileCopyrightText: 2021-2022 Blender Foundation
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from bpy.types import (
    PropertyGroup,
)
from bpy.app.handlers import persistent


### Landmarks.
@persistent
def vr_ensure_default_landmark(context: bpy.context):
    landmarks = bpy.context.scene.vr_landmarks
    if not landmarks:
        landmarks.add()
        landmarks[0].type = 'SCENE_CAMERA'


def vr_landmark_active_type_update(self, context):
    wm = context.window_manager
    session_settings = wm.xr_session_settings
    landmark_active = VRLandmark.get_active_landmark(context)

    if landmark_active.type == 'SCENE_CAMERA':
        session_settings.base_pose_type = 'SCENE_CAMERA'
    elif landmark_active.type == 'OBJECT':
        session_settings.base_pose_type = 'OBJECT'
    elif landmark_active.type == 'CUSTOM':
        session_settings.base_pose_type = 'CUSTOM'


def vr_landmark_active_base_pose_object_update(self, context):
    session_settings = context.window_manager.xr_session_settings
    landmark_active = VRLandmark.get_active_landmark(context)

    session_settings.base_pose_object = landmark_active.base_pose_object


def vr_landmark_active_base_pose_location_update(self, context):
    session_settings = context.window_manager.xr_session_settings
    landmark_active = VRLandmark.get_active_landmark(context)

    session_settings.base_pose_location = landmark_active.base_pose_location


def vr_landmark_active_base_pose_angle_update(self, context):
    session_settings = context.window_manager.xr_session_settings
    landmark_active = VRLandmark.get_active_landmark(context)

    session_settings.base_pose_angle = landmark_active.base_pose_angle


def vr_landmark_active_base_scale_update(self, context):
    session_settings = context.window_manager.xr_session_settings
    landmark_active = VRLandmark.get_active_landmark(context)

    session_settings.base_scale = landmark_active.base_scale


def vr_landmark_type_update(self, context):
    landmark_selected = VRLandmark.get_selected_landmark(context)
    landmark_active = VRLandmark.get_active_landmark(context)

    if landmark_selected.type == 'SCENE_CAMERA':
        landmark_selected.base_scale = 1.0

    if landmark_active == landmark_selected:
        vr_landmark_active_type_update(self, context)


def vr_landmark_base_pose_object_update(self, context):
    landmark_selected = VRLandmark.get_selected_landmark(context)
    landmark_active = VRLandmark.get_active_landmark(context)

    if landmark_active == landmark_selected:
        vr_landmark_active_base_pose_object_update(self, context)


def vr_landmark_base_pose_location_update(self, context):
    landmark_selected = VRLandmark.get_selected_landmark(context)
    landmark_active = VRLandmark.get_active_landmark(context)

    if landmark_active == landmark_selected:
        vr_landmark_active_base_pose_location_update(self, context)


def vr_landmark_base_pose_angle_update(self, context):
    landmark_selected = VRLandmark.get_selected_landmark(context)
    landmark_active = VRLandmark.get_active_landmark(context)

    if landmark_active == landmark_selected:
        vr_landmark_active_base_pose_angle_update(self, context)


def vr_landmark_base_scale_update(self, context):
    landmark_selected = VRLandmark.get_selected_landmark(context)
    landmark_active = VRLandmark.get_active_landmark(context)

    if landmark_active == landmark_selected:
        vr_landmark_active_base_scale_update(self, context)


def vr_landmark_active_update(self, context):
    wm = context.window_manager

    vr_landmark_active_type_update(self, context)
    vr_landmark_active_base_pose_object_update(self, context)
    vr_landmark_active_base_pose_location_update(self, context)
    vr_landmark_active_base_pose_angle_update(self, context)
    vr_landmark_active_base_scale_update(self, context)

    if wm.xr_session_state:
        wm.xr_session_state.reset_to_base_pose(context)


class VRLandmark(PropertyGroup):
    name: bpy.props.StringProperty(
        name="VR Landmark",
        default="Landmark"
    )
    type: bpy.props.EnumProperty(
        name="Type",
        items=[
            ('SCENE_CAMERA', "Scene Camera",
             "Use scene's currently active camera to define the VR view base "
             "location and rotation"),
            ('OBJECT', "Custom Object",
             "Use an existing object to define the VR view base location and "
             "rotation"),
            ('CUSTOM', "Custom Pose",
             "Allow a manually defined position and rotation to be used as "
             "the VR view base pose"),
        ],
        default='SCENE_CAMERA',
        update=vr_landmark_type_update,
    )
    base_pose_object: bpy.props.PointerProperty(
        name="Object",
        type=bpy.types.Object,
        update=vr_landmark_base_pose_object_update,
    )
    base_pose_location: bpy.props.FloatVectorProperty(
        name="Base Pose Location",
        subtype='TRANSLATION',
        update=vr_landmark_base_pose_location_update,
    )
    base_pose_angle: bpy.props.FloatProperty(
        name="Base Pose Angle",
        subtype='ANGLE',
        update=vr_landmark_base_pose_angle_update,
    )
    base_scale: bpy.props.FloatProperty(
        name="Base Scale",
        description="Viewer reference scale associated with this landmark",
        default=1.0,
        min=0.000001,
        update=vr_landmark_base_scale_update,
    )

    @staticmethod
    def get_selected_landmark(context):
        scene = context.scene
        landmarks = scene.vr_landmarks

        return (
            None if (len(landmarks) <
                     1) else landmarks[scene.vr_landmarks_selected]
        )

    @staticmethod
    def get_active_landmark(context):
        scene = context.scene
        landmarks = scene.vr_landmarks

        return (
            None if (len(landmarks) <
                     1) else landmarks[scene.vr_landmarks_active]
        )


classes = (
    VRLandmark,
)


def _reg_safe(cls):
    try:
        bpy.utils.register_class(cls)
    except ValueError:
        pass

def _unreg_safe(cls):
    try:
        bpy.utils.unregister_class(cls)
    except Exception:
        pass


def register():
    for cls in classes:
        _reg_safe(cls)

    bpy.types.Object.vr_show_in_panel = bpy.props.BoolProperty(
        name="Show in VR Panel",
        description="Include this object in the VR visibility panel overlay",
        default=True,
    )

    bpy.types.Scene.vr_landmarks = bpy.props.CollectionProperty(
        name="Landmark",
        type=VRLandmark,
    )
    bpy.types.Scene.vr_landmarks_selected = bpy.props.IntProperty(
        name="Selected Landmark"
    )
    bpy.types.Scene.vr_landmarks_active = bpy.props.IntProperty(
        update=vr_landmark_active_update,
    )
    bpy.types.Scene.vr_show_visibility_panel = bpy.props.BoolProperty(
        name="Show VR Visibility Panel",
        description="Show the object visibility overlay panel in the VR view",
        default=False,
    )

    bpy.app.handlers.load_post.append(vr_ensure_default_landmark)


def unregister():
    for cls in classes:
        _unreg_safe(cls)

    del bpy.types.Object.vr_show_in_panel
    del bpy.types.Scene.vr_landmarks
    del bpy.types.Scene.vr_landmarks_selected
    del bpy.types.Scene.vr_landmarks_active
    del bpy.types.Scene.vr_show_visibility_panel

    bpy.app.handlers.load_post.remove(vr_ensure_default_landmark)

# SPDX-FileCopyrightText: 2021-2023 Blender Foundation
#
# SPDX-License-Identifier: GPL-2.0-or-later

if "bpy" in locals():
    import importlib
    importlib.reload(properties)
else:
    from . import properties

import bpy
from bpy.app.translations import pgettext_iface as iface_
from bpy.types import (
    Menu,
    Panel,
    UIList,
)
from bl_ui.space_view3d import VIEW3D_PT_object_type_visibility


### Session.
class VIEW3D_PT_vr_session(Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "VR"
    bl_label = "VR Session"

    def draw(self, context):
        layout = self.layout
        session_settings = context.window_manager.xr_session_settings
        scene = context.scene

        layout.use_property_split = True
        layout.use_property_decorate = False  # No animation.

        is_session_running = bpy.types.XrSessionState.is_running(context)

        toggle_info = ((iface_("Start VR Session"), 'PLAY') if not is_session_running
                       else (iface_("Stop VR Session"), 'SNAP_FACE'))
        layout.operator("wm.xr_session_toggle", text=toggle_info[0],
                        translate=False, icon=toggle_info[1])

        layout.separator()

        col = layout.column(align=True, heading="Tracking")
        col.prop(session_settings, "use_positional_tracking", text="Positional")
        col.prop(session_settings, "use_absolute_tracking", text="Absolute")

        col = layout.column(align=True, heading="Actions")
        col.prop(scene, "vr_actions_enable")


### View.
class VIEW3D_PT_vr_session_view(Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "VR"
    bl_label = "View"

    def draw(self, context):
        layout = self.layout
        session_settings = context.window_manager.xr_session_settings

        layout.use_property_split = True
        layout.use_property_decorate = False  # No animation.

        col = layout.column(align=True, heading="Show")
        col.prop(session_settings, "show_floor", text="Floor")
        col.prop(session_settings, "show_annotation", text="Annotations")

        col.prop(session_settings, "show_selection", text="Selection")
        col.prop(session_settings, "show_controllers", text="Controllers")
        col.prop(session_settings, "show_custom_overlays", text="Custom Overlays")
        col.prop(session_settings, "show_object_extras", text="Object Extras")

        col = col.row(align=True, heading=" ")
        col.scale_x = 2.0
        col.popover(
            panel="VIEW3D_PT_vr_session_view_object_type_visibility",
            icon_value=session_settings.icon_from_show_object_viewport,
            text="",
        )

        col = layout.column(align=True)
        col.prop(session_settings, "controller_draw_style", text="Controller Style")

        col = layout.column(align=True)
        col.prop(session_settings, "clip_start", text="Clip Start")
        col.prop(session_settings, "clip_end", text="End")


class VIEW3D_PT_vr_session_view_object_type_visibility(VIEW3D_PT_object_type_visibility):
    def draw(self, context):
        session_settings = context.window_manager.xr_session_settings
        self.draw_ex(context, session_settings, False)


### Landmarks.
class VIEW3D_MT_vr_landmark_menu(Menu):
    bl_label = "Landmark Controls"

    def draw(self, _context):
        layout = self.layout

        layout.operator("view3d.vr_camera_landmark_from_session")
        layout.operator("view3d.vr_landmark_from_camera")
        layout.operator("view3d.update_vr_landmark")
        layout.separator()
        layout.operator("view3d.cursor_to_vr_landmark")
        layout.operator("view3d.camera_to_vr_landmark")
        layout.operator("view3d.add_camera_from_vr_landmark")


class VIEW3D_UL_vr_landmarks(UIList):
    def draw_item(self, context, layout, _data, item, icon, _active_data,
                  _active_propname, index):
        landmark = item
        landmark_active_idx = context.scene.vr_landmarks_active

        layout.emboss = 'NONE'

        layout.prop(landmark, "name", text="")

        icon = (
            'RADIOBUT_ON' if (index == landmark_active_idx) else 'RADIOBUT_OFF'
        )
        props = layout.operator(
            "view3d.vr_landmark_activate", text="", icon=icon)
        props.index = index


class VIEW3D_PT_vr_landmarks(Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "VR"
    bl_label = "Landmarks"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        landmark_selected = properties.VRLandmark.get_selected_landmark(context)

        layout.use_property_split = True
        layout.use_property_decorate = False  # No animation.

        row = layout.row()

        row.template_list("VIEW3D_UL_vr_landmarks", "", scene, "vr_landmarks",
                          scene, "vr_landmarks_selected", rows=3)

        col = row.column(align=True)
        col.operator("view3d.vr_landmark_add", icon='ADD', text="")
        col.operator("view3d.vr_landmark_remove", icon='REMOVE', text="")
        col.operator("view3d.vr_landmark_from_session", icon='PLUS', text="")

        col.menu("VIEW3D_MT_vr_landmark_menu", icon='DOWNARROW_HLT', text="")

        if landmark_selected:
            layout.prop(landmark_selected, "type")

            if landmark_selected.type == 'OBJECT':
                layout.prop(landmark_selected, "base_pose_object")
                layout.prop(landmark_selected, "base_scale", text="Scale")
            elif landmark_selected.type == 'CUSTOM':
                layout.prop(landmark_selected,
                            "base_pose_location", text="Location")
                layout.prop(landmark_selected,
                            "base_pose_angle", text="Angle")
                layout.prop(landmark_selected,
                            "base_scale", text="Scale")


### Actions.
class VIEW3D_PT_vr_actionmaps(Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "VR"
    bl_label = "Action Maps"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.use_property_split = True
        layout.use_property_decorate = False  # No animation.

        col = layout.column(align=True)
        col.prop(scene, "vr_actions_use_gamepad", text="Gamepad")

        col = layout.column(align=True, heading="Extensions")
        col.prop(scene, "vr_actions_enable_reverb_g2", text="HP Reverb G2")
        col.prop(scene, "vr_actions_enable_vive_cosmos", text="HTC Vive Cosmos")
        col.prop(scene, "vr_actions_enable_vive_focus", text="HTC Vive Focus")
        col.prop(scene, "vr_actions_enable_huawei", text="Huawei")


### Viewport feedback.
class VIEW3D_PT_vr_viewport_feedback(Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "VR"
    bl_label = "Viewport Feedback"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        view3d = context.space_data
        session_settings = context.window_manager.xr_session_settings

        col = layout.column(align=True)
        col.label(icon='ERROR', text="Note:")
        col.label(text="Settings here may have a significant")
        col.label(text="performance impact!")

        layout.separator()

        layout.prop(view3d.shading, "vr_show_virtual_camera")
        layout.prop(view3d.shading, "vr_show_controllers")
        layout.prop(view3d.shading, "vr_show_landmarks")
        layout.prop(view3d, "mirror_xr_session")


### Object Visibility.
class VIEW3D_PT_vr_object_visibility(Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "VR"
    bl_label = "Object Visibility"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        is_open = scene.vr_show_visibility_panel

        col = layout.column(align=True)
        if is_open:
            col.operator("view3d.vr_toggle_visibility", text="Close Overlay (VR)", icon='HIDE_ON')
        else:
            col.operator("view3d.vr_toggle_visibility", text="Open Overlay (VR)", icon='OVERLAY')

        objects = list(scene.objects)
        vr_count = sum(1 for o in objects if o.vr_show_in_panel)
        total = len(objects)

        col.separator()
        col.label(text=f"VR Panel: {vr_count} / {total} objects")

        row = col.row(align=True)
        op = row.operator("view3d.vr_select_all", text="All", icon='CHECKBOX_HLT')
        op.action = 'ALL'
        op = row.operator("view3d.vr_select_all", text="None", icon='CHECKBOX_DEHLT')
        op.action = 'NONE'
        op = row.operator("view3d.vr_select_all", text="Selected", icon='RESTRICT_SELECT_OFF')
        op.action = 'SELECTED'

        col.separator()

        box = col.box()
        box.scale_y = 0.85
        for obj in objects:
            row = box.row(align=True)
            row.prop(obj, "vr_show_in_panel", text="", icon='HIDE_OFF' if not obj.vr_show_in_panel else 'VIEWZOOM')
            row.prop(obj, "hide_viewport", text="", icon='HIDE_ON' if obj.hide_viewport else 'HIDE_OFF', emboss=False)
            row.label(text=obj.name, icon=f'OUTLINER_OB_{obj.type}' if obj.type in ('MESH','LIGHT','CAMERA','CURVE','EMPTY') else 'OBJECT_DATA')


### Info.
class VIEW3D_PT_vr_info(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "VR"
    bl_label = "VR Info"

    @classmethod
    def poll(cls, context):
        return not bpy.app.build_options.xr_openxr

    def draw(self, context):
        layout = self.layout
        layout.label(icon='ERROR', text="Built without VR/OpenXR features")


classes = (
    VIEW3D_PT_vr_session,
    VIEW3D_PT_vr_session_view,
    VIEW3D_PT_vr_session_view_object_type_visibility,
    VIEW3D_PT_vr_landmarks,
    VIEW3D_PT_vr_actionmaps,
    VIEW3D_PT_vr_viewport_feedback,
    VIEW3D_PT_vr_object_visibility,

    VIEW3D_UL_vr_landmarks,
    VIEW3D_MT_vr_landmark_menu,
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

    bpy.types.View3DShading.vr_show_virtual_camera = bpy.props.BoolProperty(
        name="Show VR Camera"
    )
    bpy.types.View3DShading.vr_show_controllers = bpy.props.BoolProperty(
        name="Show VR Controllers"
    )
    bpy.types.View3DShading.vr_show_landmarks = bpy.props.BoolProperty(
        name="Show Landmarks"
    )


def unregister():
    for cls in classes:
        _unregister_safe(cls)

    del bpy.types.View3DShading.vr_show_virtual_camera
    del bpy.types.View3DShading.vr_show_controllers
    del bpy.types.View3DShading.vr_show_landmarks

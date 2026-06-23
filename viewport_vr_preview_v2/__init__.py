# SPDX-FileCopyrightText: 2021-2023 Blender Foundation
#
# SPDX-License-Identifier: GPL-2.0-or-later

bl_info = {
    "name": "VR Scene Inspection Quick",
    "author": "Julian Eisel (Severin), Sebastian Koenig, Peter Kim (muxed-reality)",
    "version": (0, 11, 10),
    "blender": (3, 2, 0),
    "location": "3D View > Sidebar > VR",
    "description": ("VR viewport inspection with object visibility panel overlay. "
                    "Right trigger selects objects, touchpad click toggles panel."),
    "support": "COMMUNITY",
    "warning": "Performance-optimized fork of the built-in VR Scene Inspection addon",
    "doc_url": "",
    "category": "3D View",
}


if "bpy" in locals():
    import importlib
    importlib.reload(action_map)
    importlib.reload(gui)
    importlib.reload(operators)
    importlib.reload(properties)
else:
    from . import action_map, gui, operators, properties

import bpy


def _ensure_actions_for_active_session():
    try:
        ctx = bpy.context
        ctx_type = type(ctx).__name__
        if ctx_type != 'Context':
            return
        if not bpy.types.XrSessionState.is_running(ctx):
            return
        session_state = ctx.window_manager.xr_session_state
        if not session_state:
            return
        from . import defaults as _defaults
        for am in session_state.actionmaps:
            _defaults._vr_add_missing_actions(am, session_state)
    except Exception:
        pass


def register():
    if not bpy.app.build_options.xr_openxr:
        bpy.utils.register_class(gui.VIEW3D_PT_vr_info)
        return

    action_map.register()
    gui.register()
    operators.register()
    properties.register()
    _ensure_actions_for_active_session()


def unregister():
    if not bpy.app.build_options.xr_openxr:
        bpy.utils.unregister_class(gui.VIEW3D_PT_vr_info)
        return

    action_map.unregister()
    gui.unregister()
    operators.unregister()
    properties.unregister()

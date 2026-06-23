# SPDX-FileCopyrightText: 2021-2022 Blender Foundation
#
# SPDX-License-Identifier: GPL-2.0-or-later

def actionconfig_update(actionconfig_data, actionconfig_version):
    from bpy.app import version_file as blender_version
    if actionconfig_version >= blender_version:
        return actionconfig_data

    return actionconfig_data

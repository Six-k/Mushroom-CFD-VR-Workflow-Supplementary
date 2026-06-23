import bpy

from . import gui
from . import operators

bl_info = {
    "name": "Flow Fields Scene",
    "author": "Liu Kai, Agricultural building ventilation laboratory, China Agricultural University",
    "version": (2, 0, 0),
    "blender": (4, 0, 0),
    "location": "3D View > Sidebar > airFields",
    "description": "Visualize OpenFOAM flow fields in Blender via ParaView scripting.",
    "doc_url": "Development of an Open-Source Integrated Workflow for Airflow Simulation and Virtual Reality Visualisation in Mushroom Cultivation Facilities",
    "category": "3D View",
}


def register():
    gui.register()
    operators.register()


def unregister():
    gui.unregister()
    operators.unregister()


if __name__ == "__main__":
    register()

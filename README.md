# Mushroom CFD-VR Workflow Supplementary

Supplementary materials for the paper:

**"Development of an Open-Source Integrated Workflow for Airflow Simulation and Virtual Reality Visualisation in Mushroom Cultivation Facilities"**

*Kai Liu, Fengyun Wang, Lei An, Xia Liu, Wenxu Zhang, Luzhang Wan, Jiye Zheng\**

---

## Overview

This repository contains Blender add-ons that form part of an open-source integrated CFD-VR workflow for simulating and visualizing airflow in mushroom cultivation facilities. The workflow integrates Blender, OpenFOAM, and ParaView to enable immersive analysis of airflow characteristics in mushroom fruiting rooms.

---

## Contents

### 1. airFields_V2 — Flow Fields Scene (v2.0)

Blender add-on for visualizing OpenFOAM computational fluid dynamics results directly within Blender via ParaView scripting (`paraview.simple`).

- Load OpenFOAM case folders
- Generate streamlines, slice contours, and vector fields
- Automatic STL collision detection
- Integrated in the 3D View sidebar (airFields tab)

### 2. airFields_V3 — Flow Fields Scene (v3.0)

Enhanced version of airFields with an improved VTK-based pipeline for greater flexibility and performance.

- ParaView + VTK hybrid pipeline
- Import VTK-compatible mesh and field data
- Streamlined UI and improved rendering options
- Integrated in the 3D View sidebar (airFields_v3 tab)

### 3. viewport_vr_preview_v2 — VR Scene Inspection Quick

Performance-optimized fork of Blender's built-in VR Scene Inspection add-on, enhanced for fluid dynamics visualization workflows.

- VR viewport inspection with object visibility panel overlay
- Right trigger selects objects, touchpad click toggles info panel
- Optimized rendering pipeline for large CFD datasets
- Integrated in the 3D View sidebar (VR tab)

---

## Installation

1. Download or clone this repository
2. In Blender, go to **Edit > Preferences > Add-ons**
3. Click **Install...** and select the desired add-on folder (e.g., `airFields_V3`)
4. Enable the add-on by checking the box

### Requirements

- Blender 4.0 or later
- ParaView (with Python scripting enabled) — for airFields_V2/V3
- OpenFOAM — for generating CFD input data

---

## Usage

### Airflow Visualization (airFields_V2 / airFields_V3)

1. Prepare an OpenFOAM case with simulation results
2. In Blender, open the sidebar in the 3D Viewport (press **N**)
3. Navigate to the **airFields** or **airFields_v3** tab
4. Load your OpenFOAM case folder
5. Configure visualization parameters (slices, streamlines, etc.)
6. Generate and render flow field visualizations

### VR Inspection (viewport_vr_preview_v2)

1. Ensure your VR headset is connected and configured
2. Enable the add-on and navigate to the **VR** tab in the sidebar
3. Start a VR session to inspect CFD visualizations in immersive view

---

## Related Resources

- Demo video: [YouTube](https://youtu.be/69sOqeZiXXY)

---

## License

This project is provided for academic and research purposes. See individual add-on files for specific license information.

---

## Citation

If you use this workflow in your research, please cite:

> Liu K, Wang F, An L, et al. Development of an Open-Source Integrated Workflow for Airflow Simulation and Virtual Reality Visualisation in Mushroom Cultivation Facilities.

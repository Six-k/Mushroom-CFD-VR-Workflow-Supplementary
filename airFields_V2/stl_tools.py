import os
import math
import struct


def read_stl(filepath):
    with open(filepath, 'rb') as f:
        header = f.read(80)
        try:
            header_str = header.decode('ascii', errors='ignore').strip().lower()
        except Exception:
            header_str = ''
        if header_str.startswith('solid'):
            f.seek(0)
            return _read_stl_ascii_file(f)
        else:
            f.seek(0)
            return _read_stl_binary_file(f)


def _read_stl_ascii_file(f):
    try:
        import numpy as np
    except ImportError:
        raise ImportError("numpy is required for STL processing.")
    facets = []
    for raw_line in f:
        line = raw_line.decode('ascii', errors='ignore').strip()
        if line.startswith('facet normal'):
            parts = line.split()
            normal = np.array([float(parts[2]), float(parts[3]), float(parts[4])])
            _ = next(f)
            v1_raw = next(f).decode('ascii', errors='ignore').strip().split()
            v2_raw = next(f).decode('ascii', errors='ignore').strip().split()
            v3_raw = next(f).decode('ascii', errors='ignore').strip().split()
            v1 = np.array([float(v1_raw[1]), float(v1_raw[2]), float(v1_raw[3])])
            v2 = np.array([float(v2_raw[1]), float(v2_raw[2]), float(v2_raw[3])])
            v3 = np.array([float(v3_raw[1]), float(v3_raw[2]), float(v3_raw[3])])
            facets.append((normal, (v1, v2, v3)))
            _ = next(f); _ = next(f)
    return facets


def _read_stl_binary_file(f):
    try:
        import numpy as np
    except ImportError:
        raise ImportError("numpy is required for STL processing.")
    f.read(80)
    n_facets = struct.unpack('<I', f.read(4))[0]
    facets = []
    for _ in range(n_facets):
        data = struct.unpack('<12fH', f.read(50))
        normal = np.array(data[0:3])
        v1 = np.array(data[3:6])
        v2 = np.array(data[6:9])
        v3 = np.array(data[9:12])
        facets.append((normal, (v1, v2, v3)))
    return facets


def _edge_key(v1, v2):
    a, b = tuple(v1), tuple(v2)
    if a < b:
        return (a, b)
    return (b, a)


def _cluster_facets(facets):
    import numpy as np
    n = len(facets)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    from collections import defaultdict
    edge_to_facets = defaultdict(list)
    for i, (_, (v1, v2, v3)) in enumerate(facets):
        for ek in [_edge_key(v1, v2), _edge_key(v2, v3), _edge_key(v3, v1)]:
            edge_to_facets[ek].append(i)

    for ek, fidx_list in edge_to_facets.items():
        for j in range(1, len(fidx_list)):
            union(fidx_list[0], fidx_list[j])

    groups = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)

    return [indices for indices in groups.values()]


def _centroid_3d(points):
    import numpy as np
    return np.mean(points, axis=0)


def _fit_plane(points_3d):
    import numpy as np
    c = _centroid_3d(points_3d)
    centered = points_3d - c
    _, _, vh = np.linalg.svd(centered)
    normal = vh[2, :]
    normal = normal / np.linalg.norm(normal)
    return normal, c


def _build_2d_basis(normal):
    import numpy as np
    if abs(normal[0]) < 0.9:
        u = np.cross(normal, np.array([1.0, 0.0, 0.0]))
    else:
        u = np.cross(normal, np.array([0.0, 1.0, 0.0]))
    u = u / np.linalg.norm(u)
    v = np.cross(normal, u)
    v = v / np.linalg.norm(v)
    return u, v


def _project_to_2d(points_3d, origin, u, v):
    import numpy as np
    return np.column_stack([
        np.dot(points_3d - origin, u),
        np.dot(points_3d - origin, v),
    ])


def _unproject_to_3d(points_2d, origin, u, v):
    import numpy as np
    p2 = np.atleast_2d(points_2d)
    return origin + p2[:, 0:1] * u + p2[:, 1:2] * v


def _convex_hull_2d(points):
    import numpy as np
    pts = points[np.lexsort((points[:, 1], points[:, 0]))]
    if len(pts) <= 2:
        return pts

    def _chain(pts_sub):
        hull = []
        for p in pts_sub:
            while len(hull) >= 2:
                ab = hull[-1] - hull[-2]
                bc = p - hull[-1]
                cross = ab[0] * bc[1] - ab[1] * bc[0]
                if cross <= 0:
                    hull.pop()
                else:
                    break
            hull.append(p)
        return hull

    lower = _chain(pts)
    upper = _chain(pts[::-1])
    return np.array(lower[:-1] + upper[:-1])


def _triangle_area_3d(v1, v2, v3):
    import numpy as np
    return 0.5 * np.linalg.norm(np.cross(v2 - v1, v3 - v1))


def _hull_perimeter(hull_2d):
    import numpy as np
    peri = 0.0
    for i in range(len(hull_2d)):
        peri += np.linalg.norm(hull_2d[i] - hull_2d[(i + 1) % len(hull_2d)])
    return peri


def _triangulate_hull_to_N(hull_2d, N, centroid_2d, normal, origin, u_axis, v_axis):
    import numpy as np

    if len(hull_2d) < 3:
        return [], []

    angles = np.arctan2(hull_2d[:, 1] - centroid_2d[1], hull_2d[:, 0] - centroid_2d[0])
    order = np.argsort(angles)
    sorted_hull = hull_2d[order]

    closed = np.vstack([sorted_hull, sorted_hull[0]])

    seg_vectors = closed[1:] - closed[:-1]
    seg_lengths = np.linalg.norm(seg_vectors, axis=1)
    cumulative = np.cumsum(seg_lengths)
    total_length = cumulative[-1]

    if total_length < 1e-15:
        return [], []

    sample_points_2d = []
    for i in range(N):
        t = i / N * total_length
        idx = np.searchsorted(cumulative, t, side='right')
        if idx >= len(cumulative):
            idx = len(cumulative) - 1
        offset = t - (cumulative[idx - 1] if idx > 0 else 0.0)
        seg_len = seg_lengths[idx]
        frac = offset / seg_len if seg_len > 1e-15 else 0.0
        frac = max(0.0, min(1.0, frac))
        pt = closed[idx] + frac * seg_vectors[idx]
        sample_points_2d.append(pt)

    centroid_3d = _unproject_to_3d(np.array([centroid_2d]), origin, u_axis, v_axis)[0]

    tris_3d = []
    normals_out = []
    for i in range(N):
        p_2d_a = sample_points_2d[i]
        p_2d_b = sample_points_2d[(i + 1) % N]
        p3_a = _unproject_to_3d(np.array([p_2d_a]), origin, u_axis, v_axis)[0]
        p3_b = _unproject_to_3d(np.array([p_2d_b]), origin, u_axis, v_axis)[0]
        tris_3d.append(np.array([centroid_3d, p3_a, p3_b]))
        normals_out.append(normal)

    return tris_3d, normals_out


def subdivide_stl(input_path, output_path, N=100):
    try:
        import numpy as np
    except ImportError:
        return False, "numpy is not available."

    if not os.path.exists(input_path):
        return False, f"Input STL not found: {input_path}"

    if N < 1:
        return False, f"N must be >= 1, got {N}"

    try:
        facets = read_stl(input_path)
    except Exception as e:
        return False, f"Failed to read STL: {e}"

    if len(facets) == 0:
        return False, "Empty STL file"

    clusters = _cluster_facets(facets)

    import numpy as np
    group_info = []
    for indices in clusters:
        verts = []
        for i in indices:
            _, (v1, v2, v3) = facets[i]
            verts.extend([v1, v2, v3])
        verts = np.array(verts)
        unique = np.unique(verts.round(decimals=10), axis=0)
        area = 0.0
        for i in indices:
            _, (v1, v2, v3) = facets[i]
            area += _triangle_area_3d(v1, v2, v3)
        group_info.append((indices, unique, area))

    total_area = sum(g[2] for g in group_info)
    if total_area < 1e-15:
        return False, "Degenerate geometry (zero area)"

    allocations = []
    remaining = N
    for idx, (indices, verts, area) in enumerate(group_info):
        if idx == len(group_info) - 1:
            n_i = remaining
        else:
            n_i = max(1, int(round(N * area / total_area)))
        allocations.append(n_i)
        remaining -= n_i

    while remaining < 0:
        for i in range(len(allocations)):
            if allocations[i] > 1:
                allocations[i] -= 1
                remaining += 1
                if remaining >= 0:
                    break

    all_tris = []
    all_normals = []

    for gi, (indices, verts, area) in enumerate(group_info):
        n_i = max(1, allocations[gi])
        normal, origin = _fit_plane(verts)
        u_axis, v_axis = _build_2d_basis(normal)
        points_2d = _project_to_2d(verts, origin, u_axis, v_axis)
        hull_2d = _convex_hull_2d(points_2d)
        centroid_2d = np.mean(hull_2d, axis=0)

        if n_i == 1:
            if len(hull_2d) >= 3:
                idxs = [0, len(hull_2d)//3, 2*len(hull_2d)//3]
                tri_3d = _unproject_to_3d(hull_2d[idxs], origin, u_axis, v_axis)
                all_tris.append(tri_3d)
                all_normals.append(normal)
        elif n_i == 2:
            centroid_3d = _unproject_to_3d(np.array([centroid_2d]), origin, u_axis, v_axis)[0]
            angles = np.arctan2(hull_2d[:, 1] - centroid_2d[1], hull_2d[:, 0] - centroid_2d[0])
            p1 = hull_2d[np.argmin(angles)]
            p2 = hull_2d[np.argmax(angles)]
            p3_1 = _unproject_to_3d(np.array([p1]), origin, u_axis, v_axis)[0]
            p3_2 = _unproject_to_3d(np.array([p2]), origin, u_axis, v_axis)[0]
            for pt in hull_2d:
                p3_c = _unproject_to_3d(np.array([pt]), origin, u_axis, v_axis)[0]
                if np.linalg.norm(np.cross(p3_2 - p3_1, p3_c - p3_1)) > 1e-10:
                    all_tris.append(np.array([centroid_3d, p3_1, p3_2]))
                    all_normals.append(normal)
                    all_tris.append(np.array([centroid_3d, p3_2, p3_c]))
                    all_normals.append(normal)
                    break
        else:
            tris, norms = _triangulate_hull_to_N(
                hull_2d, n_i, centroid_2d, normal, origin, u_axis, v_axis
            )
            all_tris.extend(tris)
            all_normals.extend(norms)

    try:
        _write_stl_ascii(output_path, all_tris, all_normals)
    except Exception as e:
        return False, f"Failed to write output: {e}"

    return True, f"Subdivided into {len(all_tris)} triangles (target N={N})"


def _write_stl_ascii(filepath, faces_3d, normals):
    with open(filepath, 'w') as f:
        f.write('solid subdivided\n')
        for tri, n in zip(faces_3d, normals):
            f.write(f'facet normal {n[0]:.12g} {n[1]:.12g} {n[2]:.12g}\n')
            f.write(' outer loop\n')
            for v in tri:
                f.write(f'  vertex {v[0]:.12g} {v[1]:.12g} {v[2]:.12g}\n')
            f.write(' endloop\n')
            f.write('endfacet\n')
        f.write('endsolid subdivided\n')

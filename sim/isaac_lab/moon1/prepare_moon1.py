#!/usr/bin/env python3
"""Build an Isaac Lab height mesh and two-rover replay from a LuSNAR sample.

This script only needs NumPy, SciPy and Matplotlib. It does not import Isaac Lab.
The output is a *local approximation* from six fused LiDAR frames, not the
original Unreal/AirSim scene or a validated drivable terrain model.
"""

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt, gaussian_filter


def read_ply(path):
    """Read the binary xyz/rgb PLY written by LuSNAR-reproduction/fuse_lidar.py."""
    with Path(path).open("rb") as stream:
        lines = []
        while True:
            line = stream.readline()
            if not line:
                raise ValueError("PLY header has no end_header")
            lines.append(line.decode("ascii").strip())
            if lines[-1] == "end_header":
                break
        expected = [
            "property float x", "property float y", "property float z",
            "property uchar red", "property uchar green", "property uchar blue",
        ]
        properties = [line for line in lines if line.startswith("property ")]
        if "format binary_little_endian 1.0" not in lines or properties != expected:
            raise ValueError("Expected LuSNAR fused xyz/rgb binary little-endian PLY")
        counts = [int(line.split()[2]) for line in lines if line.startswith("element vertex ")]
        if len(counts) != 1:
            raise ValueError("Expected one vertex count")
        dtype = np.dtype([
            ("x", "<f4"), ("y", "<f4"), ("z", "<f4"),
            ("red", "u1"), ("green", "u1"), ("blue", "u1"),
        ])
        points = np.fromfile(stream, dtype=dtype, count=counts[0])
    if len(points) != counts[0]:
        raise ValueError("Truncated PLY")
    return points


def load_track(path, max_index=200):
    rows = np.loadtxt(path, delimiter=",", comments="#")
    if rows.ndim != 2 or rows.shape[1] < 8 or len(rows) <= max_index:
        raise ValueError("GT file has too few rows or columns")
    rows = rows[: max_index + 1]
    # LuSNAR world convention is x forward, y right, z down.
    # USD/Isaac uses x forward, y left, z up.
    xyz = rows[:, 1:4].astype(np.float64)
    xyz[:, 1:] *= -1.0
    seconds = (rows[:, 0] - rows[0, 0]) * 1e-9
    if np.any(np.diff(seconds) <= 0):
        raise ValueError("GT timestamps must be strictly increasing")
    return seconds, xyz


def build_height_mesh(points, bounds, resolution):
    xmin, xmax, ymin, ymax = bounds
    nx = int(round((xmax - xmin) / resolution)) + 1
    ny = int(round((ymax - ymin) / resolution)) + 1
    if nx < 2 or ny < 2:
        raise ValueError("Terrain grid is too small")
    x = points["x"].astype(np.float64)
    y = -points["y"].astype(np.float64)
    z = -points["z"].astype(np.float64)
    # Reject extreme returns that make unstable terrain spikes. This retains
    # shallow rocks and undulations while excluding distant vertical faces.
    keep = (
        np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
        & (x >= xmin) & (x <= xmax) & (y >= ymin) & (y <= ymax)
        & (z >= -1.0) & (z <= 1.0)
    )
    ix = np.clip(np.rint((x[keep] - xmin) / resolution).astype(int), 0, nx - 1)
    iy = np.clip(np.rint((y[keep] - ymin) / resolution).astype(int), 0, ny - 1)
    linear = ix * ny + iy
    order = np.argsort(linear)
    linear, z = linear[order], z[keep][order]
    rgb = np.column_stack((points["red"], points["green"], points["blue"]))[keep][order]
    unique, starts, counts = np.unique(linear, return_index=True, return_counts=True)
    flat_z = np.full(nx * ny, np.nan, dtype=np.float32)
    flat_rgb = np.zeros((nx * ny, 3), dtype=np.float32)
    for cell, start, count in zip(unique, starts, counts):
        flat_z[cell] = np.median(z[start : start + count])
        flat_rgb[cell] = np.mean(rgb[start : start + count], axis=0) / 255.0
    observed = np.isfinite(flat_z).reshape(nx, ny)
    if not observed.any():
        raise ValueError("No LiDAR returns inside selected bounds")
    height = flat_z.reshape(nx, ny)
    rgb_grid = flat_rgb.reshape(nx, ny, 3)
    nearest = distance_transform_edt(~observed, return_distances=False, return_indices=True)
    # Fill holes for a continuous collision surface; record distance to actual
    # observations so experiments can exclude inferred areas.
    distance = distance_transform_edt(~observed) * resolution
    height = height[tuple(nearest)]
    rgb_grid = rgb_grid[tuple(nearest)]
    height = gaussian_filter(height, sigma=0.65).astype(np.float32)
    xx, yy = np.meshgrid(
        xmin + np.arange(nx) * resolution,
        ymin + np.arange(ny) * resolution,
        indexing="ij",
    )
    vertices = np.column_stack((xx.ravel(), yy.ravel(), height.ravel())).astype(np.float32)
    cell_x, cell_y = np.meshgrid(np.arange(nx - 1), np.arange(ny - 1), indexing="ij")
    a = (cell_x * ny + cell_y).ravel()
    b, c, d = a + ny, a + 1, a + ny + 1
    faces = np.stack((np.stack((a, b, c), axis=1), np.stack((b, d, c), axis=1)), axis=1)
    faces = faces.reshape(-1, 3).astype(np.int32)
    return vertices, faces, rgb_grid.reshape(-1, 3), observed, distance


def make_replay(seconds, xyz, follower_delay):
    if follower_delay <= 0 or follower_delay >= seconds[-1]:
        raise ValueError("Follower delay must be within the GT time span")
    # Car 1 leads; car 2 follows the same observed track. This avoids making
    # up a second traversable path outside the six-frame LiDAR footprint.
    sim_time = seconds[seconds <= seconds[-1] - follower_delay]
    leader_time = sim_time + follower_delay
    leader = np.column_stack([np.interp(leader_time, seconds, xyz[:, i]) for i in range(3)])
    follower = np.column_stack([np.interp(sim_time, seconds, xyz[:, i]) for i in range(3)])
    return sim_time, leader, follower


def write_preview(path, vertices, shape, observed, leader, follower):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    nx, ny = shape
    fig, ax = plt.subplots(figsize=(11, 5.5), constrained_layout=True)
    terrain = vertices[:, 2].reshape(nx, ny)
    extent = (vertices[0, 0], vertices[-1, 0], vertices[0, 1], vertices[ny - 1, 1])
    ax.imshow(terrain.T, origin="lower", extent=extent, cmap="gray", aspect="equal")
    ax.contour(vertices[:, 0].reshape(nx, ny), vertices[:, 1].reshape(nx, ny),
               observed.astype(float), levels=[0.5], colors=["#f1b54e"], linewidths=0.8)
    ax.plot(leader[:, 0], leader[:, 1], color="#4fe0ef", lw=2.3, label="Car 1 leader")
    ax.plot(follower[:, 0], follower[:, 1], color="#f46c5a", lw=1.4, label="Car 2 follower")
    ax.scatter(leader[0, 0], leader[0, 1], color="#4fe0ef", s=30)
    ax.scatter(follower[0, 0], follower[0, 1], color="#f46c5a", s=30)
    ax.set(xlabel="Isaac x (m)", ylabel="Isaac y (m)", title="LuSNAR Moon_1: inferred height mesh and two-rover replay")
    ax.legend(loc="upper right")
    fig.savefig(path, dpi=180)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ply", type=Path, required=True)
    parser.add_argument("--gt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resolution", type=float, default=0.4)
    parser.add_argument("--bounds", type=float, nargs=4, default=(-5, 55, -12, 12),
                        metavar=("XMIN", "XMAX", "YMIN", "YMAX"))
    parser.add_argument("--max-gt-index", type=int, default=200)
    parser.add_argument("--follower-delay", type=float, default=5.0)
    args = parser.parse_args()
    if args.resolution <= 0:
        parser.error("--resolution must be positive")
    args.output.mkdir(parents=True, exist_ok=True)
    points = read_ply(args.ply)
    vertices, faces, colors, observed, distance = build_height_mesh(points, args.bounds, args.resolution)
    seconds, xyz = load_track(args.gt, args.max_gt_index)
    sim_time, leader, follower = make_replay(seconds, xyz, args.follower_delay)
    nx, ny = observed.shape
    np.savez_compressed(args.output / "moon1_scene.npz", vertices=vertices, faces=faces,
                        colors=colors.astype(np.float32), observed=observed, distance_to_observation=distance,
                        grid_shape=np.array([nx, ny]), sim_time=sim_time, leader=leader, follower=follower)
    write_preview(args.output / "moon1_preview.png", vertices, (nx, ny), observed, leader, follower)
    summary = {
        "source_ply": str(args.ply.resolve()), "source_gt": str(args.gt.resolve()),
        "source": "LuSNAR Moon_1, six fused LiDAR frames and first %d GT poses" % (args.max_gt_index + 1),
        "coordinate_conversion": "Isaac (x,y,z) = LuSNAR (x,-y,-z)",
        "bounds_m": args.bounds, "resolution_m": args.resolution,
        "grid_vertices": len(vertices), "mesh_triangles": len(faces),
        "observed_grid_fraction": float(observed.mean()),
        "replay_duration_s": float(sim_time[-1]), "replay_samples": len(sim_time),
        "follower_delay_s": args.follower_delay,
        "caveat": "Unobserved cells use nearest measured height; not a validated collision or RF model.",
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    from provenance import receipt
    receipt(args.output / "provenance.json", vars(args), {"source_ply":args.ply,"source_gt":args.gt,"scene_npz":args.output / "moon1_scene.npz"}, {"csv":"not generated yet", "usd":"GUI not run"})
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

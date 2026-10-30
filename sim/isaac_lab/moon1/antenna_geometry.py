"""Shared kinematic terrain/body/antenna convention; no Isaac imports."""
import numpy as np
ANTENNA_HEIGHT_M = 1.16

def terrain_z(data, x, y):
    nx, ny = map(int, data["grid_shape"])
    vertices = data["vertices"].reshape(nx, ny, 3)
    x0, y0 = vertices[0, 0, :2]
    dx = vertices[1, 0, 0] - x0
    dy = vertices[0, 1, 1] - y0
    fx = np.clip((x - x0) / dx, 0, nx - 1.000001)
    fy = np.clip((y - y0) / dy, 0, ny - 1.000001)
    ix, iy = int(fx), int(fy)
    fx, fy = fx - ix, fy - iy
    z = vertices[:, :, 2]
    return float((1 - fx) * (1 - fy) * z[ix, iy] + fx * (1 - fy) * z[ix + 1, iy]
                 + (1 - fx) * fy * z[ix, iy + 1] + fx * fy * z[ix + 1, iy + 1])


def positions(data, xyz):
    original = np.asarray(xyz, dtype=float).copy()
    body = original.copy()
    body[..., 2] = [terrain_z(data, x, y) for x, y in original.reshape(-1,3)[:, :2]]
    antenna = body.copy()
    antenna[..., 2] += ANTENNA_HEIGHT_M
    return body, antenna

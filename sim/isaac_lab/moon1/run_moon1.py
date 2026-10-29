#!/usr/bin/env python3
"""Replay two rover markers over a LuSNAR-derived moon mesh in Isaac Lab 2.3.2.

The vehicle motion is kinematic. The terrain has static collision, but this
prototype does not simulate wheel contact, slip, soil, or RF propagation.
"""

import argparse
from pathlib import Path

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--scene", type=Path)
parser.add_argument("--replay", type=Path)
parser.add_argument("--export-usd", type=Path)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
if args.scene is None or args.replay is None:
    parser.error("--scene and --replay are required")
app_launcher = AppLauncher(args)
simulation_app = app_launcher.app

import math  # noqa: E402

import numpy as np  # noqa: E402
import omni.usd  # noqa: E402
from pxr import Gf, UsdGeom, UsdPhysics  # noqa: E402

import isaaclab.sim as sim_utils  # noqa: E402


def color(prim, rgb):
    UsdGeom.Gprim(prim).CreateDisplayColorAttr([Gf.Vec3f(*rgb)])


def make_terrain(stage, data):
    vertices, faces, colors = data["vertices"], data["faces"], data["colors"]
    mesh = UsdGeom.Mesh.Define(stage, "/World/Moon1/Terrain")
    mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
    mesh.CreatePointsAttr([Gf.Vec3f(*map(float, row)) for row in vertices])
    mesh.CreateFaceVertexCountsAttr([3] * len(faces))
    mesh.CreateFaceVertexIndicesAttr(faces.ravel().tolist())
    mesh.CreateDoubleSidedAttr(True)
    mesh.CreateDisplayColorPrimvar(UsdGeom.Tokens.vertex).Set(
        [Gf.Vec3f(*map(float, row)) for row in colors]
    )
    UsdPhysics.CollisionAPI.Apply(mesh.GetPrim())
    return mesh


def make_cube(stage, path, size, location, rgb):
    cube = UsdGeom.Cube.Define(stage, path)
    cube.CreateSizeAttr(1.0)
    transform = UsdGeom.Xformable(cube.GetPrim())
    transform.AddTranslateOp().Set(Gf.Vec3d(*location))
    transform.AddScaleOp().Set(Gf.Vec3f(*size))
    color(cube.GetPrim(), rgb)


def make_rover(stage, name, rgb):
    root = UsdGeom.Xform.Define(stage, "/World/%s" % name)
    transform = UsdGeom.Xformable(root.GetPrim())
    translation = transform.AddTranslateOp()
    rotation = transform.AddOrientOp()
    base = "/World/%s" % name
    make_cube(stage, base + "/Chassis", (1.25, 0.78, 0.22), (0, 0, 0.47), rgb)
    make_cube(stage, base + "/Deck", (1.45, 1.0, 0.035), (0, 0, 0.66), (0.11, 0.16, 0.24))
    make_cube(stage, base + "/AntennaMast", (0.05, 0.05, 0.55), (0.28, 0, 1.0), (0.80, 0.80, 0.76))
    for longitudinal in (-0.47, 0.47):
        for lateral in (-0.45, 0.45):
            name_suffix = ("Rear" if longitudinal < 0 else "Front") + ("Right" if lateral < 0 else "Left")
            wheel = UsdGeom.Cylinder.Define(stage, base + "/Wheel" + name_suffix)
            wheel.CreateRadiusAttr(0.23)
            wheel.CreateHeightAttr(0.12)
            wheel_transform = UsdGeom.Xformable(wheel.GetPrim())
            wheel_transform.AddTranslateOp().Set(Gf.Vec3d(longitudinal, lateral, 0.23))
            wheel_transform.AddOrientOp().Set(Gf.Quatf(math.sqrt(0.5), math.sqrt(0.5), 0, 0))
            color(wheel.GetPrim(), (0.06, 0.07, 0.09))
    return translation, rotation


def make_line(stage, path, rgb):
    line = UsdGeom.BasisCurves.Define(stage, path)
    line.CreateTypeAttr(UsdGeom.Tokens.linear)
    line.CreateCurveVertexCountsAttr([2])
    line.CreateWidthsAttr([0.07])
    line.CreateDisplayColorAttr([Gf.Vec3f(*rgb)])
    return line


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


def set_rover(ops, data, row, prefix):
    x, y = float(row[prefix + "_x"]), float(row[prefix + "_y"])
    z = terrain_z(data, x, y)
    yaw = float(row[prefix + "_yaw"])
    ops[0].Set(Gf.Vec3d(x, y, z))
    ops[1].Set(Gf.Quatf(math.cos(yaw / 2), 0, 0, math.sin(yaw / 2)))
    return Gf.Vec3f(x, y, z + 1.16)


def main():
    data = np.load(args.scene)
    replay = np.genfromtxt(args.replay, delimiter=",", names=True, dtype=float)
    if len(replay) < 2:
        raise ValueError("Replay needs at least two rows")
    sim_cfg = sim_utils.SimulationCfg(dt=1.0 / 60.0, device=args.device, gravity=(0.0, 0.0, -1.62))
    sim = sim_utils.SimulationContext(sim_cfg)
    stage = omni.usd.get_context().get_stage()
    UsdGeom.Xform.Define(stage, "/World/Moon1")
    make_terrain(stage, data)
    sun = sim_utils.DistantLightCfg(intensity=2800.0, color=(0.95, 0.90, 0.80))
    sun.func("/World/Sun", sun, translation=(0.0, 0.0, 20.0))
    car1 = make_rover(stage, "Car1", (0.10, 0.69, 0.82))
    car2 = make_rover(stage, "Car2", (0.91, 0.33, 0.22))
    link = make_line(stage, "/World/UwbLink", (1.0, 0.86, 0.20))
    sim.set_camera_view([21.0, -26.0, 21.0], [23.0, 1.0, 0.0])
    sim.reset()
    if args.export_usd:
        args.export_usd.parent.mkdir(parents=True, exist_ok=True)
        stage.GetRootLayer().Export(str(args.export_usd))
    times = replay["time_s"]
    frame = 0
    while simulation_app.is_running():
        current = frame * sim.get_physics_dt()
        if current > times[-1]:
            break
        index = min(int(np.searchsorted(times, current)), len(times) - 1)
        row = replay[index]
        a = set_rover(car1, data, row, "car1")
        b = set_rover(car2, data, row, "car2")
        link.CreatePointsAttr([a, b]) if frame == 0 else link.GetPointsAttr().Set([a, b])
        sim.step()
        frame += 1
    print("Replayed %.2f s, %d physics frames" % (times[-1], frame))


try:
    main()
finally:
    simulation_app.close()

"""Independent read-only geometry diagnostics; no estimator or Isaac imports."""
import csv
import numpy as np
from scipy.ndimage import distance_transform_edt, gaussian_filter
from scipy.spatial import cKDTree

STRATA = ('supported_smoothed', 'smoothing_inferred_or_edge', 'filled_node', 'clipped')
REQUIRED = ['time_s', 'true_range_m'] + [f'car{c}_{k}' for c in (1, 2)
    for k in ('x', 'y', 'z', 'yaw', 'body_z', 'gt_z', 'range_m', 'quality')]


def load_csv(path):
    with open(path, newline='') as f:
        reader = csv.DictReader(f)
        missing = sorted(set(REQUIRED) - set(reader.fieldnames or []))
        if missing:
            raise ValueError('Legacy/incomplete CSV; regenerate explicitly; missing: ' + ', '.join(missing))
        rows = list(reader)
    if len(rows) < 2:
        raise ValueError('At least two rows required')
    out = {k: np.array([float(r[k]) if r[k] != '' else np.nan for r in rows]) for k in REQUIRED}
    for k, v in out.items():
        if not (k.endswith('range_m') and k != 'true_range_m' or k.endswith('quality')):
            if not np.isfinite(v).all():
                raise ValueError('Nonfinite field: ' + k)
    if np.any(np.diff(out['time_s']) <= 0):
        raise ValueError('Non-increasing time')
    return out


def metrics(a, b, fixed_dz):
    d = np.asarray(a, float) - np.asarray(b, float)
    xy = np.hypot(d[:, 0], d[:, 1])
    three = np.sqrt(np.sum(d*d, axis=1))
    denominator = three + xy
    analytic = np.divide(d[:, 2]**2, denominator, out=np.zeros_like(xy), where=denominator != 0)
    fixed = np.hypot(xy, fixed_dz)
    return dict(r_xy_m=xy, r_3d_m=three, delta_z_m=d[:, 2], ignore_error_m=three-xy,
                analytic_error_m=analytic, fixed_range_m=fixed, fixed_error_m=three-fixed,
                coincident=denominator == 0)


def grid_stencil(data, xy):
    """Match production float32 grid spacing, including its upper epsilon clip."""
    nx, ny = map(int, data['grid_shape'])
    v = data['vertices'].reshape(nx, ny, 3)
    origin = v[0, 0, :2]
    step = np.array([v[1, 0, 0]-origin[0], v[0, 1, 1]-origin[1]])
    f = (np.asarray(xy, float)-origin)/step
    fc = np.clip(f, [0, 0], [nx-1.000001, ny-1.000001])
    ij = np.floor(fc).astype(int)
    u = fc-ij
    nodes = ij[:, None, :] + np.array([[0, 0], [1, 0], [0, 1], [1, 1]])
    weights = np.column_stack(((1-u[:, 0])*(1-u[:, 1]), u[:, 0]*(1-u[:, 1]),
                               (1-u[:, 0])*u[:, 1], u[:, 0]*u[:, 1]))
    clipped = np.any(f != fc, axis=1)
    outside = np.any((xy < v[0, 0, :2]) | (xy > v[-1, -1, :2]), axis=1)
    return nodes, weights, clipped, outside, np.linalg.norm((fc-f)*step, axis=1)


def sample_grid(grid, nodes, weights):
    return np.sum(grid[nodes[:, :, 0], nodes[:, :, 1]]*weights, axis=1)


def raw_grid(points, bounds, resolution, sigma=.65, truncate=4.):
    """Independent reconstruction of retained cell medians and smoothing provenance."""
    x = points['x'].astype(float); y = -points['y'].astype(float); z = -points['z'].astype(float)
    xmin, xmax, ymin, ymax = bounds
    keep = np.isfinite(x+y+z) & (x >= xmin) & (x <= xmax) & (y >= ymin) & (y <= ymax) & (z >= -1) & (z <= 1)
    shape = (round((xmax-xmin)/resolution)+1, round((ymax-ymin)/resolution)+1)
    indices = np.rint(np.column_stack((x[keep]-xmin, y[keep]-ymin))/resolution).astype(int)
    raw = np.full(shape, np.nan, dtype=np.float32)
    cells = {}
    for ij, value in zip(indices, z[keep]):
        cells.setdefault(tuple(ij), []).append(value)
    for ij, values in cells.items():
        raw[ij] = np.median(values)
    obs = np.isfinite(raw)
    donors = distance_transform_edt(~obs, return_distances=False, return_indices=True)
    filled = raw[tuple(donors)]
    smooth = gaussian_filter(filled, sigma=sigma, truncate=truncate, mode='reflect')
    mass = gaussian_filter((~obs).astype(float), sigma=sigma, truncate=truncate, mode='reflect')
    radius = int(truncate*sigma+.5)
    xx, yy = np.indices(shape)
    edge = (xx < radius) | (yy < radius) | (xx >= shape[0]-radius) | (yy >= shape[1]-radius)
    return dict(raw=raw, observed=obs, filled=filled, smooth=smooth, fill_mass=mass,
                edge=edge, donors=donors, tree=cKDTree(np.column_stack((x[keep], y[keep]))),
                retained=int(keep.sum()), rejected=int((~keep).sum()), radius=radius)


def support(data, xy, raw):
    nodes, weights, clipped, outside, shift = grid_stencil(data, xy)
    ix, iy = nodes[:, :, 0], nodes[:, :, 1]
    active = weights > 0
    observed = data['observed'][ix, iy]
    filled = np.any(active & ~observed, axis=1)
    # Kernel coefficients are strictly positive inside its finite support.
    inferred = np.any(active & ((raw['fill_mass'][ix, iy] > 0) | raw['edge'][ix, iy]), axis=1)
    rank = np.where(clipped, 3, np.where(filled, 2, np.where(inferred, 1, 0)))
    return dict(nodes=nodes, weights=weights, observed=observed, rank=rank,
                clipped=clipped, outside=outside, clip_shift_m=shift,
                node_observation_distance_m=data['distance_to_observation'][ix, iy],
                donors=np.moveaxis(raw['donors'][:, ix, iy], 0, -1),
                raw_point_distance_m=raw['tree'].query(xy)[0],
                fill_mass=sample_grid(raw['fill_mass'], nodes, weights),
                reflected=np.any(active & raw['edge'][ix, iy], axis=1),
                unsmoothed_z=sample_grid(raw['filled'], nodes, weights),
                smooth_z=sample_grid(raw['smooth'], nodes, weights))


def summary(values):
    x = np.asarray(values, float)
    if not len(x):
        return dict(n=0, mean=None, rms=None, min=None, p05=None, p50=None, p95=None, p99=None, max=None, abs_max=None)
    return dict(n=len(x), mean=float(x.mean()), rms=float(np.sqrt(np.mean(x*x))),
                min=float(x.min()), p05=float(np.quantile(x,.05)), p50=float(np.median(x)),
                p95=float(np.quantile(x,.95)), p99=float(np.quantile(x,.99)),
                max=float(x.max()), abs_max=float(np.max(np.abs(x))))

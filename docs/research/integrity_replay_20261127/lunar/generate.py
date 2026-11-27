"""Generate frozen synthetic two-rover observations on the archived LuSNAR height field."""
import csv
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import binary_erosion, distance_transform_edt, gaussian_filter

TERRAIN_RELATIVE_PATH = Path("docs/research/lunar_end_to_end/continuous")
SOURCE_HASHES = {
    "terrain.npz": "344460e63fb7a7d9d7596bbf66a55523792046b7a24a702e7703830c6150104c",
    "CLOUD_SUPPORT.npz": "ec37e5be77876350d2e71b04237502b7ed8a2c0773066617178e8a43e0b2b137",
}
SEEDS = [832137, 832138, 832139]
DURATION = 90
SIGMAS = {"sigma_range": 0.04, "sigma_motion": 0.03, "sigma_prior": 0.50}
LAYOUTS = {
   "L1": [[5.8,-1.28],[5.8,4.12],[24.8,-1.28],[24.8,4.12]],
   "L2": [[5.9,3.72],[11.7,4.09],[18.2,3.72],[24.65,4.09]],
}
LINKS = [f"R{r}-A{a}" for r in (1,2) for a in (1,2,3,4)] + ["R1-R2"]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def dump(p, data):
    raw = (json.dumps(data, separators=(",", ":"), allow_nan=False) + "\n").encode()
    p.write_bytes(gzip.compress(raw, mtime=0))


def table(p, rows):
    with p.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


class Terrain:
    def __init__(self, source_dir):
        path = source_dir / "terrain.npz"
        with np.load(path) as d:
            self.z, self.mask = d["terrain"], d["observed"].astype(bool)
            self.low, self.res = d["low"], float(d["res"])
        # Check the full original smoothing footprint using the raw registered data,
        # including a four-node halo beyond the archived plotting crop.
        cloud = np.load(source_dir / "CLOUD_SUPPORT.npz")["world_xyz_m"]
        pad = 4
        raw = np.full(np.array(self.z.shape)+2*pad,np.nan)
        ij = np.rint((cloud[:,:2]-self.low)/self.res).astype(int)+pad
        valid = np.all((ij>=0)&(ij<np.array(raw.shape)),axis=1)
        flat = np.ravel_multi_index(ij[valid].T,raw.shape)
        order = np.argsort(flat)
        keys,starts = np.unique(flat[order],return_index=True)
        values = cloud[valid,2][order]
        for key,left,right in zip(keys,starts,np.r_[starts[1:],len(order)]):
            raw.ravel()[key]=np.median(values[left:right])
        fine = np.isfinite(raw)
        near = distance_transform_edt(~fine,return_distances=False,return_indices=True)
        check = gaussian_filter(raw[tuple(near)],.65)
        core = (slice(pad,-pad),slice(pad,-pad))
        assert np.array_equal(fine[core],self.mask)
        assert np.array_equal(check[core],self.z)
        # scipy's default Gaussian smoothing at sigma .65 has radius round(4*.65)=3.
        strict = binary_erosion(fine,np.ones((7,7),bool),border_value=0)[core]
        self.inner_mask = strict & binary_erosion(self.mask,np.ones((3,3),bool),border_value=0)
        self.raw_points = len(cloud)
        self.full_kernel_count = int(strict.sum())

    def query(self, xy):
        """Continuous heights on triangles LL/LR/UR, LL/UR/UL of each observed grid cell."""
        p=(np.atleast_2d(xy)-self.low)/self.res
        ij=np.floor(p).astype(int)
        fx,fy=(p-ij).T
        i,j=ij.T
        if (ij<0).any() or (ij>=np.array(self.z.shape)-1).any():
            raise ValueError("position outside archived grid")
        plane_a=(fx>=fy)
        z00,z10,z01,z11=self.z[i,j],self.z[i+1,j],self.z[i,j+1],self.z[i+1,j+1]
        gx=np.where(plane_a,z10-z00,z11-z01)/self.res
        gy=np.where(plane_a,z11-z10,z01-z00)/self.res
        heights=z00+(gx*fx+gy*fy)*self.res
        # All four corners have a fully observed 7 x 7 original smoothing footprint.
        supported=np.logical_and.reduce([self.inner_mask[i+di,j+dj] for di,dj in [(0,0),(0,1),(1,0),(1,1)]])
        return heights,supported,np.hypot(gx,gy)

    def segment(self, p, q):
        xy=np.array([p[:2],q[:2]])
        start,end=(xy-self.low)/self.res
        nodes=[0.,1.]
        # At x grid lines, y grid lines and lower-left/upper-right diagonals, the
        # terrain can change plane. On each remaining interval the gap is linear.
        for a,b in zip([*start,start[0]-start[1]],[*end,end[0]-end[1]]):
            if abs(b-a)<1e-12:
                continue
            k=np.arange(np.floor(min(a,b))+1,np.ceil(max(a,b)))
            nodes.extend(((k-a)/(b-a)).tolist())
        nodes=np.unique(np.clip(nodes,0,1))
        u=np.sort(np.r_[nodes,(nodes[1:]+nodes[:-1])/2])
        xyz=p+(q-p)*u[:,None]
        z,ok,_=self.query(xyz[:,:2])
        if not ok.all():
            return "unknown",None
        clear=float(np.min(xyz[:,2]-z))
        return ("LOS" if clear>1e-9 else "NLOS"),clear


def poses(t):
    u=np.asarray(t,dtype=float)/DURATION
    tau=2*np.pi
    r1=np.column_stack((7.3+16.2*u, .2+.79*np.sin(tau*u)+.23*np.sin(2*tau*u)))
    r2=np.column_stack((23.2-14.8*u, 2.6+.64*np.sin(1.2*tau*u+.45)-.25*np.sin(2*tau*u)))
    v1=np.column_stack((np.full_like(u,16.2), .79*tau*np.cos(tau*u)+.23*2*tau*np.cos(2*tau*u)))/DURATION
    v2=np.column_stack((np.full_like(u,-14.8), .64*1.2*tau*np.cos(1.2*tau*u+.45)-.25*2*tau*np.cos(2*tau*u)))/DURATION
    return np.stack((r1,r2),axis=1),np.stack((v1,v2),axis=1)


def geometry(terrain, output_dir):
    t=np.arange(20*DURATION+1)/20
    xy,v=poses(t)
    z,ok,slope=terrain.query(xy.reshape(-1,2))
    assert np.all(ok)
    xyz=np.dstack((xy,z.reshape(-1,2)+1.16))
    yaw=np.arctan2(v[:,:,1],v[:,:,0])
    # For a 0.8 x 0.6 m upright rover, a 0.5 m disk encloses every yawed footprint.
    # Check the full rectangle containing both analytic trajectories and footprints.
    domain=[(6.8,24.0),(-1.32,3.99)]
    mins=np.floor((np.array([a for a,b in domain])-terrain.low)/terrain.res).astype(int)
    maxs=np.floor((np.array([b for a,b in domain])-terrain.low)/terrain.res).astype(int)+1
    assert terrain.inner_mask[mins[0]:maxs[0]+1,mins[1]:maxs[1]+1].all()
    assert ((xy>=np.array([a for a,b in domain])+.5-1e-10) & (xy<=np.array([b for a,b in domain])-.5+1e-10)).all()
    speed_bounds=np.hypot([16.2,14.8],[.79*2*np.pi+.23*4*np.pi,.64*2.4*np.pi+.25*4*np.pi])/DURATION
    assert (speed_bounds<.25).all()
    assert min(np.linalg.norm(xy[:,0]-xy[:,1],axis=1))>1.1
    rows=[dict(t_s=float(time),rover=r+1,x_m=xyz[i,r,0],y_m=xyz[i,r,1],z_m=xyz[i,r,2],yaw_rad=yaw[i,r],speed_mps=np.linalg.norm(v[i,r]),terrain_slope_deg=np.degrees(np.arctan(slope.reshape(-1,2)[i,r])),footprint_supported=1)
          for i,time in enumerate(t) for r in range(2)]
    table(output_dir/"route_20hz.csv",rows)
    stats=dict(duration_s=DURATION,source_rate_hz=1,reference_rate_hz=20,n_support_nodes=int(terrain.mask.sum()),total_nodes=terrain.mask.size,n_observed_eroded_nodes=int(terrain.inner_mask.sum()),
               support_test="full observed 7x7 raw-data Gaussian smoothing stencil at each of the four cell corners; continuous supported rectangle encloses both footprints",
               n_raw_returns=terrain.raw_points,full_smoothing_kernel_nodes=terrain.full_kernel_count,raw_reconstruction_max_height_difference_m=0.0,
               enclosing_rectangle_m=domain,analytic_speed_bounds_mps=speed_bounds.tolist(),
               arc_lengths_m=np.linalg.norm(np.diff(xy,axis=0),axis=2).sum(axis=0).tolist(),
               max_sampled_speeds_mps=np.linalg.norm(v,axis=2).max(axis=0).tolist(),
               max_route_slope_deg=np.degrees(np.arctan(slope.reshape(-1,2).max(axis=0))).tolist(),
               min_pair_separation_m=float(np.min(np.linalg.norm(xy[:,0]-xy[:,1],axis=1))),
               compiled_speed_limit_mps=.25)
    return t[::20],xyz[::20],stats


def build(source_dir, output_dir):
    for name, expected in SOURCE_HASHES.items():
        actual = sha(source_dir / name)
        if actual != expected:
            raise ValueError(f"Unexpected SHA-256 for {name}: {actual}")
    for path in (output_dir/"observations",output_dir/"reference"):
        path.mkdir(exist_ok=True,parents=True)
    terrain=Terrain(source_dir)
    times,xyz,meta=geometry(terrain, output_dir)
    assert np.all(np.diff(times)==1)
    phase=["nominal" if t<30 else "fault" if t<60 else "recovery" for t in times]
    ramp=np.where((times>=30)&(times<60),np.minimum(.3,.02*(times-29)),0)
    geom=[]; manifest=[]
    for li, points in LAYOUTS.items():
        points=np.array(points); mz,support,_=terrain.query(points)
        assert support.all()
        anchors=np.column_stack((points,mz+1.20))
        true_ranges=[]; statuses=[]
        for i,t in enumerate(times):
            edges=[(rover,a) for rover in xyz[i] for a in anchors]+[(xyz[i,0],xyz[i,1])]
            this_ranges=[];this_status=[]
            for name,(p,q) in zip(LINKS,edges):
                label,gap=terrain.segment(p,q)
                geom.append(dict(layout=li,t_s=t,link=name,los=int(label=="LOS"),status=label,
                                 min_vertical_clearance_m=gap,slant_range_m=np.linalg.norm(p-q)))
                this_status.append(label);this_ranges.append(np.linalg.norm(p-q))
            true_ranges.append(this_ranges);statuses.append(this_status)
        st=np.array(statuses)
        true_ranges=np.array(true_ranges)
        for si,seed in enumerate(SEEDS,start=1):
            rng=np.random.Generator(np.random.PCG64(seed))
            # Exact same draws across layouts and paired conditions; truth and intervention labels are saved separately.
            prior=xyz[0,:,:2]+rng.normal(0,SIGMAS["sigma_prior"],(2,2))
            motion=np.diff(xyz[:,:,:2],axis=0)+rng.normal(0,SIGMAS["sigma_motion"],(len(times)-1,2,2))
            noise=rng.normal(0,SIGMAS["sigma_range"],(len(times),9))
            for code,bias in [('N',np.zeros(len(times))),('F',ramp)]:
                run=f"{li}_{code}_S{si}"
                ranges=true_ranges+noise
                ranges[:,8]+=bias
                measured=[[float(val) if status=="LOS" else None for val,status in zip(row,vis)] for row,vis in zip(ranges,st)]
                obs=dict(id=run,times_s=times.tolist(),anchors=anchors.tolist(),heights=xyz[:,:,2].tolist(),
                         ranges=measured,increments=motion.tolist(),prior=prior.tolist(),**SIGMAS)
                ref=dict(id=run,times_s=times.tolist(),xyz=xyz.tolist(),phase=phase,peer_injected_m=bias.tolist(),
                         layout=li,condition="nominal" if code=="N" else "peer_ramp_hold_remove",seed=seed,
                         route="constructed_opposing_traverses",motion_source="analytic",geometry_file="link_geometry.csv")
                op=output_dir/"observations"/(run+".json.gz");rp=output_dir/"reference"/op.name
                dump(op,obs);dump(rp,ref)
                manifest.append(dict(run=run,seed=seed,observation_sha256=sha(op),reference_sha256=sha(rp)))
    table(output_dir/'link_geometry.csv',geom)
    table(output_dir/'manifest.csv',manifest)
    meta.update(terrain_sha256=sha(source_dir/"terrain.npz"),raw_cloud_sha256=sha(source_dir/"CLOUD_SUPPORT.npz"),layouts=LAYOUTS,antenna_height_m=1.16,anchor_mast_height_m=1.20,seed_list=SEEDS,
                epochs_per_run=len(times),runs=len(manifest),unique_link_segments=len(geom),
                link_status_counts={lab:sum(row["status"]==lab for row in geom) for lab in ("LOS","NLOS","unknown")},
                min_vertical_clearance_m=min(r["min_vertical_clearance_m"] for r in geom if r["min_vertical_clearance_m"] is not None))
    (output_dir/'protocol_summary.json').write_text(json.dumps(meta,indent=2)+'\n')
    return meta

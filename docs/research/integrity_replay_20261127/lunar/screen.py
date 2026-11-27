"""Test a fixed opaque synthetic screen without modifying the frozen terrain or primary observations."""
import gzip
import json
import numpy as np

from generate import LINKS, Terrain, dump, sha, table

CENTRE=np.array([19.,1.55])
HALF_EXTENTS=np.array([.9,.07])
HEIGHT=1.8


def intersects(p,q,lo,hi):
    # Parametric clipping against an axis-aligned closed finite box.
    enter,leave=0.,1.
    for start,delta,a,b in zip(p,q-p,lo,hi):
        if abs(delta)<1e-13:
            if start<a or start>b:
                return False
        else:
            near,far=sorted([(a-start)/delta,(b-start)/delta])
            enter=max(enter,near);leave=min(leave,far)
            if enter>leave:
                return False
    return True


def windows(mask):
    diff=np.diff(np.r_[0,mask,0].astype(int))
    return list(zip(np.flatnonzero(diff==1).tolist(), (np.flatnonzero(diff==-1)-1).tolist()))


def build(source_dir, primary_dir, output_dir):
    for part in ("observations","reference"):
        (output_dir/part).mkdir(parents=True,exist_ok=True)
    obs=json.load(gzip.open(primary_dir/"observations/L1_N_S1.json.gz"))
    ref=json.load(gzip.open(primary_dir/"reference/L1_N_S1.json.gz"))
    xyz=np.array(ref["xyz"]);anchors=np.array(obs["anchors"]);terrain=Terrain(source_dir)
    # Sink the screen base below every point in the height grid. The top centre
    # is exactly 1.80 m above the reconstructed ground at its centre.
    top=terrain.query(CENTRE)[0].item()+HEIGHT
    lo=np.r_[CENTRE-HALF_EXTENTS,terrain.z.min()-.02]
    hi=np.r_[CENTRE+HALF_EXTENTS,top]
    route=np.genfromtxt(primary_dir/"route_20hz.csv",delimiter=",",names=True)
    xy=np.column_stack((route["x_m"],route["y_m"]))
    centre_dist=np.linalg.norm(np.maximum(np.abs(xy-CENTRE)-HALF_EXTENTS,0),axis=1)
    # Every instant is within .025 s of a checked pose and speed <= .25 m/s.
    min_body_clear=float(centre_dist.min()-.5-.25*.025)
    assert min_body_clear>0 and np.all((hi-lo)>0)
    hit=[];rows=[]
    for i,pair in enumerate(xyz):
        edges=[(r,a) for r in pair for a in anchors]+[tuple(pair)]
        flags=[intersects(p,q,lo,hi) for p,q in edges];hit.append(flags)
        for link,flag in zip(LINKS,flags):
            rows.append(dict(layout="L1",t_s=ref["times_s"][i],link=link,
                  terrain_los=1,synthetic_screen_blocked=int(flag),range_observed=int(not flag)))
    hit=np.array(hit);blocked=hit.any(axis=1)
    assert not blocked[0] and not blocked[-1] and hit.any()
    assert not hit[:,8].any()  # the independently generated UWB peer signal remains nominal
    table(output_dir/"link_geometry.csv",rows)
    w=windows(blocked); meta=dict(runs=3,description="Fixed synthetic opaque screen; crossing with 3D path causes missing range only",
           centre_xy_m=CENTRE.tolist(),width_x_m=2*HALF_EXTENTS[0],thickness_y_m=2*HALF_EXTENTS[1],height_above_ground_centre_m=HEIGHT,
           box_min_xyz_m=lo.tolist(),box_max_xyz_m=hi.tolist(),minimum_conservative_body_clearance_m=min_body_clear,
           any_blocked_measurement_windows_s=w,unique_blocked_links_by_window={n:windows(hit[:,i]) for i,n in enumerate(LINKS) if hit[:,i].any()},
           blocked_range_count_per_realisation=int(hit.sum()),affected_epochs_per_realisation=int(blocked.sum()),
           matched_unobstructed_observations="primary_inputs/observations/L1_N_S{1,2,3}.json.gz",peer_bias_m=0.)
    manifest=[]
    for si in range(1,4):
        baseline=f'L1_N_S{si}.json.gz';run=f'L1_B_S{si}'
        ob=json.load(gzip.open(primary_dir/'observations'/baseline));rf=json.load(gzip.open(primary_dir/'reference'/baseline))
        for tick,link in zip(*np.where(hit)):
            ob['ranges'][tick][link]=None
        ob['id']=rf['id']=run;rf['condition']='synthetic_screen_missing_only';rf['screen_blocked']=blocked.tolist()
        rf['phase']=['occluded' if value else 'nominal' if i<w[0][0] else 'recovery' for i,value in enumerate(blocked)]
        op=output_dir/'observations'/(run+'.json.gz');rp=output_dir/'reference'/op.name;dump(op,ob);dump(rp,rf)
        manifest.append(dict(run=run,seed=rf['seed'],observation_sha256=sha(op),reference_sha256=sha(rp),paired_baseline_sha256=sha(primary_dir/'observations'/baseline)))
    table(output_dir/'manifest.csv',manifest)
    (output_dir/'protocol_summary.json').write_text(json.dumps(meta,indent=2)+'\n')
    return meta

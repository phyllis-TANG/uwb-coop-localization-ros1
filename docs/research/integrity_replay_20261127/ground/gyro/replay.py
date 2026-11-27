"""Causal wheel / synthetic gyro display propagation at frozen UWB updates."""
import argparse, csv, json, math
from collections import defaultdict
from pathlib import Path
import numpy as np
from scipy.stats import norm

DT=.05
REF=20
SIZE=1280
SIG_W=.0008
SIG_XY=.002
H0=np.radians(2.)
WMAX=.10
VMAX=.12
BUDGET=.001
# Independent stationary calibration of 100 scalar angular-rate readings.
NCAL=100
# Each tuple is (rate noise SD in rad/s, constant offset magnitude in rad/s,
# maximum postcalibration offset shift in rad/s, fixed delivery lag in ms).
PROFILES={
 'wheel_only':(0.,0.,0.,0), 'gyro_nominal':(.004,.012,0.,10),
 'gyro_noisy':(.030,.040,0.,10), 'gyro_bias_shift':(.004,.012,.010,10),
 'gyro_delayed':(.004,.012,0.,160)}
SCENES=('nominal','wall','peer_step','peer_ramp')
SEEDS=(2026111901,2026111902)
REPLICATES=12
ROOT=Path(__file__).resolve().parent
CLOCK=np.arange(SIZE)
K2=63*41
ZG=norm.isf(BUDGET/(6*(1281-REF)))
ZL=norm.isf(BUDGET/(6*K2))
QXY=np.sqrt(2.*np.log(3*K2/BUDGET))


def rot(yaw, xy):
    x,y=np.moveaxis(np.asarray(xy),-1,0)
    c,s=np.cos(yaw),np.sin(yaw)
    return np.stack((c*x-s*y,s*x+c*y),axis=-1)


def analytic_truth(robot, template):
    """Original path equation, solely for the sensor emulator and scoring."""
    model=template['models'][f'car{robot+1}']
    u=np.arange(1281)*DT-1.
    theta=np.radians(model['initial_heading_deg'])
    lever=np.array(model['base_to_antenna_body_xy_m'])
    base0=np.array(model['start_antenna_xyz_m'][:2])-rot(theta,lever)
    if robot==0:
        d=np.stack((.85*np.sin(.055*u)+.25*np.sin(.16*u),.45*np.sin(.09*u)),axis=-1)
        yaw=theta+.5*np.sin(.1*u)+.2*np.sin(.18*u)
    else:
        d=np.stack((.65*np.sin(.08*u),.8*np.sin(.06*u)+.15*np.sin(.19*u)),axis=-1)
        yaw=theta-.45*np.sin(.085*u)+.18*np.sin(.17*u)
    return base0+d+rot(yaw,lever),yaw


def sensor_tapes(ground_seed, robot, replica):
    """Separate reproducible gyro streams. Identical normalized draws across profiles."""
    rng=np.random.default_rng(np.random.SeedSequence([734026,ground_seed,robot,replica]))
    return rng.standard_normal(NCAL),rng.standard_normal(1280)


def emulate_gyro(true_yaw, tapes, profile, robot):
    """Independent stationary calibration and moving angular-rate data."""
    sigma,bias,shift,_=PROFILES[profile]
    sign=1 if robot==0 else -1
    cal,moving=tapes
    return sign*bias+sigma*cal, np.diff(true_yaw)/DT+sign*(bias+shift)+sigma*moving


def estimate(body,dwheel,yaw_prior,lever,gyro_cal,gyro_rate,profile):
    """Estimator only sees measured increments, independent calibration and prior."""
    sigma,_,_,_=PROFILES[profile]
    if profile=='wheel_only':
        w=0.; dpsi=dwheel.copy()
    else:
        w=SIG_W**2/(SIG_W**2+(sigma*DT)**2)
        dpsi=(1.-w)*dwheel+w*(gyro_rate-gyro_cal.mean())*DT
    rel=np.r_[0.,np.cumsum(dpsi)]
    yaw=yaw_prior+rel-rel[REF]
    base=np.vstack((np.zeros(2),np.cumsum(rot(yaw[:-1],body),axis=0)))
    antenna=base+rot(yaw,lever)
    return antenna,yaw,w


def margin(n,k,lag,lever,dist,w,profile):
    """Motion-only simultaneous bound for this one sensor policy and robot/run."""
    sigma,_,shift,_=PROFILES[profile]
    step_sd=np.hypot((1.-w)*SIG_W,w*sigma*DT)
    cal_sd=w*sigma/np.sqrt(NCAL)
    elapsed=(k-REF)*DT
    delta=n*DT
    absolute=np.minimum(2.,ZG*np.sqrt(H0**2+(k-REF)*step_sd**2+(elapsed*cal_sd)**2)
                        +elapsed*w*shift)
    change=np.minimum(2.,ZL*np.sqrt(n*step_sd**2+(delta*cal_sd)**2)+delta*w*shift)
    v_antenna=VMAX+lever*WMAX
    statistical=(VMAX*delta*absolute + QXY*SIG_XY*np.sqrt(n)
                 +lever*(absolute*np.minimum(2.,WMAX*delta)+change)+v_antenna*lag)
    return np.minimum(statistical,dist+v_antenna*(delta+lag))


def current_packets(recv_ns,profile):
    times=(CLOCK*50_000_000).astype(np.int64)
    if profile!='wheel_only':
        # Per-step gyro timestamp denotes the end of the angular integration interval.
        hdr=np.arange(len(recv_ns),dtype=np.int64)*50_000_000
        recv_ns=np.maximum(recv_ns,hdr+int(PROFILES[profile][3])*1_000_000)
    k=np.searchsorted(recv_ns,times,side='right')-1
    assert np.all((k<0)|(recv_ns[np.maximum(k,0)]<=times))
    return k


def displacement(antenna,sources,ticks,usable,lever,w,profile):
    at=np.maximum(usable[ticks],sources)
    # If the synchronized packet for the source has not arrived yet, hold: this
    # branch returns zero increment independently of all as-yet unavailable data.
    has=usable[ticks]>=sources
    d=np.zeros((len(ticks),2))
    d[has]=antenna[at[has]]-antenna[sources[has]]
    lag=(ticks-at)*DT; n=at-sources
    growth=margin(n,at,lag,lever,np.linalg.norm(d,axis=1),w,profile)
    return d,growth,has,at


def rows_to_csv(path,rows):
    with path.open('w',newline='') as f:
        sw=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');sw.writeheader();sw.writerows(rows)


def norm_xy(a): return np.linalg.norm(a,axis=-1)


def observed(ages,out):
    template=json.loads((ROOT/'inputs/trajectory_template.json').read_text())
    stats=defaultdict(list)
    for seed in SEEDS:
        obs=np.load(ROOT/f'inputs/wheel_{seed}.npz')
        inputs={x:np.load(ages/f'{seed}_{x}_sources.npz') for x in SCENES}
        truthsets={x:np.load(ages/f'{seed}_{x}_truth.npz')['truth'] for x in SCENES}
        for r in range(2):
            raw=obs['pose'][r]; lever=obs['lever_xy'][r]; lev=norm_xy(lever)
            body=rot(-raw[:-1,2],np.diff(raw[:,:2],axis=0)); dwheel=np.diff(np.unwrap(raw[:,2]))
            prior=obs['initial_heading_rad'][r]
            actual_xy,actual_yaw=analytic_truth(r,template)
            for sc,truth in truthsets.items():
                np.testing.assert_allclose(truth[:,r],actual_xy[:SIZE],rtol=0,atol=1.e-12)
            for a in inputs.values():
                np.testing.assert_array_equal(a['odo_recv_ns'][r],inputs['nominal']['odo_recv_ns'][r])
            masks={}
            for sc,a in inputs.items():
                j=np.searchsorted(a['ready'][1],CLOCK*DT,side='right')-1
                ok=(j>=0)&a['accepted'][1,np.maximum(0,j)]&(CLOCK<=(j+1)*20+40)
                ticks=CLOCK[ok]; j=j[ok]; s=(j+1)*20
                masks[sc]=ticks,j,s
            for profile in PROFILES:
                usable=current_packets(inputs['nominal']['odo_recv_ns'][r],profile)
                for rep in range(REPLICATES if profile!='wheel_only' else 1):
                    cal,rate=emulate_gyro(actual_yaw,sensor_tapes(seed,r,rep),profile,r)
                    ant,hd,w=estimate(body,dwheel,prior,lever,cal,rate,profile)
                    if profile=='wheel_only':
                        expected=inputs['nominal']['odo_xy'][r]
                        np.testing.assert_allclose(ant-ant[REF],expected,rtol=0,atol=1.e-12)
                    for sc,a in inputs.items():
                        ticks,ep,s=masks[sc]
                        d,g,has,at=displacement(ant,s,ticks,usable,lev,w,profile)
                        e=norm_xy(a['pos'][1,r,ep]+d-actual_xy[ticks])
                        err=norm_xy(d-(actual_xy[ticks]-actual_xy[s]))
                        rad=a['hpl'][1,r,ep]+g
                        heading=np.full(len(at),np.nan)
                        heading[has]=np.abs(np.angle(np.exp(1j*(hd[at[has]]-actual_yaw[at[has]]))))
                        # heading is scored at the last used packet, position at display time
                        for group,mask in [('all',np.ones(len(ticks),bool)),
                                           ('slow_yaw',np.abs(np.gradient(actual_yaw,DT)[ticks])<=.015),
                                           ('fast_yaw',np.abs(np.gradient(actual_yaw,DT)[ticks])>=.050)]:
                            vals=(e[mask],err[mask],rad[mask],g[mask],heading[mask],has[mask])
                            stats[profile,r,group].append(vals)
    rows=[]
    for (name,r,group),parts in stats.items():
        e,err,rad,g,head,has=[np.concatenate(p) for p in zip(*parts)]
        nrep=1 if name=='wheel_only' else REPLICATES
        rows.append(dict(profile=name,robot=r+1,motion_group=group,gyro_draws=nrep if name!='wheel_only' else 0,
                         issued_ticks_per_draw=len(e)//nrep,pooled_scored_ticks=len(e),
                         task_ticks_per_draw=10240 if group=='all' else '',hpl_exceedances=int(np.sum(e>rad)),
                         movement_exceedances=int(np.sum(err>g)),median_pe_cm=100*np.median(e),
                         p95_pe_cm=100*np.quantile(e,.95),median_move_error_cm=100*np.median(err),
                         p95_move_error_cm=100*np.quantile(err,.95),median_radius_cm=100*np.median(rad),
                         p95_radius_cm=100*np.quantile(rad,.95),p95_packet_heading_error_deg=np.degrees(np.nanquantile(head,.95)),
                         held_for_gyro_fraction=float(np.mean(~has)),
                         available_at_50cm_pct=100*np.sum(rad<=.5)/(10240*nrep) if group=='all' else ''))
    rows_to_csv(out/'ground_summary.csv',rows)
    for r in (1,2):
        w=next(x for x in rows if x['profile']=='wheel_only' and x['robot']==r and x['motion_group']=='all')
        assert w['issued_ticks_per_draw']==9868 and round(w['available_at_50cm_pct'],2)==(43.87,39.34)[r-1]


def controls(out):
    """Exactly straight and constant-turn controls. Only displacement (no simulated HPL)."""
    ticks=CLOCK[40:]; source=ticks-20; lever=np.array([.12,-.08]); speed=.10
    recv=np.arange(1281)*50_000_000+10_000_000
    use={name:current_packets(recv,name) for name in PROFILES}
    records=[]
    for scenario,omega in [('straight',0.),('constant_turn',.10)]:
        t=np.arange(1281)*DT
        yaw=omega*(t-t[REF]); p=np.empty((1281,2))
        if omega:
            p[:,0]=speed*np.sin(yaw)/omega; p[:,1]=speed*(1-np.cos(yaw))/omega
        else:
            p[:,0]=speed*t;p[:,1]=0
        xy=p+rot(yaw,lever); correct_body=rot(-yaw[:-1],np.diff(p,axis=0))
        for profile in PROFILES:
            metrics=[]
            for rep in range(24):
                rng=np.random.default_rng(np.random.SeedSequence([930011,rep]))
                body=correct_body+rng.normal(0,SIG_XY,correct_body.shape)
                dwheel=np.diff(yaw)+rng.normal(0,SIG_W,1280)
                prior=yaw[REF]+rng.normal(0,H0)
                cal,rate=emulate_gyro(yaw,sensor_tapes(25000,0,rep),profile,0)
                ant,head,w=estimate(body,dwheel,prior,lever,cal,rate,profile)
                d,g,has,at=displacement(ant,source,ticks,use[profile],norm_xy(lever),w,profile)
                e=norm_xy(d-(xy[ticks]-xy[source]))
                h=np.abs(np.angle(np.exp(1j*(head[at]-yaw[at]))))
                metrics.append((e,g,h))
            e,g,h=map(np.concatenate,zip(*metrics))
            records.append(dict(path=scenario,profile=profile,independent_sensor_runs=24,
                                one_second_windows_per_run=len(ticks),pooled_windows=len(e),
                                p95_motion_error_cm=100*np.quantile(e,.95),median_motion_error_cm=100*np.median(e),
                                p95_heading_error_deg=np.degrees(np.quantile(h,.95)),
                                median_motion_allowance_cm=100*np.median(g),motion_exceedances=int(np.sum(e>g))))
    rows_to_csv(out/'controlled_motion.csv',records)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--age-inputs',type=Path,default=ROOT.parent/'age/inputs')
    p.add_argument('--out',type=Path,default=ROOT/'results')
    p.add_argument('--controls-only', action='store_true', help='Run the two synthetic trajectories; no input archive is needed')
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    if not a.controls_only:
        observed(a.age_inputs, a.out)
    controls(a.out)

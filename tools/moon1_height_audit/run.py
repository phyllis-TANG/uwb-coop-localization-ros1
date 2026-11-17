#!/usr/bin/env python3
"""Rebuild and audit a local Moon_1 sample. No localization solver is called."""
import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from datetime import datetime, timezone

import numpy as np
from geometry import STRATA, load_csv, metrics, raw_grid, support, summary

ROOT = Path(__file__).resolve().parents[2]
SIM = ROOT/'sim/isaac_lab/moon1'
sys.path.insert(0,str(SIM))
from prepare_moon1 import read_ply
from antenna_geometry import positions
from make_uwb_replay import resample


def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,np.ndarray):return clean(x.tolist())
    if isinstance(x,np.generic):return clean(x.item())
    if isinstance(x,Path):return str(x)
    return x


def write_json(path,obj):
    path.write_text(json.dumps(clean(obj),indent=2,ensure_ascii=False,allow_nan=False)+'\n')


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def identity(path):
    p=Path(path)
    return dict(path=str(p.resolve()),exists=p.is_file(),bytes=p.stat().st_size if p.is_file() else None,
                sha256=sha(p) if p.is_file() else None)


def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()


def write_csv(path,rows):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def compare_array(a,b):
    result=dict(old_shape=list(a.shape),new_shape=list(b.shape),old_dtype=str(a.dtype),new_dtype=str(b.dtype))
    if a.shape!=b.shape:return dict(result,equal=False,max_abs_difference=None)
    return dict(result,equal=bool(np.array_equal(a,b)),max_abs_difference=float(np.max(np.abs(a.astype(float)-b.astype(float)))) if a.size else 0)


def inventory(paths):
    records=[]
    for p in paths:
        r=identity(p)
        if p.is_file() and p.suffix=='.npz':
            with np.load(p,allow_pickle=False) as n:r['arrays']={k:dict(shape=list(n[k].shape),dtype=str(n[k].dtype)) for k in n.files}
        if p.is_file() and p.suffix=='.csv':
            with p.open() as f:
                reader=csv.DictReader(f);rows=list(reader)
                r.update(fields=reader.fieldnames,rows=len(rows))
                if rows and 'time_s' in rows[0]:r['time_range_s']=[float(rows[0]['time_s']),float(rows[-1]['time_s'])]
        records.append(r)
    return records


def analyze(data,raw,times,leader,follower,name,fixed):
    antennas=[positions(data,track)[1] for track in (leader,follower)]
    sup=[support(data,track[:,:2],raw) for track in (leader,follower)]
    m=metrics(*antennas,fixed)
    unsmoothed=[a.copy() for a in antennas]
    for i in range(2):unsmoothed[i][:,2]=sup[i]['unsmoothed_z']+1.16
    before=metrics(*unsmoothed,fixed)
    ranks=np.maximum(sup[0]['rank'],sup[1]['rank'])
    rows=[]
    traces=[]
    for i,t in enumerate(times):
        row=dict(sequence=name,index=i,time_s=float(t),stratum=STRATA[ranks[i]])
        row.update({k:float(v[i]) for k,v in m.items() if k!='coincident'})
        row.update(coincident=bool(m['coincident'][i]),unsmoothed_ignore_error_m=float(before['ignore_error_m'][i]),
                   smoothing_error_change_m=float(m['ignore_error_m'][i]-before['ignore_error_m'][i]))
        for c in range(2):
            for j,axis in enumerate('xyz'):row[f'car{c+1}_{axis}_m']=float(antennas[c][i,j])
            for k in ['raw_point_distance_m','fill_mass','reflected','clipped','outside','clip_shift_m']:
                row[f'car{c+1}_{k}']=clean(sup[c][k][i])
            row[f'car{c+1}_smoothing_dz_m']=float(antennas[c][i,2]-1.16-sup[c]['unsmoothed_z'][i])
            traces.append(dict(sequence=name,index=i,car=c+1,time_s=float(t),**{k:clean(v[i]) for k,v in sup[c].items()}))
        rows.append(row)
    stats=[]
    for label in ['all',*STRATA]:
        mask=np.ones(len(times),bool) if label=='all' else ranks==STRATA.index(label)
        vals=dict(m,unsmoothed_ignore_error_m=before['ignore_error_m'],smoothing_error_change_m=m['ignore_error_m']-before['ignore_error_m'])
        for k,v in vals.items():
            if k not in ('coincident','analytic_error_m','fixed_range_m'):
                stats.append(dict(sequence=name,stratum=label,metric=k,**summary(v[mask])))
    return rows,traces,stats,antennas


def figures(out,data,rows,stats):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figdir=out/'figures';figdir.mkdir()
    selected=[r for r in rows if r['sequence']=='resampled_20hz']
    t=np.array([r['time_s'] for r in selected])
    v=data['vertices'].reshape(*data['grid_shape'],3)
    fig,ax=plt.subplots(figsize=(11,4.5),layout='constrained')
    ax.pcolormesh(v[:,:,0],v[:,:,1],data['observed'].astype(int),cmap='Greys',vmin=0,vmax=1,shading='nearest',alpha=.4)
    colors=['#147d64','#d58b12','#c34731','#792caf']
    for c in (1,2):
        x=np.array([r[f'car{c}_x_m'] for r in selected]);y=np.array([r[f'car{c}_y_m'] for r in selected])
        ax.plot(x,y,ls='-' if c==1 else '--',color='#244969',lw=1,label=f'Car {c}')
        for s,color in zip(STRATA,colors):
            mask=np.array([r['stratum']==s for r in selected]);ax.scatter(x[mask],y[mask],s=8,color=color,label=s if c==1 else None)
    ax.set(xlabel='x (m)',ylabel='y (m)',title='Moon_1 simulated data: gray=observed cells; white=filled cells')
    ax.axis('equal');ax.legend(fontsize=7,ncol=2);fig.savefig(figdir/'support.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(2,1,figsize=(10,6),sharex=True,layout='constrained')
    for ax,key,label in zip(axes,['delta_z_m','r_xy_m'],['Antenna height difference (m)','Horizontal distance (m)']):
        for name,marker in [('original_replay','.'),('resampled_20hz',None)]:
            rr=[r for r in rows if r['sequence']==name]
            ax.plot([r['time_s'] for r in rr],[r[key] for r in rr],label=name,marker=marker,lw=.9,ms=3)
        ax.set_ylabel(label);ax.grid(alpha=.2);ax.legend(fontsize=8)
    axes[-1].set_xlabel('Simulation time (s)');fig.savefig(figdir/'height_distance.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(2,1,figsize=(10,6),sharex=True,layout='constrained')
    for name in ['original_replay','resampled_20hz']:
        rr=[r for r in rows if r['sequence']==name]
        for ax,key in zip(axes,['ignore_error_m','fixed_error_m']):ax.plot([r['time_s'] for r in rr],np.array([r[key] for r in rr])*1000,label=name,lw=1)
    axes[0].set_ylabel('3D - planar (mm)');axes[1].set_ylabel('3D - fixed dz=-0.03 m (mm)')
    for ax in axes:ax.grid(alpha=.2);ax.legend(fontsize=8);ax.axhline(0,color='gray',lw=.5)
    axes[-1].set_xlabel('Simulation time (s)');fig.savefig(figdir/'mismatch.png',dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,4.5),layout='constrained')
    for i,key in enumerate(['ignore_error_m','fixed_error_m']):
        vv=[next(r for r in stats if r['sequence']=='resampled_20hz' and r['stratum']==s and r['metric']==key) for s in STRATA]
        ax.bar(np.arange(4)+i*.32,[0 if r['rms'] is None else r['rms']*1000 for r in vv],width=.32,label=key)
        if i==0:
            for j,r in enumerate(vv):ax.annotate(f"n={r['n']}"+(" (absent)" if not r['n'] else ''),(j,0),xytext=(0,5),textcoords='offset points',fontsize=8)
    ax.set_xticks(np.arange(4)+.16,[s.replace('_','\n') for s in STRATA],fontsize=8)
    ax.set(ylabel='RMS (mm)',title='Descriptive strata; time samples are not independent trials')
    ax.legend(fontsize=8);fig.savefig(figdir/'strata.png',dpi=160);plt.close(fig)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ply',type=Path,required=True);p.add_argument('--gt',type=Path,required=True)
    p.add_argument('--old-dir',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--config',type=Path,default=ROOT/'docs/research/moon1_height_audit/CONFIG.json')
    args=p.parse_args();out=args.out.resolve()
    if out.exists():raise ValueError('Output must be new; refusing overwrite')
    if out.is_relative_to(ROOT):raise ValueError('Derived artifacts must be outside Git')
    if git('status','--porcelain'):raise ValueError('Commit audit implementation/config before execution')
    cfg=json.loads(args.config.read_text())
    code_files=list(SIM.glob('*.py'))+[ROOT/'ros_ws/src/uwb_coop_localization/scripts/two_car_model.py',ROOT/cfg['fixed_height_source']]
    for path in code_files:
        baseline=subprocess.check_output(['git','show',cfg['generator_commit']+':'+str(path.relative_to(ROOT))],cwd=ROOT)
        if path.read_bytes()!=baseline:raise ValueError('Generator differs from frozen code: '+str(path))
    backend=json.loads((ROOT/cfg['fixed_height_source']).read_text())
    heights=[backend['models'][c]['antenna_height_m'] for c in ['car1','car2']]
    if heights != [cfg['fixed_height_car1_m'],cfg['fixed_height_car2_m']] or not np.isclose(heights[0]-heights[1],cfg['fixed_delta_z_m'],atol=1e-15):
        raise ValueError('Fixed height configuration differs')
    paths=[args.ply,args.gt]+[args.old_dir/n for n in ['moon1_scene.npz','summary.json','uwb_replay.csv','moon1_scene.usda','moon1_scene_v3.usda','moon1_scene_v3_lunar.usda','isaaclab_v3_run.log','provenance.json','uwb_replay.manifest.json','moon1_scene_v3_lunar.manifest.json']]+code_files
    # Only source-adjacent Moon_1 assets; no general personal-directory scan.
    paths+=list((args.gt.parent/'LiDAR').glob('*.txt'))
    source_root=args.ply.parent.parent
    paths += [source_root/n for n in ['archive_manifest.json','results/fusion_metrics.json','fuse_lidar.py','README.md','source/README.md']]
    before=inventory(paths)
    for rec in before[:2]:
        if not rec['exists']:raise FileNotFoundError(rec['path'])
    out.mkdir(parents=True)
    write_json(out/'INPUTS.json',before)
    write_json(out/'CONFIG.json',cfg)
    env=dict(python=sys.version,executable=sys.executable,platform=platform.platform(),packages={n:importlib.metadata.version(n) for n in ['numpy','scipy','matplotlib']},
             thread_env={k:os.environ.get(k) for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','PYTHONDONTWRITEBYTECODE','PYTHONPATH']})
    write_json(out/'ENVIRONMENT.json',env)
    commands=[]
    def call(script,arguments):
        cmd=[sys.executable,str(SIM/script),*map(str,arguments)]
        result=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
        (out/(script+'.log')).write_text(result.stdout+result.stderr)
        commands.append(dict(argv=cmd,cwd=str(ROOT),returncode=result.returncode))
        write_json(out/'COMMANDS.json',commands)
        result.check_returncode()
    scene=out/'scene'
    call('prepare_moon1.py',['--ply',args.ply,'--gt',args.gt,'--output',scene,'--bounds',*cfg['bounds_m'],'--resolution',cfg['resolution_m'],'--max-gt-index',cfg['max_gt_index'],'--follower-delay',cfg['follower_delay_s']])
    call('make_uwb_replay.py',['--scene',scene/'moon1_scene.npz','--output',scene/'uwb_replay.csv','--rate',cfg['rate_hz'],'--noise',cfg['noise_m'],'--bias',cfg['bias_m'],'--nlos-probability',cfg['nlos_probability'],'--nlos-bias',cfg['nlos_bias_m'],'--dropout-probability',cfg['dropout_probability'],'--seed',cfg['seed']])
    with np.load(scene/'moon1_scene.npz',allow_pickle=False) as f:data={k:f[k] for k in f.files}
    comparisons={}
    with np.load(args.old_dir/'moon1_scene.npz',allow_pickle=False) as old:
        comparisons['npz']={k:compare_array(old[k],data[k]) if k in old else {'status':'new_only'} for k in data}
        comparisons['old_only_arrays']=sorted(set(old.files)-set(data))
    old_summary=json.loads((args.old_dir/'summary.json').read_text());new_summary=json.loads((scene/'summary.json').read_text())
    comparisons['summary']={k:dict(old=old_summary.get(k),new=new_summary.get(k),equal=old_summary.get(k)==new_summary.get(k)) for k in old_summary.keys()|new_summary.keys()}
    old_csv=np.genfromtxt(args.old_dir/'uwb_replay.csv',delimiter=',',names=True)
    new_csv=np.genfromtxt(scene/'uwb_replay.csv',delimiter=',',names=True)
    comparisons['csv']={k:compare_array(old_csv[k],new_csv[k]) if k in old_csv.dtype.names else {'status':'new_only'} for k in new_csv.dtype.names}
    comparisons['csv_old_only_fields']=sorted(set(old_csv.dtype.names)-set(new_csv.dtype.names))
    write_json(out/'COMPARISON.json',comparisons)
    parsed=load_csv(scene/'uwb_replay.csv')
    try:load_csv(args.old_dir/'uwb_replay.csv')
    except ValueError as e:legacy=dict(rejected=True,reason=str(e))
    else:legacy=dict(rejected=False,reason='Old CSV already has new schema; inspect version')
    points=read_ply(args.ply)
    raw=raw_grid(points,cfg['bounds_m'],cfg['resolution_m'],cfg['smoothing_sigma_cells'],cfg['smoothing_truncate'])
    np.testing.assert_array_equal(raw['observed'],data['observed'])
    np.testing.assert_array_equal(raw['smooth'].ravel(),data['vertices'][:,2])
    times=data['sim_time']; tick=np.arange(0,times[-1]+1e-9,1/cfg['rate_hz'])
    leader,ly=resample(times,data['leader'],tick);follower,fy=resample(times,data['follower'],tick)
    allrows=[];traces=[];stats=[]
    for t,a,b,name in [(times,data['leader'],data['follower'],'original_replay'),(tick,leader,follower,'resampled_20hz')]:
        rr,tt,ss,_=analyze(data,raw,t,a,b,name,cfg['fixed_delta_z_m']);allrows+=rr;traces+=tt;stats+=ss
    write_csv(out/'TIMESERIES.csv',allrows);write_csv(out/'METRICS.csv',stats)
    write_json(out/'SUPPORT_TRACE.json',traces)
    actual=[np.column_stack([parsed[f'car{c}_{v}'] for v in 'xyz']) for c in (1,2)]
    distances=np.sqrt(np.sum((actual[0]-actual[1])**2,axis=1))
    csv_error=float(np.max(abs(distances-parsed['true_range_m'])))
    assert csv_error<=cfg['csv_rounding_tolerance_m']
    np.testing.assert_allclose(parsed['time_s'],tick,atol=5.1e-7,rtol=0)
    for c,track in [(1,leader),(2,follower)]:
        body,ant=positions(data,track)
        np.testing.assert_allclose(actual[c-1],ant,atol=5.1e-7,rtol=0)
        np.testing.assert_allclose(parsed[f'car{c}_body_z'],body[:,2],atol=1e-12,rtol=0)
        np.testing.assert_allclose(parsed[f'car{c}_gt_z'],track[:,2],atol=1e-12,rtol=0)
    # Independent integer timestamp and coordinate audit, not an import of load_track.
    with args.gt.open() as f:gtrows=[r for r in csv.reader(f) if r and not r[0].startswith('#')]
    stamps=np.array([int(r[0]) for r in gtrows[:cfg['max_gt_index']+1]],dtype=np.int64)
    exact=(stamps-stamps[0])*1e-9
    production=(stamps.astype(float)-float(stamps[0]))*1e-9
    xyz=np.array([[float(v) for v in r[1:4]] for r in gtrows[:len(stamps)]])*[1,-1,-1]
    assert np.all(np.diff(exact)>0)
    np.testing.assert_array_equal(times,production[production<=production[-1]-cfg['follower_delay_s']])
    for key,query in [('leader',times+cfg['follower_delay_s']),('follower',times)]:
        expected=np.column_stack([np.interp(query,production,xyz[:,i]) for i in range(3)])
        np.testing.assert_array_equal(data[key],expected)
    np.testing.assert_allclose(parsed['car1_yaw'],ly,atol=5.1e-7,rtol=0)
    np.testing.assert_allclose(parsed['car2_yaw'],fy,atol=5.1e-7,rtol=0)
    residual_changes={}
    for c in (1,2):
        residual_changes[f'car{c}']=float(np.max(abs((new_csv[f'car{c}_range_m']-new_csv['true_range_m'])-(old_csv[f'car{c}_range_m']-old_csv['true_range_m']))))
    # Only rank of one free 3D pair. No prior, map derivative, pseudoinverse or position estimate.
    diagnostic=[]
    for r,a,b in zip([r for r in allrows if r['sequence']=='resampled_20hz'],*actual):
        d=a-b;norm=np.linalg.norm(d)
        if norm==0:diagnostic.append(dict(time_s=r['time_s'],status='coincident_undefined'));continue
        u=d/norm;j=np.r_[u,-u][None,:];singular=np.linalg.svd(j,compute_uv=False)
        diagnostic.append(dict(time_s=r['time_s'],status='range_only',rank=int(np.sum(singular>1e-12)),nullity=5,singular_value=float(singular[0])))
    write_csv(out/'RANK.csv',diagnostic)
    after=inventory(paths)
    assert before==after,'Input changed during run'
    checks=dict(legacy_csv=legacy,csv_distance_max_error_m=csv_error,formula_max_error_m=max(abs(r['ignore_error_m']-r['analytic_error_m']) for r in allrows),
        timestamp_float_minus_integer_max_s=float(np.max(abs(production-exact))),
        time_pairing='PASS: car1 at t+5, car2 at t; 20Hz resampled from paired NPZ tracks',
        coordinate_transform='PASS: (x,-y,-z); meters, nanoseconds converted to seconds',
        body_gt_antenna_fields='PASS',raw_grid_reconstruction='PASS: mask and smoothed heights exactly equal',
        retained_ply_points=raw['retained'],rejected_ply_points=raw['rejected'],gaussian_radius_cells=raw['radius'],
        input_hashes_unchanged=True,old_new_sample_noise_difference_m=residual_changes,
        independent_time_replicates=False,formal_runs=0,nonlinear_solver_calls=0)
    write_json(out/'CHECKS.json',checks)
    figures(out,data,allrows,stats)
    write_json(out/'RUN.json',dict(utc=datetime.now(timezone.utc).isoformat(),audit_commit=git('rev-parse','HEAD'),generator_commit=cfg['generator_commit'],plan_commit=cfg['plan_commit'],
        branch=git('branch','--show-current'),remote=git('remote','get-url','origin'),argv=sys.argv,cwd=str(Path.cwd()),config_sha256=sha(args.config),
        source_files=[identity(p) for p in sorted(Path(__file__).parent.glob('*.py'))],
        gt_rows=len(gtrows),gt_timestamp_ns=[gtrows[0][0],gtrows[-1][0]],used_gt_timestamp_ns=[str(stamps[0]),str(stamps[-1])],
        coordinate_system='LuSNAR (x,y,z) -> (x,-y,-z); m, s',
        fixed_height_source=identity(ROOT/cfg['fixed_height_source']),
        outputs=[identity(p) for p in sorted(out.rglob('*')) if p.is_file()],formal_runs=0,nonlinear_solver_calls=0,
        historical_provenance='Old hashes identify currently accessible files only; original generation receipts absent',usd='Existing USD inventoried only; no new USD or GUI run'))
    print(json.dumps(checks,indent=2))

if __name__=='__main__':main()

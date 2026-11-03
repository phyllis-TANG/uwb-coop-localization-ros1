"""Portable saved-output verification. Python standard library only.
Run: python verify_bundle.py [package directory]. No estimator or raw bag access.
"""
import json,math,hashlib,sys
from pathlib import Path
ROOT=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parent
checks=0;max_error=0.
def read(p):return json.loads((ROOT/p).read_text(encoding='utf-8-sig'))
def write(p,obj):
    path=ROOT/p;path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def close(a,b):
    global checks,max_error
    if isinstance(a,list):
        assert len(a)==len(b)
        for x,y in zip(a,b):close(x,y)
    else:
        e=abs(a-b);assert e<1e-10,(a,b,e)
        checks+=1;max_error=max(max_error,e)
def avg(v):return sum(v)/len(v)
def meanxy(v):return [avg([p[k] for p in v]) for k in (0,1)]
def mse(v,r):return avg([sum((p[k]-r[k])**2 for k in (0,1)) for p in v])
def pct(v,q):
    v=sorted(v);x=(len(v)-1)*q;i=math.floor(x);j=math.ceil(x)
    return v[i]+(v[j]-v[i])*(x-i)
def main():
    manifest=read('SOURCE_MANIFEST.json')
    for e in manifest['files']:
        assert hashlib.sha256((ROOT/e['destination']).read_bytes()).hexdigest()==e['destination_sha256'],e['destination']
    allstatic=read('static/combined_results.json');masks=[];plot=[];staticrows=[]
    for run in sorted({r['run_id'] for r in allstatic}):
        timelines={};phase_sets={}
        for profile in ('raw','historical'):
            prefix=f'static/runs/{run}/{profile}/'
            t=read(prefix+'trajectory.json');s=read(prefix+'summary.json')
            axes={a:[(r['second'],r['cutoff_ns']) for r in t[a]] for a in ('I','J','W025')}
            assert axes['I']==axes['J']==axes['W025'];assert len(set(axes['I']))==len(axes['I'])
            timelines[profile]=axes['I'];phase_sets[profile]={}
            for phase,(lo,hi) in s['phase_windows_s'].items():
                idx=[i for i,r in enumerate(t['I']) if lo<=r['second']<=hi]
                common=[i for i in idx if all(t[a][i]['accepted'] for a in ('I','J','W025'))]
                phase_sets[profile][phase]=common
                masks.append(dict(run_id=run,profile=profile,phase=phase,window_s=[lo,hi],scheduled_indices=idx,common_indices=common,common_cutoff_ns=[str(t['I'][i]['cutoff_ns']) for i in common]))
                for ci,car in enumerate(('car1','car2')):
                    ref=s['reference'][car];pts={a:[t[a][i]['pose'][ci*3:ci*3+2] for i in common] for a in t}
                    means={a:meanxy(v) for a,v in pts.items()};mses={a:mse(v,ref) for a,v in pts.items()}
                    for arm in ('J','W025'):
                        matches=[r for r in allstatic if (r['run_id'],r['profile'],r['phase'],r['car'],r['arm'])==(run,profile,phase,car,arm)]
                        assert len(matches)==1;r=matches[0]
                        assert r['n_common']==len(common) and r['n_scheduled']==len(idx)
                        close(math.sqrt(mses['I']),r['independent_rmse_m']);close(math.sqrt(mses[arm]),r['arm_rmse_m'])
                        d=mses[arm]-mses['I'];delta=[means[arm][k]-means['I'][k] for k in (0,1)]
                        close(d,r['paired_mean_squared_error_difference_m2']);close(delta,r['mean_arm_minus_I_xy_m'])
                        for a,field in [('I','independent_bias_xy_m'),(arm,'arm_bias_xy_m')]:close([means[a][k]-ref[k] for k in (0,1)],r[field])
                        span=2*math.sqrt(2)*.02*math.hypot(*delta)
                        close([d-span,d+span],[r['reported_reference_assumption']['lower_m2'],r['reported_reference_assumption']['upper_m2']])
                        staticrows.append(dict(run_id=run,profile=profile,phase=phase,car=car,arm=arm,D_m2=d,reference_xy_m=ref,mean_independent_xy_m=means['I'],mean_cooperative_xy_m=means[arm],reference_interval_m2=[d-span,d+span],n_common=len(common)))
                    for a in ('I','J','W025'):
                        plot.append(dict(run_id=run,geometry=run[:2],profile=profile,phase=phase,car=car,method=a,mse_m2=mses[a],mean_antenna_xy_m=means[a],reference_xy_m=ref,n_common=len(common)))
        assert timelines['raw']==timelines['historical']
        assert phase_sets['raw']==phase_sets['historical']
    assert len(staticrows)==160
    write('verification/static_common_times.json',masks)
    write('verification/static_plot_rows.json',plot)
    write('verification/static_pair_rows.json',staticrows)
    five={'G1_R2_N','G1_R3_N','G2_R1_N','G2_R2_N','G2_R3_N'}
    mainplot=[r for r in plot if r['run_id'] in five and r['phase']=='normal' and r['method'] in ('I','J')]
    assert len(mainplot)==40;write('verification/static_main_40_rows.json',mainplot)
    scope_checks=[]
    for target in read('incoming/static_scope_comparison_20.json'):
        scope=target['scope'];phase='normal' if scope in ('five_N_bags_normal','all_10_normal') else 'human' if scope=='human_action_5' else 'recovery'
        selected=[r for r in staticrows if r['phase']==phase and r['car']==target['car'] and r['arm']==target['arm'] and (scope!='five_N_bags_normal' or r['run_id'] in five) and (scope!='recovery_clean_4' or r['run_id']!='G2_R2_W1')]
        effects={};spans={}
        for run in sorted({r['run_id'] for r in selected}):
            a=next(r for r in selected if r['run_id']==run and r['profile']=='raw');b=next(r for r in selected if r['run_id']==run and r['profile']=='historical')
            effects[run]=b['D_m2']-a['D_m2']
            delta=[(b['mean_cooperative_xy_m'][k]-b['mean_independent_xy_m'][k])-(a['mean_cooperative_xy_m'][k]-a['mean_independent_xy_m'][k]) for k in (0,1)]
            spans[run]=2*math.sqrt(2)*.02*math.hypot(*delta)
        groups={g:[r for r in effects if r.startswith(g)] for g in ('G1','G2')}
        means={g:avg([effects[r] for r in group]) for g,group in groups.items()}
        T=means['G2']-means['G1'];span=sum(avg([spans[r] for r in group]) for group in groups.values())
        close(T,target['T_m2']);close([T-span,T+span],[target['reference_low_m2'],target['reference_high_m2']])
        assert len(groups['G1'])==target['n_G1'] and len(groups['G2'])==target['n_G2']
        scope_checks.append(dict(target,recomputed_T_m2=T))
    write('verification/static_scope_20_readback.json',scope_checks)
    # Dynamic: retain original method validity, body-to-antenna transformation and stable windows.
    dev=read('dynamic/development/STOP_COMPARISON.json');res=read('dynamic/reserved/RESERVED_RESULTS.json')
    refs=read('dynamic/reserved/REFERENCES.json');protocol=read('dynamic/reserved/PROTOCOL.json')
    for unit in refs.values():
        for ref in unit.values():
            assert any(e['source'].replace('\\','/')==ref['source_path'].replace('\\','/') and e['source_sha256']==ref['source_sha256'] for e in manifest['files']),ref['source_path']
    rows=[dict(r,unit=r['case'],data_use='development') for r in dev['rows']]+[dict(r,data_use='original_frozen_validation_now_exposed') for r in res['rows']]
    dynmasks=[];dynplot=[]
    for unit in ('A1','B1','A2','B2_PREFIX','B2_CONTINUATION'):
        base=f'dynamic/runs/{unit}/';cfg=read(base+'config.json');methods=('M2','M3','M3W025')
        ts={m:read(base+m+'/trajectory.json') for m in methods}
        times={m:[r['state_ns'] for r in ts[m]] for m in methods}
        assert times['M2']==times['M3']==times['M3W025'];assert len(set(times['M2']))==len(times['M2'])
        for old,h in (dev['source_hashes'] if unit in ('A1','B1') else res['trajectory_sha256']).items():
            if old.replace('\\','/').endswith('/trajectory.json') and '/'+unit+'/' in old.replace('\\','/'):
                assert any(e['source'].replace('\\','/')==old.replace('\\','/') and e['source_sha256']==h for e in manifest['files'])
        for r in [r for r in rows if r['unit']==unit]:
            phase=r['phase'];car=r['car'];ci=('car1','car2').index(car)
            if unit in ('A1','B1'):
                lo,hi=r['window_ns'];ref=r['reference_xy_m'];role='initialization_stop' if phase=='START' else 'post_motion_stop'
            else:
                u=next(u for u in protocol['units'] if u['unit']==unit)
                w=next(w for w in u['evaluation_windows'] if w['phase']==phase)
                lo,hi=w['start_ns'],w['end_ns'];ref=refs[unit][phase][car];role=w['role']
            idx=[i for i,x in enumerate(ts['M2']) if lo<=x['state_ns']<=hi]
            common=[i for i in idx if all(ts[m][i]['valid'][car] and ts[m][i]['pose'] is not None for m in methods)]
            assert len(idx)==r['scheduled_frames'] and len(common)==r['common_valid_frames']
            for m in methods:assert sum(ts[m][i]['valid'][car] for i in idx)==r['own_valid_frames'][m]
            pts={}
            for m in methods:
                pts[m]=[]
                for i in common:
                    x,y,a=ts[m][i]['pose'][4*ci:4*ci+3];lx,ly=cfg['models'][car]['base_to_antenna_body_xy_m']
                    pts[m].append([x+math.cos(a)*lx-math.sin(a)*ly,y+math.sin(a)*lx+math.cos(a)*ly])
                err=[math.dist(p,ref) for p in pts[m]];metrics=r['methods'][m]
                close(math.sqrt(mse(pts[m],ref)),metrics['rmse_m']);close(pct(err,.5),metrics['median_m']);close(pct(err,.95),metrics['p95_m'])
            for m in methods[1:]:
                d=mse(pts[m],ref)-mse(pts['M2'],ref)
                delta=[x-y for x,y in zip(meanxy(pts[m]),meanxy(pts['M2']))];span=2*math.sqrt(2)*.02*math.hypot(*delta)
                close(d,r['paired'][m+'-M2']['mean_squared_error_difference_m2']);close([d-span,d+span],r['paired'][m+'-M2']['sensitivity_interval_m2'])
            dynmasks.append(dict(unit=unit,phase=phase,car=car,window_ns=[str(lo),str(hi)],scheduled_indices=idx,common_indices=common,common_state_ns=[str(times['M2'][i]) for i in common]))
            dynplot.append(dict(r,reference_xy_m=ref,window_ns=[str(lo),str(hi)],stop_role=role,mean_antenna_xy_m={m:meanxy(pts[m]) for m in methods}))
    assert len(dynplot)==32
    write('verification/dynamic_common_times.json',dynmasks);write('verification/dynamic_all_32_stop_rows.json',dynplot)
    report={'status':'PASS','source_files_verified':len(manifest['files']),'static_runs':10,'static_profiles':20,'static_paired_rows_recomputed':160,'external_static_scope_rows_recomputed':len(scope_checks),'static_profile_time_and_mask_equality':True,'dynamic_units':5,'dynamic_trajectory_files':15,'dynamic_stop_car_rows_recomputed':32,'scalar_checks':checks,'max_absolute_error':max_error,'raw_bag_decode':False,'estimator_rerun':False,'continuous_truth_validated':False,'reference_uncertainty':'operator estimate per-axis +/-2cm; conservative sqrt(2)*.02m ball, not confidence interval'}
    write('verification/REPORT.json',report);print(json.dumps(report))
if __name__=='__main__':main()

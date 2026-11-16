"""Independent saved-state readback; no optimization and no formal-input generation."""
import argparse, collections, csv, gzip, hashlib, json, platform, shutil, subprocess, sys
from pathlib import Path
import numpy as np
import scipy
from run import B, CFG, DOC, ROOT, dump, module

def residual(obs,method,x,oracle):
    pts=x[:24].reshape(6,2,2); a=np.array(obs['anchors']); y=np.array(obs['ranges']); vals=[]
    if method=='B3': y=y-np.array(oracle)
    for t in range(6):
        for c in range(2):
            for k in range(4):
                pred=float(np.sqrt(np.sum((pts[t,c]-a[k])**2)))
                if method=='B2' and obs['kind']=='wall' and c==0 and k==0: pred+=x[-1]
                vals.append((pred-y[t*9+c*4+k])/obs['range_sigma'])
        if method!='B0':
            pred=float(np.sqrt(np.sum((pts[t,1]-pts[t,0])**2)))
            if method=='B2' and obs['kind']=='peer': pred+=x[-1]
            vals.append((pred-y[t*9+8])/obs['range_sigma'])
    vals.extend(((np.diff(pts.reshape(6,4),axis=0).ravel()-obs['movement'])/obs['motion_sigma']).tolist())
    if obs['prior_sigma'] is not None: vals.extend(((x[:4]-obs['prior_center'])/obs['prior_sigma']).tolist())
    return np.array(vals)

def writecsv(path,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w') as f:
        w=csv.DictWriter(f,fieldnames=keys,lineterminator="\n");w.writeheader();w.writerows(rows)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--a-root',type=Path,required=True);args=ap.parse_args();out=args.out
    rows=sum([json.loads((out/f'{p}_rows.json').read_text()) for p in ['original','alternatives','supplement']],[])
    units=sum([json.loads((out/f'{p}_inputs.json').read_text()) for p in ['common','supplement']],[]); um={u['id']:u for u in units}
    saved=[]
    for s in json.loads((out/'original_results.json').read_text()): saved.append((s['unit'],s['method'],'P0',s['diagnostics']))
    for p in ['alternatives','supplement']:
        for s in json.loads((out/f'{p}_results.json').read_text()): saved.append((s['unit'],s['method'],s['protocol'],s['result']))
    rm={(r['unit'],r['method'],r['protocol']):r for r in rows}; sm={(i,m,p):r for i,m,p,r in saved}
    checks=dict(formal_runs=0,common_conditions=32,original_solves=128,alternative_solves=256,supplement_conditions=27,supplement_stage_solves=216,independent_recomputed_states=0,max_residual_error=0.,max_gradient_fd_error=0.,max_mse_error=0.,max_cost_error=0.,original_hash_matches=0,original_state_max_difference=0.,original_status_matches=0,near_design_matches=0,controlled_pairs=0)
    for uid,m,p,rec in saved:
        if rec['estimate'] is None: continue
        u=um[uid];x=np.array(rec['estimate']);r=residual(u['obs'],m,x,u['oracle']); row=rm[uid,m,p]
        checks['max_residual_error']=max(checks['max_residual_error'],float(max(abs(r-np.array(rec['residual'])))))
        checks['max_cost_error']=max(checks['max_cost_error'],abs(float(r@r/2)-row['cost']))
        mse=np.mean(np.sum((x[:24].reshape(6,2,2)-u['truth'])**2,axis=2),axis=0)
        checks['max_mse_error']=max(checks['max_mse_error'],abs(float(mse[0])-row['mse_car1']),abs(float(mse[1])-row['mse_car2']))
        # Independent residual finite difference, not finite difference of rounded costs.
        eye=np.eye(len(x)); h=1e-5
        jf=np.column_stack([(residual(u['obs'],m,x+h*e,u['oracle'])-residual(u['obs'],m,x-h*e,u['oracle']))/(2*h) for e in eye])
        checks['max_gradient_fd_error']=max(checks['max_gradient_fd_error'],float(max(abs(jf.T@r-np.array(rec['gradient'])))))
        assert row['accepted']==bool(row['scipy_success'] and row['finite'] and row['gradient_inf']<=1e-5)
        checks['independent_recomputed_states']+=1
    with gzip.open(ROOT/'docs/research/midterm_simulation_s2/UNITS.jsonl.gz','rt') as f: old=[json.loads(s) for s in f]
    for u in units[:32]:
        hit=next(o for o in old if all(o[k]==u[k] for k in ['profile','geometry','motion']) and o['kind']==u['obs']['kind'] and o['bias_m']==u['bias'] and o['seed']==26011601)
        assert hit['observation_sha256']==u['obs_sha256'];checks['original_hash_matches']+=1
        for o in hit['results']:
            rec=sm[u['id'],o['method'],'P0'];checks['original_state_max_difference']=max(checks['original_state_max_difference'],float(max(abs(np.array(o['estimate'])-rec['estimate']))))
            assert o['input_sha256']==rm[u['id'],o['method'],'P0']['input_sha256']
            assert o['success']==rm[u['id'],o['method'],'P0']['accepted']; checks['original_status_matches']+=1
    A=module('fixed_a',args.a_root/'tools/midterm_simulation_s1b/analyze.py')
    for u in units:
        if u['panel']!='supplement':continue
        a,z=A.design(u['geometry'],u['motion']);assert np.array_equal(a,u['obs']['anchors']);assert np.array_equal(z[:24],np.array(u['truth']).ravel());checks['near_design_matches']+=1
    for g in ['good','weak','near']:
        for m in ['static','turn']:
            group={u['profile']:u for u in units if u['panel']=='supplement' and u['geometry']==g and u['motion']==m}
            for left,right,factor in [('none','survey_weak','prior_sigma'),('survey_weak','survey_strong','prior_sigma'),('survey_weak','center_plus_weak','prior_center')]+([('survey_strong','center_plus_strong','prior_center'),('center_plus_weak','center_plus_strong','prior_sigma')] if m=='static' else []):
                a=dict(group[left]['obs']);b=dict(group[right]['obs']);a.pop(factor);b.pop(factor);assert a==b;checks['controlled_pairs']+=1
    checks['bias_translation_max_residual_difference']=0.
    for u in units:
        x=np.array(sm[u['id'],'B2','P1']['estimate']); ob=dict(u['obs']); ob['ranges']=(np.array(ob['ranges'])+.3*B.active(ob['kind'])).tolist(); shifted=x.copy();shifted[-1]+=.3
        dif=float(max(abs(residual(ob,'B2',shifted,u['oracle'])-residual(u['obs'],'B2',x,u['oracle']))))
        checks['bias_translation_max_residual_difference']=max(checks['bias_translation_max_residual_difference'],dif)
    assert checks['bias_translation_max_residual_difference']<1e-11
    assert checks['max_residual_error']<1e-11 and checks['max_gradient_fd_error']<2e-6 and checks['original_state_max_difference']<1e-12
    assert checks['original_hash_matches']==32 and checks['original_status_matches']==128
    assert checks['independent_recomputed_states']==600
    # D and denominator are paired by condition, never by individual time point.
    for r in rows:
        b=rm[r['unit'],'B0',r['protocol']];r['D_car1']=r['mse_car1']-b['mse_car1'];r['D_car2']=r['mse_car2']-b['mse_car2'];r['paired_accepted']=r['accepted'] and b['accepted']
    writecsv(DOC/'PER_RUN.csv',rows)
    ih=[]
    for u in units:
        ih.append(dict(unit=u['id'],panel=u['panel'],geometry=u['geometry'],motion=u['motion'],kind=u['obs']['kind'],bias=u['bias'],profile=u['profile'],seed=26011601,observations_sha256=B.digest(u['obs']),truth_sha256=B.digest(u['truth']),noise_sha256=B.digest(u['noise']),oracle_sha256=B.digest(u['oracle'])))
    writecsv(DOC/'INPUT_HASHES.csv',ih)
    summary=[]
    for panel,protocol in [('common','P0'),('common','P1'),('common','P2'),('supplement','P0'),('supplement','P1')]:
        rs=[r for r in rows if r['panel']==panel and r['protocol']==protocol]
        summary.append(dict(panel=panel,protocol=protocol,n=len(rs),accepted=sum(r['accepted'] for r in rs),finite=sum(r['finite'] for r in rs),statuses=json.dumps(dict(collections.Counter(r['scipy_status'] for r in rs))),warnings=sum(r['warning_count'] for r in rs),limits=sum(r['hit_limit'] for r in rs),exceptions=sum(r['exception'] for r in rs),cost_max=max(r['cost'] for r in rs),gradient_max=max(r['gradient_inf'] for r in rs),scaled_gradient_max=max(r['scaled_gradient_inf'] for r in rs),max_position_delta=max(r['position_change_max_m'] for r in rs),max_bias_delta=max(r['bias_change_m'] for r in rs),max_cost_decrease=max(r['cost_decrease'] for r in rs),material_changes=sum(r['material_change'] for r in rs),nfev_total=sum(r['nfev'] for r in rs),cumulative_nfev_total=sum(r['total_nfev'] for r in rs),elapsed_s=sum(r['elapsed_s'] for r in rs),position_failures=sum(r['position_error_failure'] for r in rs),bias_failures=sum(bool(r['bias_error_failure']) for r in rs)))
    writecsv(DOC/'PROTOCOL_COMPARISON.csv',summary)
    supp=[]
    for r in rows:
        if r['panel']=='supplement' and r['protocol']=='P1':supp.append(r)
    writecsv(DOC/'SUPPLEMENT.csv',supp)
    pairs=[]
    for g in ['good','weak','near']:
        for m in ['static','turn']:
            groups={u['profile']:u['id'] for u in units if u['panel']=='supplement' and u['geometry']==g and u['motion']==m}
            for l,r,factor in [('none','survey_weak','enable_prior'),('survey_weak','survey_strong','weight'),('survey_weak','center_plus_weak','center')]+([('survey_strong','center_plus_strong','center'),('center_plus_weak','center_plus_strong','weight')] if m=='static' else []):
                for method in B.METHODS:
                    x=np.array(sm[groups[l],method,'P1']['estimate']);y=np.array(sm[groups[r],method,'P1']['estimate'])
                    pairs.append(dict(geometry=g,motion=m,method=method,left=l,right=r,factor=factor,position_change_max_m=float(np.max(np.linalg.norm((y-x)[:24].reshape(-1,2),axis=1))),bias_change_m=float(y[-1]-x[-1]) if method=='B2' else None,left_accepted=rm[groups[l],method,'P1']['accepted'],right_accepted=rm[groups[r],method,'P1']['accepted']))
    writecsv(DOC/'CONTROLLED_PAIRS.csv',pairs)
    classification=[]
    for r in rows:
        if r['panel']=='common' and r['protocol']=='P0':
            a=rm[r['unit'],r['method'],'P1'];b=rm[r['unit'],r['method'],'P2']; xa=np.array(sm[r['unit'],r['method'],'P1']['estimate']);xb=np.array(sm[r['unit'],r['method'],'P2']['estimate']);delta=float(np.max(np.linalg.norm((xa-xb)[:24].reshape(-1,2),axis=1)))
            classification.append(dict(unit=r['unit'],method=r['method'],original_accepted=r['accepted'],category='stable_local_stop_difference' if not(a['material_change'] or b['material_change']) else 'material_change',weak_geometry=r['geometry']=='weak',reference_rank=r['reference_data_rank'],final_rank=r['data_rank'],P1_P2_position_difference=delta,branch_sensitive=delta>.001,structural_nonuniqueness='not established; rank deficiency alone insufficient',anomaly=not(a['finite'] and b['finite']) or a['exception'] or b['exception']))
    writecsv(DOC/'STOP_CLASSIFICATION.csv',classification)
    checks['max_P1_P2_position_difference']=max(x['P1_P2_position_difference'] for x in classification)
    checks['all_checks_passed']=True;dump(DOC/'CHECKS.json',checks)
    # Deterministic compressed evidence: full inputs, estimates, gradients, spectra, warnings.
    for name in ['common_inputs','original_results','alternatives_results','supplement_inputs','supplement_results']:
        data=(out/(name+'.json')).read_bytes();(DOC/(name+'.json.gz')).write_bytes(gzip.compress(data,mtime=0))
    source={}
    for base,paths in [(ROOT,['tools/midterm_simulation_s2/prototype.py','tools/midterm_simulation_phase1/identifiability.py','docs/research/midterm_simulation_s2/REPORT.md','docs/research/midterm_simulation_s2/MATH.md','docs/research/midterm_simulation_s2/CONFIG.json','docs/research/midterm_simulation_s2/VALIDATION_PROTOCOL_DRAFT.md']),(args.a_root,['docs/research/midterm_simulation_s1b/REPORT.md','docs/research/midterm_simulation_s1b/S2_INTERFACE.md','docs/research/midterm_simulation_s1b/CONFIG.json','tools/midterm_simulation_s1b/analyze.py'])]:
        for p in paths:source[('A/' if base==args.a_root else 'B/')+p]=hashlib.sha256((base/p).read_bytes()).hexdigest()
    dump(DOC/'SOURCE_LOCK.json',dict(A='ed17e3ad177b5d52c1470e85da9f7a8645dbada9',B='8174445e3b8e473bef15a82d345b7a7e1d94ac05',common='df323eccdffd375a2fb255ebbfd734b6c2be4aac',files=source,plan_sha256=hashlib.sha256((DOC/'NUMERICAL_PLAN.md').read_bytes()).hexdigest()))
    dump(DOC/'ENVIRONMENT.json',dict(python=sys.version,executable=sys.executable,numpy=np.__version__,scipy=scipy.__version__,cwd=str(ROOT),a_readonly_checkout=str(args.a_root),raw_artifacts=str(out),free_bytes=shutil.disk_usage(ROOT).free,applicable_AGENTS=[],process_visibility='sandbox namespace only; no other solver visible; host processes unknown',initial_head='115b17deb2f848e596d1638a0b45cf360deae947',base_head='8174445e3b8e473bef15a82d345b7a7e1d94ac05',remote='https://github.com/phyllis-TANG/uwb-coop-localization-ros1.git',environment_issue='default Python NumPy 2.2.6 / SciPy 1.8.0 incompatible warning; reused original B venv SciPy 1.15.3',checkout_issue='initial full checkout interrupted while partial-clone hydration stalled; recreated no-checkout then sparse docs/tools; no old worktree edited'))
    print(json.dumps(checks,indent=2));print(json.dumps(summary,indent=2))
if __name__=='__main__':main()

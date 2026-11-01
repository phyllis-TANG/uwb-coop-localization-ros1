import dynamic_compare as d
import gzip,json,copy
import numpy as np
base=d.HERE/'B1';out=d.HERE/'anomaly_audit001';cfg=d.read(base/'config.json')
with gzip.open(base/'bins.jsonl.gz','rt',encoding='utf-8') as f:bins=[json.loads(l) for l in f]
original=d.read(base/'M3W025/trajectory.json');m2=d.read(base/'M2/trajectory.json');saved={}
with gzip.open(base/'M3W025/updates.jsonl.gz','rt',encoding='utf-8') as f:
    for i,l in enumerate(f):
        if i in (270,350,483):saved[i]=json.loads(l)['result']
def graph():
    r=saved[270];assert r['accepted_graph'];bb=bins[270-r['graph_states']+1:271];g=d.WeightedGraph(cfg)
    g.prior=d.core.Prior(**{k:np.array(v) for k,v in r['prior'].items()});g.times=[b['second'] for b in bb]
    g.local=[np.array(b['local']) for b in bb];g.observations=[copy.deepcopy(b['wall']) for b in bb];g.peers=[b['peer'] for b in bb]
    g.intervals=[copy.deepcopy(b['intervals']) for b in bb[1:]];g.states=[np.array(s) for s in r['candidate_states']]
    g.marginalizations=r['marginalizations'];g.missing_edges=r['missing_angular_edges_cumulative'].copy();return g
results={}
for condition in ('baseline','diagnostic_remove_car1_node10'):
    g=graph();records=[];maxdiff=0.
    for i in range(271,530):
        b=bins[i];walls=copy.deepcopy(b['wall'])
        if condition!='baseline':walls['car1'].pop('node_10',None)
        g.next_intervals=b['intervals'];r=g.update(b['second'],b['local'],walls,b['peer'])
        if condition=='baseline':
            delta=np.array(r['pose'])-original[i]['pose'];delta[[2,6]]=np.arctan2(np.sin(delta[[2,6]]),np.cos(delta[[2,6]]));maxdiff=max(maxdiff,float(np.max(np.abs(delta))))
            assert maxdiff<1e-7,(i,maxdiff)
        records.append({'index':i,'state_ns':b['state_ns'],'pose':r['pose'],'valid':r['estimate_valid'],'status':r['status'],'cost':r['optimizer'].get('cost')})
    d.write(out/(condition+'.json'),records);results[condition]={'frames':len(records),'baseline_max_pose_difference':maxdiff if condition=='baseline' else None,'end_pose':records[-1]['pose']}
    print(condition,json.dumps(results[condition]),flush=True)
seeds=[]
for i in (350,483):
    r=saved[i];n=r['graph_states'];bb=bins[i-n+1:i+1];prior=d.core.Prior(**{k:np.array(v) for k,v in r['prior'].items()})
    for name,x in [('saved',np.array(r['candidate_states']).ravel()),('M2_saved_publications',np.array([a['pose'] for a in m2[i-n+1:i+1]]).ravel())]:
        obj=d.WeightedObjective([b['second'] for b in bb],[b['local'] for b in bb],[b['wall'] for b in bb],[b['peer'] for b in bb],[b['intervals'] for b in bb[1:]],cfg,prior,True)
        fit=d.least_squares(obj.fun,x,jac=obj.jac,method='trf',tr_solver='exact',loss='linear',max_nfev=cfg['optimizer']['max_nfev'],ftol=1e-7,xtol=1e-7,gtol=1e-7)
        seeds.append({'index':i,'seed':name,'success':bool(fit.success),'nfev':fit.nfev,'cost':float(fit.cost),'end_pose':fit.x[-8:].tolist(),'saved_cost':r['optimizer']['cost']})
results['same_objective_seed_checks']=seeds;d.write(out/'DIAGNOSTIC_RESULTS.json',results);print(json.dumps(seeds),flush=True)

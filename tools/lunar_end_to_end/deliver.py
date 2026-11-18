"""Post-run descriptive tables and CPU scene export; never invokes optimizer."""
import csv,json,shutil,hashlib,tarfile,time,importlib.metadata
from collections import defaultdict
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from inputs import DOC,ART,atomic
from runner import progress
COLORS=['#555555','#2171b5','#f28e2b','#c43939']
def csvwrite(path,rows):
 if not rows:return
 with path.open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def summarize():
 root=ART/'evaluation';plan=json.loads((root/'RUN_PLAN.json').read_text());meta={r['id']:r for r in json.loads((DOC/'INPUT_MANIFEST.json').read_text())};runs=[];full=[];fail=[]
 for task in plan:
  path=root/'results'/f"{task['key']}.json";r=json.loads(path.read_text()) if path.exists() else dict(state='INTERRUPTED' if (root/'attempts'/f"{task['key']}.json").exists() else 'UNEXECUTED');r=dict(**r,meta=meta[task['input_id']],group=task['group']);runs.append(r)
  if r['state']!='ACCEPTED':fail.append(dict(key=task['key'],group=task['group'],state=r['state'],window=r['meta']['window'],seed=r['meta']['seed'],peer=r['meta']['peer'],motion=r['meta']['motion'],method=task['method'],gradient_inf=r.get('gradient_inf'),rank=r.get('rank'),seconds=r.get('seconds'),error=r.get('error','')))
  for c in range(2):
   m=r.get('metrics',{});full.append(dict(key=task['key'],group=task['group'],window=r['meta']['window'],seed=r['meta']['seed'],peer=r['meta']['peer'],motion=r['meta']['motion'],sensitivity=r['meta']['sensitivity'],method=task['method'],car=c+1,state=r['state'],finite=r.get('finite',False),rmse_m=m.get('rmse_m',[None,None])[c],p50_m=m.get('p50_m',[None,None])[c],p95_m=m.get('p95_m',[None,None])[c],max_m=m.get('max_m',[None,None])[c],range_residual_rms_m=m.get('range_residual_rms_m'),bias0_m=m.get('bias0_m'),bias_slope_m_s=m.get('bias_slope_m_s'),gradient_inf=r.get('gradient_inf'),rank=r.get('rank'),dimension=r.get('dimension'),seconds=r.get('seconds'),optimizer_calls=r.get('optimizer_calls_started',0)))
 csvwrite(DOC/'FULL_RESULTS.csv',full);csvwrite(DOC/'FAILURES.csv',fail);atomic(DOC/'FAILURE_LEDGER.json',fail);atomic(DOC/'PROGRESS.json',progress(root,plan));groups=defaultdict(list)
 for r in runs:groups[(r['group'],r['meta']['peer'],r['meta']['motion'],r['meta']['sensitivity'],r['method'])].append(r)
 summaries=[]
 for (group,peer,motion,sens,method),rs in groups.items():
  for subset in ['all_finite','accepted_complete_seed_cluster']:
   clusters=[];selected_rs=[]
   for seed in sorted({r['meta']['seed'] for r in rs}):
    sel=[r for r in rs if r['meta']['seed']==seed]
    if len(sel)!=3 or not all(r.get('finite',False) for r in sel) or (subset!='all_finite' and not all(r['state']=='ACCEPTED' for r in sel)):continue
    clusters.append(np.mean([r['metrics']['rmse_m'] for r in sel],axis=0));selected_rs.extend(sel)
   for c in range(2):summaries.append(dict(group=group,peer=peer,motion=motion,sensitivity=sens,method=method,car=c+1,subset=subset,planned_methods=len(rs),finite=sum(r.get('finite',False) for r in rs),accepted=sum(r['state']=='ACCEPTED' for r in rs),not_accepted=sum(r['state']!='ACCEPTED' for r in rs),seed_clusters=len(clusters),mean_window_rmse_m=float(np.mean(clusters,axis=0)[c]) if clusters else None,min_seed_rmse_m=float(np.min(clusters,axis=0)[c]) if clusters else None,max_seed_rmse_m=float(np.max(clusters,axis=0)[c]) if clusters else None,mean_range_residual_rms_m=float(np.mean([r['metrics']['range_residual_rms_m'] for r in selected_rs]))))
 csvwrite(DOC/'SUMMARY.csv',summaries)
 lookup={(r['meta']['window'],r['meta']['seed'],r['meta']['peer'],r['meta']['motion'],r['meta']['sensitivity'],r['method']):r for r in runs};paired=[];details=[]
 for r in runs:
  m=r['meta'];references=[]
  if r['group']=='core' and r['method']!='M0':references.append(('gain_vs_M0','M0',m['sensitivity']))
  if r['group']=='core' and r['method']=='M3':references.append(('gain_M3_vs_M2','M2',m['sensitivity']))
  if r['group']=='sensitivity':references.append(('gain_vs_control',r['method'],'control'))
  for kind,method,sens in references:
   b=lookup[(m['window'],m['seed'],m['peer'],m['motion'],sens,method)]
   for c in range(2):details.append(dict(kind=kind,window=m['window'],seed=m['seed'],peer=m['peer'],motion=m['motion'],sensitivity=m['sensitivity'],method=r['method'],car=c+1,both_accepted=b['state']==r['state']=='ACCEPTED',both_finite=b.get('finite',False) and r.get('finite',False),gain_m=b['metrics']['rmse_m'][c]-r['metrics']['rmse_m'][c] if b.get('finite',False) and r.get('finite',False) else None))
 csvwrite(DOC/'PAIRS.csv',details);pg=defaultdict(list)
 for x in details:pg[tuple(x[k] for k in ['kind','peer','motion','sensitivity','method','car'])].append(x)
 for key,items in pg.items():
  for subset in ['all_finite','both_accepted_complete_seed_cluster']:
   ss=[]
   for seed in sorted({x['seed'] for x in items}):
    arr=[x for x in items if x['seed']==seed]
    if len(arr)==3 and all(x['both_finite'] and (subset=='all_finite' or x['both_accepted']) for x in arr):ss.append(np.mean([x['gain_m'] for x in arr]))
   paired.append(dict(zip(['kind','peer','motion','sensitivity','method','car'],key),subset=subset,total_pairs=len(items),both_finite_pairs=sum(x['both_finite'] for x in items),both_accepted_pairs=sum(x['both_accepted'] for x in items),seed_clusters=len(ss),mean_gain_m=float(np.mean(ss)) if ss else None,positive_seed_clusters=int(sum(x>0 for x in ss))))
 csvwrite(DOC/'PAIRED_SUMMARY.csv',paired)
 absorption=[]
 for motion in ['correlated','scale','slip_proxy']:
  for method in ['M2','M3']:
   for window in ['W0','W1','W2']:
    arr=[]
    for seed in range(2026111701,2026111711):
     a=lookup[(window,seed,'normal',motion,'control',method)];b=lookup[(window,seed,'normal','white','control',method)];arr.append([a['metrics']['bias0_m']-b['metrics']['bias0_m'],(a['metrics']['bias_slope_m_s'] or 0)-(b['metrics']['bias_slope_m_s'] or 0),int(a['state']==b['state']=='ACCEPTED')])
    absorption.append(dict(window=window,motion=motion,method=method,seed_pairs=10,both_accepted=int(np.sum(arr,axis=0)[2]),mean_bias0_shift_m=float(np.mean(arr,axis=0)[0]),mean_abs_bias0_shift_m=float(np.mean(np.abs(arr),axis=0)[0]),mean_slope_shift_m_s=float(np.mean(arr,axis=0)[1]),mean_abs_slope_shift_m_s=float(np.mean(np.abs(arr),axis=0)[1])))
 csvwrite(DOC/'MOTION_ABSORPTION.csv',absorption)
 sensitivity_bias=[]
 for sens in ['time_plus','time_minus','height_plus','height_minus','missing']:
  for window in ['W0','W1','W2']:
   for method in ['M2','M3']:
    arr=[]
    for seed in range(2026111701,2026111705):
     a=lookup[(window,seed,'normal','white',sens,method)];b=lookup[(window,seed,'normal','white','control',method)];arr.append([a['metrics']['bias0_m']-b['metrics']['bias0_m'],(a['metrics']['bias_slope_m_s'] or 0)-(b['metrics']['bias_slope_m_s'] or 0)])
    sensitivity_bias.append(dict(sensitivity=sens,window=window,method=method,seeds=4,mean_bias0_shift_m=float(np.mean(arr,axis=0)[0]),mean_slope_shift_m_s=float(np.mean(arr,axis=0)[1])))
 csvwrite(DOC/'SENSITIVITY_BIAS.csv',sensitivity_bias)
 atomic(DOC/'NUMERICAL_SUMMARY.json',dict(total_nfev=sum(sum(s['nfev'] for s in r.get('stages',[])) for r in runs),max_gradient=max(r.get('gradient_inf',0) for r in runs),max_method_seconds=max(r.get('seconds',0) for r in runs),all_full_rank=all(r.get('rank')==r.get('dimension') for r in runs),rank_by_method={m:sorted({r['rank'] for r in runs if r['method']==m}) for m in ['M0','M1','M2','M3']},max_endpoint_calls=max(len(r.get('stages',[])) for r in runs)))
 return runs,lookup,summaries,paired

def figures(lookup,summaries):
 figs=DOC/'figures';figs.mkdir(exist_ok=True);data=np.load(ART/'scene.npz');windows=json.loads((DOC/'WINDOWS.json').read_text());low=data['low'];res=float(data['res']);g=data['terrain'];mask=data['observed'];extent=[low[0],low[0]+(g.shape[0]-1)*res,low[1],low[1]+(g.shape[1]-1)*res]
 fig,axs=plt.subplots(2,1,figsize=(13,5),constrained_layout=True);axs[0].imshow(g.T,origin='lower',extent=extent,cmap='terrain',aspect='auto');axs[1].imshow(mask.T,origin='lower',extent=extent,cmap='Greys',aspect='auto')
 for ax in axs:
  ax.plot(data['gt_xyz'][:,0],data['gt_xyz'][:,1],lw=.7,color='red',label='source reference, not verified route')
  for w in windows:
   q=np.array(w['xyz_m']);ax.scatter(q[:,:,0],q[:,:,1],s=12,label=w['id']);ax.annotate(w['id'],q[0,0,:2],xytext=(0,8),textcoords='offset points')
  ax.set(xlabel='moon_map x [m]',ylabel='y [m]');ax.legend(fontsize=7,loc='lower center',ncol=4)
 axs[0].set_title('Rebuilt 10-frame terrain (filled heights included)');axs[1].set_title('Observed nodes dark; white is filled / unobserved');fig.savefig(figs/'scene_coverage.png',dpi=170);plt.close(fig)
 fig,axs=plt.subplots(2,4,figsize=(14,7),constrained_layout=True)
 for j,motion in enumerate(['white','correlated','scale','slip_proxy']):
  for c in range(2):
   ax=axs[c,j]
   for mi,method in enumerate(['M0','M1','M2','M3']):
    vals=[next(r['mean_window_rmse_m'] for r in summaries if r['group']=='core' and r['motion']==motion and r['peer']==peer and r['method']==method and r['car']==c+1 and r['subset']=='all_finite') for peer in ['normal','constant','step','ramp']];ax.plot(range(4),vals,'o-',label=method,color=COLORS[mi])
   ax.set_xticks(range(4),['normal','constant','step','ramp'],rotation=25);ax.set(title=f'{motion}, Car{c+1}',ylabel='Mean window RMSE [m]');ax.grid(alpha=.2)
 axs[0,0].legend();fig.suptitle('All finite endpoints including numerical non-acceptance; 10 seed clusters');fig.savefig(figs/'core_rmse.png',dpi=160);plt.close(fig)
 chosen=[('W0','normal','white'),('W1','constant','scale'),('W2','step','slip_proxy')]
 for wi,peer,motion in chosen:
  w=next(w for w in windows if w['id']==wi);q=np.array(w['xyz_m']);fig,axs=plt.subplots(2,2,figsize=(11,8),constrained_layout=True);ax=axs[0,0];ax.plot(q[:,0,0],q[:,0,1],'k-o',label='reference Car1');ax.plot(q[:,1,0],q[:,1,1],'k--o',label='reference Car2');a=np.array(w['anchors_xyz_m']);ax.scatter(a[:,0],a[:,1],marker='^',label='designed anchors')
  for t in range(6):ax.plot(q[t,:,0],q[t,:,1],color='gray',alpha=.3)
  states=[]
  for mi,method in enumerate(['M0','M1','M2','M3']):
   r=lookup[(wi,2026111701,peer,motion,'control',method)];est=np.array(r['q'][:24]).reshape(6,2,2);states.append(f"{method}: {r['state']}; grad={r['gradient_inf']:.2g}")
   for c in range(2):ax.plot(est[:,c,0],est[:,c,1],color=COLORS[mi],lw=.8);axs[1,c].plot(w['times_s'],np.array(r['metrics']['error_m'])[:,c],label=method,color=COLORS[mi])
  ax.set(xlabel='x [m]',ylabel='y [m]',title=f'{wi}: {peer}/{motion}');ax.legend(fontsize=7)
  ax=axs[0,1];span=np.array(q[:,:,:2]).reshape(-1,2);lims=[span[:,0].min()-3,span[:,0].max()+3,span[:,1].min()-3,span[:,1].max()+3];ax.imshow(mask.T,origin='lower',extent=extent,cmap='Greys',vmin=0,vmax=1);ax.set(xlim=lims[:2],ylim=lims[2:],title='Observed support and selected path',xlabel='x [m]',ylabel='y [m]');ax.plot(q[:,0,0],q[:,0,1],'r-o');ax.plot(q[:,1,0],q[:,1,1],'b-o')
  for c in range(2):
   axs[1,c].set(title=f'Car{c+1} antenna error',xlabel='relative time [s]',ylabel='3D error [m]');axs[1,c].legend()
   if peer=='step':axs[1,c].axvspan(.6,1,color='red',alpha=.1)
   if motion=='slip_proxy':axs[1,c].axvspan(.4,.6,color='orange',alpha=.2)
  fig.suptitle('\n'.join([f'Preselected seed 2026111701; {wi}']+states),fontsize=9);fig.savefig(figs/f'representative_{wi}.png',dpi=160);plt.close(fig)
 # One-page workflow artifact.
 fig,ax=plt.subplots(figsize=(11,3));ax.axis('off');labels=['Sources\nLuSNAR / fixed PRs','Scene & paths\n10 frames, 3 windows','Observations\n540 shared inputs','M0-M3\n2160 runs','Independent readback\nHashes / residuals / states','Evidence\nTables / figures / USD']
 for i,l in enumerate(labels):
  x=.08+i*.17;ax.text(x,.5,l,ha='center',va='center',fontsize=9,bbox=dict(boxstyle='round',fc='#e8eef5'))
  if i<5:ax.annotate('',xy=(x+.11,.5),xytext=(x+.06,.5),arrowprops=dict(arrowstyle='->'))
 fig.savefig(figs/'workflow.png',dpi=170,bbox_inches='tight');plt.close(fig)

def usd_export(lookup):
 from pxr import Usd,UsdGeom,Gf,Vt
 out=DOC/'scene_export';out.mkdir(exist_ok=True);data=np.load(ART/'scene.npz');g=data['terrain'];low=data['low'];res=float(data['res']);mask=data['observed'];windows=json.loads((DOC/'WINDOWS.json').read_text());stage=Usd.Stage.CreateNew(str(out/'lunar_kinematic.usda'));UsdGeom.SetStageUpAxis(stage,UsdGeom.Tokens.z);UsdGeom.SetStageMetersPerUnit(stage,1.);stage.SetStartTimeCode(0);stage.SetEndTimeCode(5);stage.SetTimeCodesPerSecond(5)
 for w,(_,peer,motion) in zip(windows,[('W0','normal','white'),('W1','constant','scale'),('W2','step','slip_proxy')]):
  prefix='/'+w['id'];q=np.array(w['xyz_m']);xy=q[:,:,:2].reshape(-1,2);lo=np.maximum(np.floor((xy.min(0)-4-low)/res).astype(int),0);hi=np.minimum(np.ceil((xy.max(0)+4-low)/res).astype(int),np.array(g.shape)-1);ix=np.arange(lo[0],hi[0]+1);iy=np.arange(lo[1],hi[1]+1);pts=np.array([[low[0]+i*res,low[1]+j*res,g[i,j]] for i in ix for j in iy]);ny=len(iy);faces=[]
  for i in range(len(ix)-1):
   for j in range(ny-1):k=i*ny+j;faces.extend([k,k+ny,k+ny+1,k+1])
  mesh=UsdGeom.Mesh.Define(stage,prefix+'/Terrain');mesh.CreatePointsAttr(pts.tolist());mesh.CreateFaceVertexCountsAttr([4]*(len(faces)//4));mesh.CreateFaceVertexIndicesAttr(faces);mesh.CreateSubdivisionSchemeAttr('none');mesh.CreateDisplayColorPrimvar(UsdGeom.Tokens.vertex).Set([(0.48,.48,.48) if mask[i,j] else (.7,.25,.2) for i in ix for j in iy]);mesh.GetPrim().SetCustomDataByKey('mode','kinematic export; red filled nodes; no validated wheel contact')
  for k,a in enumerate(w['anchors_xyz_m']):
   sp=UsdGeom.Sphere.Define(stage,prefix+f'/Anchor{k}');sp.CreateRadiusAttr(.15);sp.AddTranslateOp().Set(Gf.Vec3d(*a));sp.CreateDisplayColorAttr([(1.,.7,0.)])
  for c in range(2):
   body=UsdGeom.Cube.Define(stage,prefix+f'/Car{c+1}/Body');body.CreateSizeAttr(.4);op=body.AddTranslateOp();ant=UsdGeom.Sphere.Define(stage,prefix+f'/Car{c+1}/Antenna');ant.CreateRadiusAttr(.1);aop=ant.AddTranslateOp();ant.CreateDisplayColorAttr([(0.,.5,1.) if c==0 else (1.,.4,0.)]);body.GetPrim().SetCustomDataByKey('identity','procedural visualization proxy, not real PR130 chassis; no dynamic body')
   line=UsdGeom.BasisCurves.Define(stage,prefix+f'/Reference{c}');line.CreateTypeAttr('linear');line.CreateCurveVertexCountsAttr([6]);line.CreatePointsAttr(q[:,c].tolist());line.CreateWidthsAttr([.04]);line.CreateDisplayColorAttr([(0.,.8,0.)])
   for t in range(6):op.Set(Gf.Vec3d(*(q[t,c]-[0,0,1.16])),t);aop.Set(Gf.Vec3d(*q[t,c]),t)
  peerline=UsdGeom.BasisCurves.Define(stage,prefix+'/Peer');peerline.CreateTypeAttr('linear');peerline.CreateCurveVertexCountsAttr([2]);pp=peerline.CreatePointsAttr();peerline.CreateWidthsAttr([.02]);peerline.CreateDisplayColorAttr([(.6,.1,.6)])
  for t in range(6):pp.Set(q[t].tolist(),t)
  for mi,method in enumerate(['M0','M1','M2','M3']):
   r=lookup[(w['id'],2026111701,peer,motion,'control',method)];est=np.dstack([np.array(r['q'][:24]).reshape(6,2,2),q[:,:,2]])
   for c in range(2):
    line=UsdGeom.BasisCurves.Define(stage,prefix+f'/{method}/Trajectory{c}');line.CreateTypeAttr('linear');line.CreateCurveVertexCountsAttr([6]);line.CreatePointsAttr(est[:,c].tolist());line.CreateWidthsAttr([.025]);line.CreateDisplayColorAttr([tuple(int(COLORS[mi][j:j+2],16)/255 for j in [1,3,5])]);line.GetPrim().SetCustomDataByKey('numerical_state',r['state'])
  stage.GetPrimAtPath(prefix).SetCustomDataByKey('condition',f'{peer}/{motion}; seed=2026111701; dt=.2s; reference time start={w["start_s"]}; slip edge [.4,.6] only for W2; step starts .6s W2')
 stage.GetRootLayer().Save();check=Usd.Stage.Open(str(out/'lunar_kinematic.usda'));assert UsdGeom.GetStageMetersPerUnit(check)==1 and UsdGeom.GetStageUpAxis(check)=='Z';assert check.GetPrimAtPath('/W2/Car2/Antenna').GetAttribute('xformOp:translate').GetTimeSamples()==[0.,1.,2.,3.,4.,5.]
 atomic(DOC/'SCENE_EXECUTION.json',dict(cpu_usd_export=True,usd_reopened=True,meters_per_unit=1,up_axis='Z',time_codes_per_second=5,mode='kinematic timeSamples, no physics execution',isaac_executed=False,rendered_in_isaac=False,dynamics_executed=False,reason='nvidia-smi driver communication failure; torch.cuda.is_available() False; existing Sim6.2/Lab3.0 retained unchanged',screenshots='figures are CPU matplotlib plots, not Isaac screenshots',versions={k:importlib.metadata.version(k) for k in ['numpy','scipy','matplotlib','usd-core']}))

def archive():
 root=ART/'evaluation';package=ART/'package';package.mkdir(exist_ok=True)
 for name in ['observations','references','results','attempts','endpoints']:
  shutil.copytree(root/name,package/name,dirs_exist_ok=True)
 for name in ['RUN_PLAN.json','PROGRESS.json','CLOCK.json']:shutil.copy2(root/name,package/name)
 for name in ['INPUT_MANIFEST.json','INPUT_SOURCES.json','WINDOWS.json','FREEZE.json','SEEDS.json','SCENE_STATS.json','OBSERVATION_CONTRACT.md','SOURCE_MAP.md','MODEL_AND_PARAMETERS.md','PROTOCOL.md']:shutil.copy2(DOC/name,package/name)

 # Full delivery material, excluding circular archive/checksum/readback receipt.
 for source in sorted(DOC.rglob('*')):
  if source.is_file() and source.name not in ['portable_results.tar.gz','SHA256SUMS','INDEPENDENT_CHECK.json','RESULTS_READY.json']:
   dest=package/'delivery'/source.relative_to(DOC);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
 shutil.copy2(ART/'scene.npz',package/'scene.npz');shutil.copy2(Path(__file__).parent/'checker.py',package/'checker.py')
 files={str(p.relative_to(package)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(package.rglob('*')) if p.is_file() and p.name!='MANIFEST.json'};atomic(package/'MANIFEST.json',files)
 with tarfile.open(DOC/'portable_results.tar.gz','w:gz') as tar:
  for p in sorted(package.rglob('*')):
   if p.is_file():tar.add(p,arcname=str(p.relative_to(package)),recursive=False)
 print('Archive ready', (DOC/'portable_results.tar.gz').stat().st_size)
if __name__=='__main__':
 runs,lookup,summary,pairs=summarize();figures(lookup,summary);usd_export(lookup);archive()

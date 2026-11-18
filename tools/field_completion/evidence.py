"""Observation-only coverage/geometry audit and final figures."""
import gzip,csv
from fcommon import *
from readback import csvsave

def evidence(batch,dest):
 batch=Path(batch);dest=Path(dest);cfg=read(DOC/'CONFIG.json');rows=[];timing=read(DOC/'ACCEPTANCE.json')['timing'];sources=read(SOURCE/'SOURCES.json')
 for case in cfg['cases']:
  o=read(batch/'measurements'/f'{case}.json');src=next(x for x in sources if x['case']==case)
  with gzip.open(SOURCE/case/'measurements.jsonl.gz','rt') as f:msgs=[json.loads(l) for l in f]
  for car in CARS:
   od=[x for x in msgs if x['topic']==f'/{car}/odom'];times=np.array([(x['receipt_ns']-src['bag_origin_ns'])*1e-9 for x in od]);loc=np.array([x['position_m'][:2] for x in od]);local=np.array(o['cars'][car]['local'])
   movement=np.linalg.norm(np.diff(local[:,:2],axis=0),axis=1)
   rows.append({'case':case,'car':car,'epochs':len(o['times']),'grid_start_s':o['times'][0],'grid_end_s':o['times'][-1],'raw_odom_start_s':times[0],'raw_odom_end_s':times[-1],'max_odom_gap_s':float(max(np.diff(times))),'grid_odom_path_m':float(sum(movement)),'raw_odom_path_m':float(np.linalg.norm(np.diff(loc,axis=0),axis=1).sum()),'grid_steps_over_002m':int(sum(movement>.02)),'wall_observed_factors':sum(len(r) for r in o['cars'][car]['observations']),'peer_available_epochs':sum(x['range_m'] is not None for x in o['peers']),'one_direction_only_epochs':sum(sum(y is not None for y in x['directions_m'])==1 for x in o['peers']),'missing_peer_epochs':sum(x['range_m'] is None for x in o['peers']),'raw_sha256':src['sha256'],'portable_sha256':digest(SOURCE/case/'measurements.jsonl.gz')})
 csvsave(dest/'INPUT_COVERAGE.csv',rows)
 csvsave(dest/'CLOCK_FRAME_AUDIT.csv',[{**{k:v for k,v in x.items() if not isinstance(v,list)},'frames':';'.join(x['frame_ids']),'child_frames':';'.join(x['child_frames']),'receipt_header_ms_p05':x['receipt_minus_header_ms_p05_p50_p95'][0],'receipt_header_ms_median':x['receipt_minus_header_ms_p05_p50_p95'][1],'receipt_header_ms_p95':x['receipt_minus_header_ms_p05_p50_p95'][2]} for x in timing])
 src=next(x for x in sources if x['case']=='013206');geometry=float(np.sqrt(2+(.17-.20)**2));static=[]
 with gzip.open(SOURCE/'013206/measurements.jsonl.gz','rt') as f:msgs=[json.loads(l) for l in f]
 for car,node in [('car1','node_0'),('car2','node_1')]:
  values=[v['range_m'] for x in msgs if x['topic']==f'/{car}/uwb/ranges' for v in x['ranges'] if v['anchor_id']==node and v['range_m'] is not None and v['range_m']>0]
  static.append({'case':'013206','receiver':car,'n':len(values),'manual_geometry_m':geometry,'raw_median_m':float(np.median(values)),'median_minus_geometry_m':float(np.median(values)-geometry),'iqr_m':float(np.diff(np.percentile(values,[25,75]))[0]),'calibration_reuse':'Car1 walls calibrated using this bag; not held-out accuracy'})
 csvsave(dest/'STATIC_REFERENCE.csv',static)

 def loadcsv(name):
  with (dest/(name+'.csv')).open() as f:return list(csv.DictReader(f))
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 traj=loadcsv('TRAJECTORIES');peer=loadcsv('PEER_RESIDUALS');colors={'F0':'gray','F1':'tab:blue','F2':'tab:orange','F3':'tab:green'}
 fig,axes=plt.subplots(4,3,figsize=(16,15),constrained_layout=True)
 for row,case in enumerate(cfg['fit_cases']):
  for method in cfg['methods']:
   for car,style in [('car1','-'),('car2','--')]:
    tt=[x for x in traj if x['case']==case and x['method']==method and x['car']==car]
    axes[row,0].plot([float(x['antenna_x_m']) for x in tt],[float(x['antenna_y_m']) for x in tt],style,color=colors[method],label=method+' '+car,lw=1)
   pp=[x for x in peer if x['case']==case and x['method']==method]
   axes[row,1].plot([float(x['t_s']) for x in pp],[float(x['after_bias_residual_m']) for x in pp],color=colors[method],label=method,lw=.8)
   if method in ['F2','F3']:axes[row,2].plot([float(x['t_s']) for x in pp],[float(x['bias_m']) for x in pp],color=colors[method],label=method)
  axes[row,0].set(title=case+' estimated antenna trajectories',xlabel='room x (m)',ylabel='room y (m)');axes[row,0].axis('equal')
  axes[row,1].set(title='Peer residual after modeled bias',xlabel='receipt time (s)',ylabel='m')
  axes[row,2].set(title='Fitted bias (no truth)',xlabel='receipt time (s)',ylabel='m')
  for ax in axes[row]:ax.grid(alpha=.3);ax.legend(fontsize=6)
 fig.suptitle('Full field batch: all four cases; no continuous ground truth; inspect numerical status before interpretation');fig.savefig(dest/'full_batch.png',dpi=150);plt.close(fig)
if __name__=='__main__':evidence(*sys.argv[1:])

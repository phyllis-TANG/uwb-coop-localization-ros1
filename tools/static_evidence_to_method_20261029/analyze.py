#!/usr/bin/env python3
"""Ten exposed static bags only. Descriptive ranges; no locator, ROS or network."""
import argparse,csv,gzip,hashlib,json,math,sys,time,subprocess
from pathlib import Path
from collections import Counter,defaultdict
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/field_20261024_25'))
import bag_decoder as bd
BASE='83f64f5af0dda40228ab115a680bb65ef2379e9a'
DOC='docs/research/static_evidence_to_method_20261029/'
FIELD='docs/field_tests/20261024_25/'
TRANSFER='docs/field_tests/20261018/single_car_transfer_20261021/results/range_transfer.csv'
SESSION=FIELD+'SESSION_LOG_ARCHIVE.md'
IDS=['B048','B050','B067','B069','B070','B068']
SHORT=['P1','P4','clear_A','human_B','human_B_repeat','clear_C','T01','T02','T03','T04']
WALLS=['node_10','node_2','node_3','node_8']
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def dump(p,x):
 with p.open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def csvout(p,rows):
 keys=list(dict.fromkeys(k for r in rows for k in r))
 with p.open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=keys,lineterminator='\n');w.writeheader();w.writerows(rows)
def stats(v):
 a=np.asarray(v,dtype=float);a=a[np.isfinite(a)&(a>0)]
 if not len(a):return None,None
 m=float(np.median(a));return m,float(np.median(abs(a-m)))
def windows(s,d):
 out=[('whole',0.,d,True)]
 if s.startswith(('clear_','human_')):out += [('early',0.,10.,False),('middle',10.,20.,False),('late',20.,d,True)]
 elif s=='T02':out += [(n,a,b,False) for n,a,b in [('pre',5.,35.),('wall_action',45.,75.),('recovery1',85.,155.),('peer_action',165.,195.),('recovery2',205.,d-5.)]]
 elif s.startswith('T'):out += [('trim5',5.,d-5.,False)]
 return out

def plan(inputdir):
 catalog=json.loads((ROOT/'datasets/field_raw/catalog.json').read_text());manifest=json.loads((ROOT/FIELD/'manifest.json').read_text())
 out=[]
 for rid in IDS:
  r=next(x for x in catalog if x['record_id']==rid)
  out.append(dict(file=r['filename'],sha256=r['sha256'],path=str(ROOT/'datasets/field_raw'/r['archive_path']),notes=['datasets/field_raw/'+p for p in r['linked_support_files']],index_source='datasets/field_raw/catalog.json#'+rid))
 for s in ['T01','T02','T03','T04']:
  r=next(x for x in manifest['historical_and_fault_bags'] if Path(x['relative_path']).name.startswith(s+'_'))
  out.append(dict(file=Path(r['relative_path']).name,sha256=r['sha256'],path=str(inputdir/Path(r['relative_path']).name),notes=[str(p) for p in sorted(inputdir.glob(s+'*.notes.txt'))],index_source=FIELD+'manifest.json#'+r['relative_path']))
 for s,r in zip(SHORT,out):r['id']=s
 return out

def run(inputdir,out):
 out.mkdir(exist_ok=False);started=time.time();inputs=plan(inputdir);sources={}
 def source(p):
  path=Path(p);path=path if path.is_absolute() else ROOT/path
  sources[str(p)]=sha(path);return path
 for p in ['datasets/field_raw/catalog.json',FIELD+'EXPERIMENTS.md',FIELD+'geometry.json',FIELD+'manifest.json',SESSION,TRANSFER,'docs/field_tests/20261017/session_config.json','docs/field_tests/20261018/single_car_transfer_20261021/REPORT.md',DOC+'PREREGISTRATION.md','tools/field_20261024_25/bag_decoder.py']:
  source(p).read_bytes()
 for n in ['TRUST_BASIS.md','DATA_USE_MATRIX.csv','NEXT_GATE.md','FIELD_MINIMUM_20261030.md','HANDOFF.md']:source('docs/research/raw_anchor_trust_check_20261029/'+n).read_bytes()
 for p in [FIELD+'cooperative_dcs_probe_20261028/REPORT.md',FIELD+'cooperative_influence_probe_20261028/REPORT.md','docs/research/cooperative_followup_20261029/a_evidence/A_FACTS.md']:source(p).read_bytes()
 with (ROOT/TRANSFER).open() as f:old=[r for r in csv.DictReader(f) if r['dataset'] in [x['file'] for x in inputs[:2]]]
 assert len(old)==8
 oldmap={(r['dataset'],r['node']):r for r in old};allrows=[];evidence=[];checks=[];decoded=[]
 for inp in inputs:
  s=inp['id'];path=Path(inp['path']);assert sha(path)==inp['sha256'],('SHA',path)
  for p in inp['notes']:source(p).read_bytes()
  con,raw=bd.load_bag(path);start=min(t for _,t,_ in raw);end=max(t for _,t,_ in raw);duration=(end-start)/1e9
  dec={i:bd.Decoder(c['type'],c['definition']) for i,c in con.items() if c['topic'] in ['/car1/uwb/ranges','/car2/uwb/ranges']};groups=defaultdict(list)
  with gzip.open(out/(s+'_ranges.jsonl.gz'),'wt') as cache:
   for record,(i,t,b) in enumerate(raw):
    if i not in dec:continue
    m=dec[i].decode(b,con[i]['type']);car=con[i]['topic'].split('/')[1];n=dict(record_id=record,connection_id=i,car=car,receive_ns=t,header_ns=bd.stamp(m),ranges=[{'anchor':z['anchor_id'],'range':float(z['range']) if math.isfinite(z['range']) else None} for z in m['ranges']]);groups[car].append(n);cache.write(json.dumps(n,allow_nan=False)+'\n')
  inp.update(start_receive_ns=start,end_receive_ns=end,duration_s=duration,ranges_decoded=sum(map(len,groups.values())),all_bag_records=len(raw),topic_counts=dict(Counter(con[i]['topic'] for i,t,b in raw)),decoded_cache_sha256=sha(out/(s+'_ranges.jsonl.gz')))
  for win,a,b,last in windows(s,duration):
   for car in ['car1','car2']:
    frames=[m for m in groups[car] if a<=(m['receive_ns']-start)/1e9 and ((m['receive_ns']-start)/1e9<b or last and m['receive_ns']==end)]
    for link in WALLS+(['node_0'] if car=='car1' else ['node_1']):
     valid=[];missing=invalid=duplicate=0
     for m in frames:
      vs=[z['range'] for z in m['ranges'] if z['anchor']==link]
      if not vs:missing+=1
      elif len(vs)>1:duplicate+=1
      elif vs[0] is None or vs[0]<=0:invalid+=1
      else:valid.append(vs[0])
     med,mad=stats(valid);ref=None;refkind='none_no_per_car_XYZ';corr=None;delta=None
     if s in ['P1','P4'] and car=='car2' and link in WALLS:
      oldr=oldmap[(inp['file'],link)];ref=float(oldr['geometry_m']);refkind='manual_antenna_XYZ_slant';corr=float(oldr['P1_offset_m']);delta=med-ref-corr if med is not None else None
     elif link not in WALLS:
      ref=2.93 if s.startswith(('clear_','human_')) else {'T01':2.08,'T02':2.08,'T03':2.11,'T04':2.12}.get(s)
      if ref is not None:refkind='manual_direct_tape_inherited_T01' if s=='T02' else 'manual_direct_tape'
     row=dict(bag=s,file=inp['file'],bag_sha256=inp['sha256'],window=win,start_s=a,end_s=b,end_inclusive=last,clock='bag_receive_relative_first_record',car=car,link=link,origin='supplement_this_run',metric_kind='raw_range_distribution_and_reference_difference',frames=len(frames),valid=len(valid),missing_entry=missing,invalid_entry=invalid,duplicate_target_frames=duplicate,coverage=len(valid)/len(frames) if frames else None,status='topic_absent' if not groups[car] else 'window_empty' if not frames else 'link_missing' if not valid else 'observed',median_m=med,MAD_m=mad,manual_reference_m=ref,reference_kind=refkind,median_minus_reference_m=med-ref if med is not None and ref is not None else None,P1_offset_m=corr,corrected_minus_geometry_m=delta,source_path=str(path),source_version=inp['sha256'],result_path='COMPACT_RESULTS.csv')
     allrows.append(row)
  w=[r for r in allrows if r['bag']==s and r['window']=='whole']
  decoded.append(dict(bag=s,ranges_decoded=inp['ranges_decoded'],status='COMPLETE'))
  evidence.append(dict(bag=s,file=inp['file'],sha256=inp['sha256'],measurement_definition='人工天线XYZ (2,2,0.20)m；P1已拟合，不作独立验证' if s=='P1' else '最终人工天线XYZ (3,3,0.20)m；保留旧(3.5,4)更正' if s=='P4' else '双向peer只比较用户直接卷尺2.93m；各车XY未知' if s.startswith(('clear_','human_')) else '直接卷尺'+str({'T01':2.08,'T02':2.08,'T03':2.11,'T04':2.12}[s])+'m；名义A/B不是逐包实际XYZ',time_windows=json.dumps(windows(s,duration)),time_basis='bag_receive; first record zero; header recorded, not used for selection',prior_analysis=TRANSFER if s in ['P1','P4'] else 'datasets/field_raw/catalog.json; user-confirmed tape; detailed MAD table not located' if s.startswith(('clear_','human_')) else SESSION,prior_version=sources[TRANSFER] if s in ['P1','P4'] else sources['datasets/field_raw/catalog.json'] if s.startswith(('clear_','human_')) else sources[SESSION],this_run='reuse existing numeric rows separately; supplement ranges coverage/MAD/contrasts only',input_status='SHA_VERIFIED_AND_RANGES_DECODED',supports='测距相对人工几何差及同日P1修正迁移' if s in ['P1','P4'] else '分链覆盖/MAD/中位数变化、双向peer人工距离差；保留弱效/反例',limitations='P1自拟合；P4迁移仍混合位置/姿态/人工几何误差；仅Car2墙话题' if s in ['P1','P4'] else '人员进入时刻未知；无各车XY；人体操作不是真故障标签' if s.startswith(('clear_','human_')) else '人工时段近似；朝向/回位/环境混杂；名义XYZ不作精密真值',sources=' | '.join([inp['index_source']]+inp['notes']),results='COMPACT_RESULTS.csv; CONTRASTS.csv',raw_read_this_run=True))
  print('DONE',s,'ranges',inp['ranges_decoded'],flush=True)
 # Original numeric rows kept separate from newly computed rows.
 for r in old:
  s=next(x['id'] for x in inputs if x['file']==r['dataset']);now=next(x for x in allrows if x['bag']==s and x['car']=='car2' and x['link']==r['node'] and x['window']=='whole')
  assert abs(now['median_m']-float(r['median_m']))<1e-12
  assert now['frames']==int(r['uwb_frames_in_window']) and now['valid']==int(r['valid_samples'])
  checks.append(dict(check='A_same_whole_window_median_and_counts',bag=s,link=r['node'],pass_=True))
  allrows.append(dict(bag=s,file=r['dataset'],bag_sha256=r['bag_sha256'],window='whole',clock='original_whole_bag_no_time_filter',car='car2',link=r['node'],origin='reused_numeric',metric_kind='manual_geometry_difference_original_transfer',frames=int(r['uwb_frames_in_window']),valid=int(r['valid_samples']),coverage=int(r['valid_samples'])/int(r['uwb_frames_in_window']),median_m=float(r['median_m']),manual_reference_m=float(r['geometry_m']),reference_kind='manual_antenna_XYZ_slant',median_minus_reference_m=float(r['raw_minus_geometry_m']),P1_offset_m=float(r['P1_offset_m']),corrected_minus_geometry_m=float(r['corrected_minus_geometry_m']),source_path=TRANSFER,source_version=sources[TRANSFER],result_path='COMPACT_RESULTS.csv'))
 # Rounded original report values, comparison tolerance fixed in preregistration.
 legacy=[('T01','whole','car1','node_0',2.089),('T01','whole','car2','node_1',2.133)]
 for window,vals in zip(['pre','wall_action','recovery1','peer_action','recovery2'],[(3.542,2.089,2.130),(3.577,2.091,2.133),(3.549,2.093,2.135),(3.542,2.091,2.135),(3.540,2.091,2.133)]):
  for (car,link),value in zip([('car2','node_10'),('car1','node_0'),('car2','node_1')],vals):legacy.append(('T02',window,car,link,value))
 for s,vals in [('T03',(2.105,2.148)),('T04',(2.018,2.064))]:
  for car,link,value in zip(['car1','car2'],['node_0','node_1'],vals):legacy.append((s,'trim5',car,link,value))
 for s,w,c,l,v in legacy:
  now=next(r for r in allrows if r['bag']==s and r['window']==w and r['car']==c and r['link']==l and r['origin']=='supplement_this_run');diff=now['median_m']-v
  checks.append(dict(check='C_rounded_report_median',bag=s,window=w,car=c,link=l,difference_m=diff,tolerance_m=.00051,pass_=abs(diff)<=.00051))
  allrows.append(dict(bag=s,file=now['file'],bag_sha256=now['bag_sha256'],window=w,start_s=now['start_s'],end_s=now['end_s'],clock='bag_receive_relative_first_record',car=c,link=l,origin='reused_numeric',metric_kind='raw_range_median_original_report',median_m=v,source_path=SESSION,source_version=sources[SESSION],result_path='COMPACT_RESULTS.csv'))
 contrasts=[];fresh=[r for r in allrows if r['origin']=='supplement_this_run']
 for r in fresh:
  if r['bag'] in ['P1','P4','clear_A','T01']:continue
  base_s,base_w=('T02','pre') if r['bag']=='T02' else ('T01','trim5') if r['bag'] in ['T03','T04'] else ('clear_A','whole')
  if r['bag']=='T02' and r['window']=='whole':continue
  if r['bag'] in ['T03','T04'] and r['window']!='trim5':continue
  b=next(x for x in fresh if (x['bag'],x['window'],x['car'],x['link'])==(base_s,base_w,r['car'],r['link']))
  contrasts.append(dict(bag=r['bag'],window=r['window'],car=r['car'],link=r['link'],baseline_bag=base_s,baseline_window=base_w,kind='same_nominal_setup_range_change_not_position_error',delta_m=r['median_m']-b['median_m'] if r['median_m'] is not None and b['median_m'] is not None else None,delta_MAD_m=r['MAD_m']-b['MAD_m'] if r['MAD_m'] is not None and b['MAD_m'] is not None else None,reference_adjusted_delta_m=r['median_minus_reference_m']-b['median_minus_reference_m'] if r['median_minus_reference_m'] is not None and b['median_minus_reference_m'] is not None else None,origin='derived_this_run',source_path='COMPACT_RESULTS.csv',source_version='same_run',result_path='CONTRASTS.csv'))
 csvout(out/'COMPACT_RESULTS.csv',allrows);csvout(out/'OLD_STATIC_EVIDENCE.csv',evidence);csvout(out/'CONTRASTS.csv',contrasts);dump(out/'CHECKS.json',checks)
 dump(out/'RUN_MANIFEST.json',dict(task='STATIC-TO-METHOD-02',baseline=BASE,execution_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),start_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(started)),elapsed_s=time.time()-started,inputs=inputs,scope='10 exposed static bags; range topics only',rows=len(allrows),reused_numeric_rows=sum(r['origin']=='reused_numeric' for r in allrows),supplemented_rows=len(fresh),decoded=decoded,source_sha256=sources,code_sha256={p.name:sha(p) for p in Path(__file__).parent.glob('*.py')},outputs={p.name:sha(p) for p in out.iterdir() if p.is_file()},all_reuse_checks_pass=all(x['pass_'] for x in checks),new_FGO_runs=0,new_simulations=0,raw_frame_QC_repeated=False,holdout_bags_opened=[],note='Whole-bag and segment rows overlap, not independent experiments; no online classification or certified health.'))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.input_dir,a.output)

"""Post-freeze read-only delivery summaries. No searches or new observations."""
import argparse,csv,statistics
from collections import Counter,defaultdict
from common import *
from runtime import plans

def csvwrite(p,rows):
 keys=list(dict.fromkeys(k for row in rows for k in row));p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
def analyze(results,out):
 inp=read(DOC/'INPUTS.json.gz');out.mkdir(parents=True,exist_ok=True);rows=[];records={}
 for stage in ('deterministic','random'):
  directory=results/stage;walls={}
  if (directory/'WALL_COSTS.jsonl').exists():walls={x['id']:x['wall_seconds'] for x in map(json.loads,(directory/'WALL_COSTS.jsonl').read_text().splitlines())}
  for job in plans(inp,stage):
   c=job['case'];m=job['method'];row=dict(stage=stage,case=c['id'],group=c['group'],condition=c['condition'],seed=c.get('seed'),method=m,status='UNEXECUTED')
   rp=directory/(job['id']+'.receipt.json')
   if rp.exists():
    receipt=read(rp);row.update(status=receipt['status'],error=receipt['error'],wall_seconds=walls.get(job['id'],receipt['total_wall_seconds']),peak_rss_kib=receipt.get('peak_rss_kib'))
    row.update({k+'_seconds':v for k,v in receipt['costs'].items()})
    if receipt['status']=='COMPLETED':
     path=directory/(job['id']+'.result.json.gz');assert sha(path)==receipt['record_sha256'];record=read(path);records[stage,c['id'],m]={'projections':record['projections']};r=record['result'];e=record['evaluation']
     row.update(termination=r['termination'],processed=r['processed'],pending=r['counts'].get('PENDING',0),inside=r['counts'].get('INSIDE',0),undecided=r['counts'].get('UNDECIDED',0),empty=r['empty_proved'],b_certificate=record['certificate_b']['status'],a_certificate=record['certificate_a']['status'],noise_event=e['noise_event']['holds'] if e['noise_event'] else 'NOT_APPLICABLE',exact_joint_position=e['exact_joint_position_feasibility'],finite_joint_hit=e['finite_joint_outer_contains'])
     for car in ('p','s'):
      z=record['projections'][car]
      for k in ('area_upper_m2','feasible_area_lower_m2','radius_upper_m','boundary_contact'):row[car+'_'+k]=float(F(z[k])) if z[k] is not None and not isinstance(z[k],bool) else z[k]
      row[car+'_span_x_m']=float(F(z['span_m'][0])) if z['span_m'] else None;row[car+'_span_y_m']=float(F(z['span_m'][1])) if z['span_m'] else None
      row[car+'_projection_hit']=e['finite_car_projection_contains'][car]
      for branch,zv in z['branch_evidence'].items():
       for k,v in zv.items():row[car+'_'+branch+'_'+k]=v
   rows.append(row)
 csvwrite(out/'RUNS.csv',rows)
 summaries=[]
 for stage in ('deterministic','random'):
  for m in ('J5','P4','N4'):
   rs=[r for r in rows if r['stage']==stage and r['method']==m]
   if not rs:continue
   done=[r for r in rs if r['status']=='COMPLETED'];executed=[r for r in rs if r['status']!='UNEXECUTED'];summary=dict(stage=stage,method=m,planned=len(rs),executed=len(executed),completed=len(done),unexecuted=len(rs)-len(executed),failures=len(executed)-len(done),budget_stops=sum(r.get('termination') in ('TIME_BUDGET','BOX_BUDGET','MEMORY_BUDGET') for r in done),empty=sum(r.get('empty',False) for r in done),processed=sum(r.get('processed',0) for r in done))
   costs=[r['wall_seconds'] for r in executed];summary.update(total_wall_seconds=sum(costs),median_wall_seconds=statistics.median(costs) if costs else None)
   summaries.append(summary)
 csvwrite(out/'SUMMARY.csv',summaries);pairs=[];idx={(r['stage'],r['case'],r['method']):r for r in rows}
 for stage in ('deterministic','random'):
  for c in inp[stage]:
   choices=[('J5','P4')] if stage=='deterministic' else []
   if c['group']=='main':choices.append(('N4','P4'))
   for old,new in choices:
    a=idx[stage,c['id'],old];b=idx[stage,c['id'],new];row=dict(stage=stage,case=c['id'],group=c['group'],condition=c['condition'],old=old,new=new,old_status=a['status'],new_status=b['status'])
    if 'wall_seconds' in a and 'wall_seconds' in b:row.update(old_wall_seconds=a['wall_seconds'],new_wall_seconds=b['wall_seconds'],old_over_new_wall=a['wall_seconds']/b['wall_seconds'],new_minus_old_wall=b['wall_seconds']-a['wall_seconds'])
    if a['status']==b['status']=='COMPLETED':
     for car in ('p','s'):
      for k in ('area_upper_m2','radius_upper_m','span_x_m','span_y_m'):
       aa=a.get(car+'_'+k);bb=b.get(car+'_'+k);row[car+'_new_minus_old_'+k]=None if aa is None or bb is None else bb-aa
      aa=records[stage,c['id'],old]['projections'][car]['rectangles'];bb=records[stage,c['id'],new]['projections'][car]['rectangles'];row[car+'_identical_rectangle_representation']=aa==bb
    pairs.append(row)
 csvwrite(out/'PAIRED.csv',pairs);write(out/'ANALYSIS.json',dict(status='PASS',rows=len(rows),completed=sum(r['status']=='COMPLETED' for r in rows),search_calls=0,optimizer_calls=0,notes='Area differences are reliable upper-bound differences, not exact feasible-set area differences.'))
 print(json.dumps(summaries))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();analyze(a.results,a.out)

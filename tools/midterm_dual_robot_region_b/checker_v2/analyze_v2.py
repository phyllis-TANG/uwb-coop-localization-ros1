"""Descriptive v2 costs, complete denominators and separated event/region outcomes."""
import argparse,csv,json,statistics,sys,math
from collections import Counter,defaultdict
from fractions import Fraction
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import read,write,DOC
from runtime import plans
D=DOC/'checker_v2'
def csvwrite(path,rows):
 if not rows:return
 with path.open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def corr(x,y):
 if len(x)<2:return None
 xm=statistics.mean(x);ym=statistics.mean(y);num=sum((a-xm)*(b-ym) for a,b in zip(x,y));den=math.sqrt(sum((a-xm)**2 for a in x)*sum((b-ym)**2 for b in y));return num/den if den else None
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);args=ap.parse_args();inputs=read(DOC/'INPUTS.json.gz');gate=read(D/'GATE.json');rows=[];regions=[];costs=[];denoms={};oldwall={r['id']:r['wall_seconds'] for r in map(json.loads,(args.root/'old_delivery/raw/WALL_COSTS.jsonl').read_text().splitlines())}
 for stage in ['deterministic','random']:
  out=args.root/stage;plan=plans(inputs,stage);ledger=out/'WALL_COSTS.jsonl';wall={r['id']:r['wall_seconds'] for r in map(json.loads,ledger.read_text().splitlines())} if ledger.exists() else {};counts=Counter()
  for item in plan:
   unit=item['id'];rp=out/(unit+'.receipt.json');receipt=read(rp) if rp.exists() else None;status=receipt['status'] if receipt else 'INTERRUPTED' if (out/(unit+'.attempt.json')).exists() else 'NOT_RUN';counts[status]+=1;r=read(out/(unit+'.result.json.gz')) if receipt and receipt.get('record_sha256') else None;ev=r.get('evaluation',{}) if r else {};event=ev.get('noise_event');reason=receipt.get('error') if receipt else ';'.join(gate['reasons']) if stage=='random' and gate['status']!='PASS' else 'NOT_STARTED'
   rows.append(dict(stage=stage,id=unit,method=item['method'],case=item['case']['id'],group=item['case'].get('group'),status=status,reason=reason,noise_event_holds=None if event is None else event['holds'],noise_quadratic=None if event is None else event['quadratic'],truth_in_domain=ev.get('truth_in_declared_domain'),exact_feasibility=ev.get('exact_joint_position_feasibility'),joint_outer_hit=ev.get('finite_joint_outer_contains'),p_outer_hit=ev.get('finite_car_projection_contains',{}).get('p'),s_outer_hit=ev.get('finite_car_projection_contains',{}).get('s'),termination=r['result']['termination'] if r else None))
   if not r or status!='COMPLETED':continue
   cost=receipt['costs'];costs.append(dict(stage=stage,id=unit,method=item['method'],group=item['case'].get('group'),nodes=len(r['result']['nodes']),retained=sum(n['status'] not in ['SPLIT','OUTSIDE'] for n in r['result']['nodes']),full_wall_seconds=wall[unit],old_full_wall_seconds=oldwall.get(unit),**{k:cost[k] for k in ['input_parse','source_load','search','certificate_b','certificate_conversion','projection','certificate_a','evaluation','compressed_io']},other_inclusive_seconds=wall[unit]-sum(cost.values())))
   for car in ['p','s']:
    p=r['projections'][car];regions.append(dict(stage=stage,id=unit,method=item['method'],car=car,outer_rectangles=len(p['rectangles']),inside_rectangles=len(p['inside_rectangles']),unresolved_rectangles=len(p['unresolved_rectangles']),area_upper_m2=p['area_upper_m2'],feasible_area_lower_m2=p['feasible_area_lower_m2'],radius_upper_m=p['radius_upper_m'],span_x_m=None if p['span_m'] is None else p['span_m'][0],span_y_m=None if p['span_m'] is None else p['span_m'][1],boundary_contact=p['boundary_contact']))
  denoms[stage]=dict(planned=len(plan),completed=counts['COMPLETED'],failed=sum(v for k,v in counts.items() if k not in ['COMPLETED','NOT_RUN','INTERRUPTED']),interrupted=counts['INTERRUPTED'],unexecuted=counts['NOT_RUN'],statuses=dict(counts))
 csvwrite(D/'RUN_OUTCOMES.csv',rows);csvwrite(D/'REGIONS.csv',regions);csvwrite(D/'COSTS.csv',costs);write(D/'DENOMINATORS.json',denoms)
 summary={}
 for method in ['J5','P4','N4']:
  rs=[r for r in costs if r['stage']=='deterministic' and r['method']==method and r['group']=='main'];components={k:sum(r[k] for r in rs) for k in ['search','certificate_b','certificate_conversion','projection','certificate_a','compressed_io','other_inclusive_seconds']};summary[method]=dict(main_completed=len(rs),median_full_wall_seconds=statistics.median(r['full_wall_seconds'] for r in rs) if rs else None,old_median_full_wall_seconds=statistics.median(r['old_full_wall_seconds'] for r in rs) if rs else None,component_sums_seconds=components,node_wall_pearson=corr([r['nodes'] for r in rs],[r['full_wall_seconds'] for r in rs]),retained_wall_pearson=corr([r['retained'] for r in rs],[r['full_wall_seconds'] for r in rs]))
 write(D/'COST_SUMMARY.json',summary)
 separation={}
 for stage in ['deterministic','random']:
  for method in ['J5','P4','N4']:
   allrows=[r for r in rows if r['stage']==stage and r['method']==method];rs=[r for r in allrows if r['status']=='COMPLETED'];separation[stage+'/'+method]=dict(planned=len(allrows),completed=len(rs),noise_event_true=sum(r['noise_event_holds'] is True for r in rs),noise_event_false=sum(r['noise_event_holds'] is False for r in rs),noise_event_unavailable=sum(r['noise_event_holds'] is None for r in rs),exact_feasibility=dict(Counter(r['exact_feasibility'] for r in rs)),joint_outer_hits=sum(r['joint_outer_hit'] is True for r in rs),p_outer_hits=sum(r['p_outer_hit'] is True for r in rs),s_outer_hits=sum(r['s_outer_hit'] is True for r in rs),truth_in_domain=sum(r['truth_in_domain'] is True for r in rs),qualified_event_trials=sum(r['truth_in_domain'] is True and r['noise_event_holds'] is True for r in rs),qualified_event_outer_misses=sum(r['truth_in_domain'] is True and r['noise_event_holds'] is True and r['joint_outer_hit'] is False for r in rs))
 write(D/'EVENT_FEASIBILITY_HIT_COUNTS.json',separation);print(json.dumps(dict(denominators=denoms,costs=summary),indent=2))
if __name__=='__main__':main()

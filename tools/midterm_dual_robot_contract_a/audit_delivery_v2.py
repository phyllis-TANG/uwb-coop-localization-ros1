"""Read-only linkage of original costs/nodes to portable proofs, plus evaluation checks.

Evaluation is separate from checker_v2 and never drives pruning or domain selection.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
from core import F, bounds, digest, iv, need, q, recovery
from check import read_json

METHOD={'5d':'J5','4d':'P4','no_peer':'N4'}

def contains(nodes,point):
    p=list(map(F,point))
    return any(all(a<=v<=b for v,(a,b) in zip(p,map(iv,n['box'])))
               for n in nodes if n['kind'] in ('INSIDE','UNDECIDED','PENDING'))

def audit(evidence,evaluation):
    root=Path(evidence);lock=read_json(root/'EVIDENCE_LOCK.json')
    xs={x['case_id']:x for x in read_json(root/'inputs.json')}
    truth={x['case_id']:x for x in read_json(evaluation)['deterministic']}
    rows=[]
    for rec in lock['formal_records']:
        case=rec['case_id'];mode=rec['mode'];method=METHOD[mode];unit=case+'_'+method;x=xs[case]
        cert=read_json(root/rec['certificate_file'])
        packed=(root/'raw'/(unit+'.result.json.gz')).read_bytes()
        raw=json.loads(gzip.decompress(packed));receipt=read_json(root/'raw'/(unit+'.receipt.json'));worker=read_json(root/'raw'/(unit+'.worker.json'));attempt=read_json(root/'raw'/(unit+'.attempt.json'))
        need(hashlib.sha256(packed).hexdigest()==receipt['record_sha256'],'RECEIPT_PAYLOAD_HASH')
        identity={'schema':'DUAL-B-RUN-V1','id':unit,'case_sha256':digest(raw['case']), 'method':method,
                  'settings_sha256':digest(raw['settings']),'freeze_sha':lock['run_frozen_sha'],'a_sha':lock['a_frozen_sha']}
        need(all(r['identity']==identity for r in (raw,receipt,worker,attempt)),'RAW_IDENTITY_MISMATCH')
        need(raw['case']['a_input']==x,'RAW_FROZEN_INPUT_MISMATCH')
        need(receipt['status']==raw['status']==worker['status']=='COMPLETED','RAW_STATUS_MISMATCH')
        need(receipt['costs']==worker['costs'],'RAW_COST_MISMATCH')
        result=raw['result']; expected_nodes=[]
        for n in result['nodes']:
            new={'id':n['path'],'box':n['box'],'kind':n['status']}
            if n['status']=='SPLIT':new.update(axis=n['axis'],cut=n['mid'],children=[n['path']+'0',n['path']+'1'])
            expected_nodes.append(new)
        need(expected_nodes==cert['nodes'] and result['queue']==cert['queue'],'PORTABLE_TREE_DIFFERS_FROM_RAW')
        need(cert['cost']['processed_nodes']==result['processed'],'RAW_PROCESSED_MISMATCH')
        need(cert['cost']['distance_evaluations']==result['distance_evaluations'],'RAW_DISTANCE_COST_MISMATCH')
        need(q(cert['cost']['search_seconds'])==F(str(receipt['costs']['search'])),'RAW_SEARCH_COST_MISMATCH')
        need(q(cert['cost']['peak_rss_bytes'])==receipt['peak_rss_kib']*1024,'RAW_RSS_MISMATCH')
        # Reproduce this archival float conversion only, not certification arithmetic.
        need(q(cert['cost']['certificate_write_seconds'])==F(str(sum(receipt['costs'][k] for k in ('certificate_b','certificate_a','compressed_io')))),'RAW_CERTIFICATE_COST_MISMATCH')
        need(all(v>=0 for v in receipt['costs'].values()) and receipt['total_wall_seconds']>=0,'NEGATIVE_ORIGINAL_COST')
        need(result['processed']<=raw['settings']['max_boxes'],'B_DECLARED_NODE_BUDGET')
        # B stores deduplicated rectangles and a finer sqrt radius. Check its geometry
        # directly rather than expecting its rounding/area representation to match A.
        for car in ('p','s'):
            bp=raw['projections'][car];ap=cert['projections'][car]
            expected=set(tuple(map(iv,r['box'])) for r in ap['rectangles'])
            actual=set(tuple(map(iv,r)) for r in bp['rectangles'])
            need(actual==expected,'RAW_PROJECTION_SET_MISMATCH')
            if not actual:
                need(bp['center'] is None and bp['radius_upper_m'] is None and F(bp['area_upper_m2'])==0,'RAW_EMPTY_GEOMETRY')
            else:
                need(list(map(F,bp['center']))==list(map(F,ap['center'])),'RAW_PROJECTION_CENTER')
                rad=F(bp['radius_upper_m']);need(rad>=0 and rad*rad>=F(ap['radius_squared']),'RAW_RADIUS_NOT_ENCLOSING')
                lows=[min(r[j][0] for r in actual) for j in range(2)]
                highs=[max(r[j][1] for r in actual) for j in range(2)]
                area=min((highs[0]-lows[0])*(highs[1]-lows[1]),sum((r[0][1]-r[0][0])*(r[1][1]-r[1][0]) for r in actual))
                need(F(bp['area_upper_m2'])==area,'RAW_AREA_UPPER_MISMATCH')
        z=truth[case]['truth_position']; b=truth[case]['truth_bias']; point=z+[b] if mode=='5d' else z
        exact_bound=bounds(x,[[v,v] for v in point],mode)
        tau=24 if mode=='no_peer' else 26
        empty=case=='empty_in_domain'
        if empty:
            need(cert['status']=='EMPTY_IN_DECLARED_DOMAIN','EXPECTED_EMPTY_NOT_CERTIFIED')
            eval_status='NOT_APPLICABLE_INTENTIONALLY_INCONSISTENT'
        else:
            need(exact_bound[1]<=tau and contains(cert['nodes'],point),'TRUE_POINT_OR_BOUNDARY_LOST')
            eval_status='POINT_FEASIBILITY_AND_OUTER_MEMBERSHIP_PROVED'
        mirror=None
        if case.startswith('collinear_'):
            mz=[z[0],str(-F(z[1])),z[2],str(-F(z[3]))];mp=mz+[b] if mode=='5d' else mz
            need(bounds(x,[[v,v] for v in mp],mode)[1]<=tau and contains(cert['nodes'],mp),'COMMON_MIRROR_BRANCH_LOST')
            mirror='COMMON_MIRROR_FEASIBLE_AND_RETAINED'
        if case=='forced_budget':need(cert['status']=='BUDGET_OUTER' and cert['queue'],'FORCED_QUEUE_LOST')
        # Width information does not confuse large certified INSIDE boxes with unresolved cells.
        unresolved=[n for n in cert['nodes'] if n['kind'] in ('UNDECIDED','PENDING')]
        max_width=max((b-a for n in unresolved for a,b in map(iv,n['box'][:4])),default=F(0))
        rows.append({'case_id':case,'method':method,'mode':mode,'raw_linkage':'PASS','original_receipt_sha256':hashlib.sha256((root/'raw'/(unit+'.receipt.json')).read_bytes()).hexdigest(),
                     'original_costs':receipt['costs'],'original_total_wall_seconds':receipt['total_wall_seconds'],
                     'original_peak_rss_kib':receipt['peak_rss_kib'],'termination':result['termination'],
                     'counts':cert['counts'],'queue_length':len(cert['queue']), 'domain_contact':cert['domain_contact'],
                     'max_unresolved_position_width':str(max_width),'point_evaluation':eval_status,'mirror':mirror,
                     'truth_bias_recovery_evaluation_only':None if mode=='no_peer' else recovery(x,z),
                     'projections':{car:{k:v for k,v in p.items() if k!='rectangles'} for car,p in cert['projections'].items()}})
    need(len(rows)==44,'AUDIT_DENOMINATOR')
    return {'raw_linkage_and_evaluation':'PASS','formal_denominator':lock['formal_denominator'],'completed':44,'failed':0,'unexecuted':0,
            'outside_plan':lock['outside_plan_records'],'conditional_random':lock['conditional_random'],
            'search_calls':0,'cost_scope':'archival linkage and consistency, not independent proof of historical wall-clock measurement',
            'rows':rows}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--evidence',required=True);p.add_argument('--evaluation',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    result=audit(a.evidence,a.evaluation);Path(a.out).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('Read-only audit passed:',len(result['rows']))

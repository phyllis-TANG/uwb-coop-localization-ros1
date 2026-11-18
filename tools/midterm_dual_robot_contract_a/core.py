"""DUAL-A-V1: independent exact-rational certificate kernel; no locator imports."""
import hashlib
import json
import math
from fractions import Fraction as F

BASE = '3ad69c8137183c1986012e354857b73527978c48'
VERSION = 'DUAL-A-V1'
ORDER = ['p_x', 'p_y', 's_x', 's_y', 'b']
IDS = [f't0/{car}/a{k}' for car in ('p', 's') for k in range(4)] + ['t0/p/s/peer']
POLICY = {'kind': 'rational_isqrt', 'sqrt_digits': 30, 'closed_sets': True}

class Invalid(ValueError):
    pass

def need(ok, message):
    if not ok:
        raise Invalid(message)

def q(x):
    need(isinstance(x, str), 'RATIONAL_STRING_REQUIRED')
    try:
        return F(x)
    except (ValueError, ZeroDivisionError):
        raise Invalid('INVALID_RATIONAL')

def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()

def digest(x):
    return hashlib.sha256(canonical(x)).hexdigest()

def seal(x):
    x['input_hash'] = digest({k:v for k,v in x.items() if k != 'input_hash'})
    return x

def iv(v):
    need(isinstance(v, list) and len(v)==2, 'INVALID_INTERVAL')
    a,b=map(q,v)
    need(a<=b, 'REVERSED_INTERVAL')
    return a,b

def sqrt_bounds(x):
    need(x>=0, 'NEGATIVE_SQRT')
    scale=10**30
    k=math.isqrt(x.numerator*scale*scale//x.denominator)
    lo=F(k,scale)
    return lo, lo if lo*lo==x else F(k+1,scale)

def square(v):
    a,b=v
    return (0 if a<=0<=b else min(a*a,b*b), max(a*a,b*b))

def distance(a,b):
    bounds=[square((x[0]-y[1],x[1]-y[0])) for x,y in zip(a,b)]
    return sqrt_bounds(sum(x[0] for x in bounds))[0], sqrt_bounds(sum(x[1] for x in bounds))[1]

def gap(x,y):
    return max(F(0), y[0]-x, x-y[1])

def gap_bounds(pred,obs):
    return max(F(0),obs[0]-pred[1],pred[0]-obs[1]), max(gap(pred[0],obs),gap(pred[1],obs))

def threshold(m):
    need(m in (8,9), 'UNSUPPORTED_NOISE_DIMENSION')
    return {'id': f'DUAL-A-V1-CHI2-{m}-CHERNOFF', 'dimension': m, 'tau': str(2*m+8),
            'alpha': '1/20', 'method': 'mgf_t_1/4_squared_taylor_80', 't': '1/4', 'terms':80}

def threshold_check(c,m):
    need(c==threshold(m), 'THRESHOLD_IDENTITY_MISMATCH')
    # P(chi2_m > tau)^2 <= 2^m exp(-tau/2).
    x=q(c['tau'])/2
    term=F(1); total=term
    for k in range(1,80):
        term*=x/k; total+=term
    bound=F(2**m)/total
    need(bound<=q(c['alpha'])**2, 'TAIL_NOT_CERTIFIED')
    return {'tail_squared_upper':str(bound), 'alpha_squared':str(q(c['alpha'])**2)}

def validate(x):
    required={'schema_version','model_id','state_order','measurement_ids','anchor_map','bias_incidence','domains',
              'observation_intervals','noise_model','threshold_certificate','arithmetic_policy','budget','input_hash',
              'source_commit','case_id','units','frame','epoch','antenna_reference','representation','position_prior','motion'}
    need(set(x)==required, 'INPUT_KEYS_MISMATCH_OR_TRUTH_LEAK')
    need(x['schema_version']==VERSION and x['model_id']=='dual_robot_single_epoch_diagonal_v1','MODEL_UNSUPPORTED')
    need(x['state_order']==ORDER and x['source_commit']==BASE,'STATE_OR_SOURCE_MISMATCH')
    need(x['measurement_ids']==IDS, 'OBSERVATION_IDENTITY_OR_DUPLICATE')
    need(x['bias_incidence']==[0]*8+[1], 'UNSUPPORTED_BIAS_LINKS')
    need(x['units']=='m' and x['frame']=='synthetic_xy' and x['epoch']=='t0' and x['antenna_reference']=='2d_antenna','UNSUPPORTED_UNITS_FRAME_EPOCH')
    need(x['position_prior'] is None and x['motion'] is None,'UNSUPPORTED_PRIOR_OR_MOTION')
    need(x['representation']=='enclosing_closed_cartesian_intervals','UNSUPPORTED_REPRESENTATION')
    need(x['arithmetic_policy']==POLICY,'UNSUPPORTED_ARITHMETIC')
    need(set(x['anchor_map'])=={f'a{k}' for k in range(4)}, 'ANCHOR_IDENTITY')
    for a in x['anchor_map'].values():
        need(len(a)==2,'ANCHOR_DIMENSION'); [q(t) for t in a]
    need(len(x['domains'])==5 and len(x['observation_intervals'])==9,'DIMENSION_MISMATCH')
    [iv(t) for t in x['domains']+x['observation_intervals']]
    n=x['noise_model']
    need(set(n)=={'kind','dimension','variance','independence','bias_evolution'},'UNSUPPORTED_R_OR_NOISE_FIELDS')
    need(n['kind']=='known_diagonal_gaussian' and n['dimension']==9 and n['independence']=='nine_unique_raw_errors' and n['bias_evolution']=='single_constant','UNSUPPORTED_NOISE_OR_TIME_VARYING_BIAS')
    need(len(n['variance'])==9 and all(q(t)>0 for t in n['variance']),'R_NOT_POSITIVE_DEFINITE')
    threshold_check(x['threshold_certificate'],9)
    b=x['budget']
    need(set(b)=={'max_nodes','max_seconds','position_resolution','bias_resolution'},'BUDGET_KEYS')
    need(type(b['max_nodes']) is int and b['max_nodes']>=1 and q(b['max_seconds'])>0 and q(b['position_resolution'])>0 and q(b['bias_resolution'])>0,'INVALID_BUDGET')
    need(x['input_hash']==digest({k:v for k,v in x.items() if k!='input_hash'}),'INPUT_HASH_MISMATCH')
    return x

def bounds(x, box, mode):
    """Bound min_v Q for 5d; min_(v,b) Q for 4d; min_v anchor Q for no_peer."""
    dim=5 if mode=='5d' else 4
    need(mode in ('5d','4d','no_peer') and len(box)==dim,'MODE_DIMENSION')
    z=[iv(t) for t in box]
    ds=[]
    for pos in (z[:2],z[2:4]):
        for k in range(4):
            anchor=[(q(t),q(t)) for t in x['anchor_map'][f'a{k}']]
            ds.append(distance(pos,anchor))
    obs=[iv(t) for t in x['observation_intervals']]
    if mode!='no_peer':
        d=distance(z[:2],z[2:4])
        if mode=='5d':
            ds.append((d[0]+z[4][0], d[1]+z[4][1]))
        else:
            bl,bu=iv(x['domains'][4])
            ds.append(d); obs[8]=(obs[8][0]-bu,obs[8][1]-bl)
    L=F(0); U=F(0)
    for pred, ob, var in zip(ds, obs, x['noise_model']['variance']):
        lo,hi=gap_bounds(pred,ob); L+=lo*lo/q(var); U+=hi*hi/q(var)
    return L,U

def recovery(x,point):
    need(len(point)==4,'RECOVERY_POINT_DIMENSION')
    vals=[q(t) for t in point]
    need(all(a<=v<=b for v,(a,b) in zip(vals,map(iv,x['domains'][:4]))),'RECOVERY_POINT_OUTSIDE_DOMAIN')
    box=[[str(t),str(t)] for t in vals]
    slo,shi=bounds(x,box,'no_peer'); tau=q(x['threshold_certificate']['tau'])
    bl,bu=iv(x['domains'][4]); il,iu=iv(x['observation_intervals'][8])
    d0,d1=distance([(v,v) for v in vals[:2]],[(v,v) for v in vals[2:]])
    def clip(a,b):
        a=max(a,bl); b=min(b,bu)
        return None if a>b else [str(a),str(b)]
    if tau<slo:
        return {'outer':None,'inner':None,'status':'EMPTY_PROVED'}
    v=q(x['noise_model']['variance'][8]); rout=sqrt_bounds(v*(tau-slo))[1]
    outer=clip(il-d1-rout,iu-d0+rout)
    inner=None
    if tau>=shi:
        rin=sqrt_bounds(v*(tau-shi))[0]
        inner=clip(il-d0-rin,iu-d1+rin)
    return {'outer':outer,'inner':inner,'status':'EMPTY_PROVED' if outer is None else ('FEASIBLE_PROVED' if inner is not None else 'UNDECIDED')}

def projections(nodes):
    retained=[n for n in nodes if n['kind'] in ('INSIDE','UNDECIDED','PENDING')]
    out={}
    for car,axes in [('p',(0,1)),('s',(2,3))]:
        rectangles=[{'leaf':n['id'],'box':[n['box'][k] for k in axes]} for n in retained]
        if not rectangles:
            out[car]={'rectangles':[], 'center':None,'radius':None,'radius_squared':None,'area_upper':'0'}; continue
        boxes=[[iv(t) for t in r['box']] for r in rectangles]
        lo=[min(b[j][0] for b in boxes) for j in range(2)]
        hi=[max(b[j][1] for b in boxes) for j in range(2)]
        c=[(lo[j]+hi[j])/2 for j in range(2)]
        r2=max(sum(max((b[j][0]-c[j])**2,(b[j][1]-c[j])**2) for j in range(2)) for b in boxes)
        area=min((hi[0]-lo[0])*(hi[1]-lo[1]),sum((b[0][1]-b[0][0])*(b[1][1]-b[1][0]) for b in boxes))
        out[car]={'rectangles':rectangles,'center':list(map(str,c)),'radius_squared':str(r2), 'radius':str(sqrt_bounds(r2)[1]),'area_upper':str(area)}
    return out

def check(x,c):
    validate(x)
    need(c['schema_version']==VERSION and c['input_hash']==x['input_hash'],'CERT_INPUT_IDENTITY')
    mode=c['mode']; need(mode in ('5d','4d','no_peer'),'MODE_UNSUPPORTED')
    dim=5 if mode=='5d' else 4; m=8 if mode=='no_peer' else 9
    need(c['measurement_ids']==IDS[:m], 'CERT_OBSERVATION_IDENTITY')
    threshold_check(c['threshold_certificate'],m); tau=q(c['threshold_certificate']['tau'])
    need(c['source_commit']==BASE,'CERT_SOURCE_IDENTITY')
    nodes=c['nodes']; need(isinstance(nodes,list) and nodes,'NO_COMPLETE_OUTER_CERTIFICATE')
    ids=[n['id'] for n in nodes]; need(all(isinstance(i,str) for i in ids) and len(set(ids))==len(ids),'DUPLICATE_NODE')
    by={n['id']:n for n in nodes}; need(c['root'] in by,'ROOT_MISSING')
    def equal(a,b):
        return list(map(iv,a))==list(map(iv,b))
    need(equal(by[c['root']]['box'],x['domains'][:dim]),'ROOT_DOMAIN_MISMATCH')
    seen=set(); stack=[c['root']]; counts={k:0 for k in ('SPLIT','OUTSIDE','INSIDE','UNDECIDED','PENDING')}
    while stack:
        nid=stack.pop(); need(nid in by and nid not in seen,'MISSING_OR_REUSED_BRANCH'); seen.add(nid)
        n=by[nid]; need(len(n['box'])==dim,'BOX_DIMENSION'); b=list(map(iv,n['box']))
        kind=n['kind']; need(kind in counts,'INVALID_NODE_KIND'); counts[kind]+=1
        if kind=='SPLIT':
            axis=n['axis']; need(type(axis) is int and 0<=axis<dim,'INVALID_SPLIT_AXIS')
            cut=q(n['cut']); need(b[axis][0]<cut<b[axis][1],'DEGENERATE_SPLIT')
            kids=n['children']; need(len(kids)==2 and all(k in by for k in kids),'MISSING_BRANCH')
            left=[t[:] for t in n['box']]; right=[t[:] for t in n['box']]
            left[axis][1]=n['cut']; right[axis][0]=n['cut']
            need(equal(by[kids[0]]['box'],left) and equal(by[kids[1]]['box'],right),'CHILDREN_DO_NOT_COVER_PARENT')
            stack.extend(reversed(kids))
        else:
            need('children' not in n,'LEAF_HAS_CHILDREN')
            lo,hi=bounds(x,n['box'],mode)
            if kind=='OUTSIDE': need(lo>tau,'FALSE_OUTSIDE')
            if kind=='INSIDE': need(hi<=tau,'FALSE_INSIDE')
    need(seen==set(ids),'UNREACHABLE_NODE')
    pending=[n['id'] for n in nodes if n['kind']=='PENDING']
    need(c['queue']==pending,'LOST_OR_REORDERED_QUEUE')
    keep=[n for n in nodes if n['kind'] in ('INSIDE','UNDECIDED','PENDING')]
    need(c['projections']==projections(nodes),'PROJECTION_OR_RADIUS_MISMATCH')
    contact=any(any(iv(t)[0]==iv(r)[0] or iv(t)[1]==iv(r)[1] for t,r in zip(n['box'],x['domains'][:dim])) for n in keep)
    need(c['domain_contact']==contact,'DOMAIN_CONTACT_MISMATCH')
    need(c['counts']==counts,'COUNTS_MISMATCH')
    cost=c['cost']; processed=len(nodes)-counts['PENDING']
    need(cost['processed_nodes']==processed and processed<=x['budget']['max_nodes'],'NODE_BUDGET_OR_COST_MISMATCH')
    for name in ('search_seconds','certificate_write_seconds','peak_rss_bytes'):
        need(q(cost[name])>=0,'INVALID_RAW_COST')
    need(type(cost['distance_evaluations']) is int and cost['distance_evaluations']>=0,'INVALID_RAW_COST')
    status=c['status']
    if status=='EMPTY_IN_DECLARED_DOMAIN': need(not keep and not pending,'FALSE_EMPTY')
    elif status=='BUDGET_OUTER': need(bool(pending),'BUDGET_WITHOUT_QUEUE')
    elif status=='OUTER_CERTIFIED': need(bool(keep) and not pending,'INVALID_COMPLETE_STATUS')
    else: raise Invalid('STATUS_UNSUPPORTED')
    need(c['internal_semantics']==('forall_state_exists_observation' if mode=='5d' else ('forall_position_exists_bias_and_observation' if mode=='4d' else 'forall_position_exists_observation')),'QUANTIFIER_MISMATCH')
    for r in c['bias_recovery']:
        need(r['result']==recovery(x,r['point']),'BIAS_RECOVERY_MISMATCH')
    return {'certificate_valid':True,'input_hash':x['input_hash'],'mode':mode,'counts':counts,
            'status':status,'cost_attestation':'structural counters checked; timing/RSS self-reported, not independently measurable from archive'}

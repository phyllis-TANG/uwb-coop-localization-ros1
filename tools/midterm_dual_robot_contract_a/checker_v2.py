"""A independent checker v2. Fresh input-scoped exact caches, no search imports.

Public integration: check(input_object, certificate) -> identical v1 result.
The frozen core.py remains the arithmetic and semantic reference.
"""
import importlib.util as _importlib
from pathlib import Path as _Path

# Explicit sibling loading is essential: B also has a module named core.py.
# Importing this entry by file path must never import B's search core accidentally.
_spec=_importlib.spec_from_file_location('dual_a_v1_frozen_kernel',_Path(__file__).with_name('core.py'))
_core=_importlib.module_from_spec(_spec)
_spec.loader.exec_module(_core)
(BASE, VERSION, IDS, F, Invalid, need, q, iv, distance, gap_bounds,
 sqrt_bounds, threshold_check, validate)=tuple(getattr(_core,name) for name in
 ('BASE','VERSION','IDS','F','Invalid','need','q','iv','distance','gap_bounds',
  'sqrt_bounds','threshold_check','validate'))

CHECKER_VERSION='DUAL-A-CHECKER-V2'

class PreparedInput:
    """One immutable parsed-input snapshot. No global, cross-car or cross-input cache."""
    def __init__(self,x):
        validate(x)
        self._rationals={}
        self.domains=tuple(self.interval(v) for v in x['domains'])
        self.anchors=tuple(tuple((self.rational(t),self.rational(t)) for t in x['anchor_map'][f'a{k}']) for k in range(4))
        self.obs=tuple(self.interval(v) for v in x['observation_intervals'])
        self.variance=tuple(self.rational(v) for v in x['noise_model']['variance'])
        self.tau=self.rational(x['threshold_certificate']['tau'])
        bl,bu=self.domains[4]
        self.peer_target=(self.obs[8][0]-bu,self.obs[8][1]-bl)
        # Entries contain all four exact distance bounds AND their residual sums.
        # Car identity is essential because the eight observation/variance rows differ.
        self._anchor_cache={}
        self.anchor_hits=0; self.anchor_misses=0

    def rational(self,t):
        need(isinstance(t,str),'RATIONAL_STRING_REQUIRED')
        if t not in self._rationals:self._rationals[t]=q(t)
        return self._rationals[t]

    def interval(self,v):
        need(isinstance(v,list) and len(v)==2,'INVALID_INTERVAL')
        a,b=map(self.rational,v); need(a<=b,'REVERSED_INTERVAL');return a,b

    def box(self,b):return tuple(self.interval(v) for v in b)

    def anchors_for(self,car,pos):
        key=(car,tuple(pos))
        if key in self._anchor_cache:
            self.anchor_hits+=1; return self._anchor_cache[key]
        self.anchor_misses+=1
        ds=tuple(distance(pos,a) for a in self.anchors)
        lo=F(0);hi=F(0)
        for k,d in enumerate(ds):
            j=4*car+k; low,high=gap_bounds(d,self.obs[j])
            lo+=low*low/self.variance[j];hi+=high*high/self.variance[j]
        result=(ds,lo,hi); self._anchor_cache[key]=result
        return result

    def bounds_parsed(self,z,mode):
        dim=5 if mode=='5d' else 4
        need(mode in ('5d','4d','no_peer') and len(z)==dim,'MODE_DIMENSION')
        _,pl,pu=self.anchors_for(0,z[:2]);_,sl,su=self.anchors_for(1,z[2:4])
        lo,hi=pl+sl,pu+su
        if mode!='no_peer':
            d=distance(z[:2],z[2:4])
            if mode=='5d':
                d=(d[0]+z[4][0],d[1]+z[4][1]); target=self.obs[8]
            else:target=self.peer_target
            low,high=gap_bounds(d,target)
            lo+=low*low/self.variance[8];hi+=high*high/self.variance[8]
        return lo,hi

    def bounds(self,box,mode):return self.bounds_parsed(self.box(box),mode)

    def recovery(self,point):
        need(len(point)==4,'RECOVERY_POINT_DIMENSION')
        vals=tuple(self.rational(t) for t in point)
        need(all(a<=v<=b for v,(a,b) in zip(vals,self.domains[:4])),'RECOVERY_POINT_OUTSIDE_DOMAIN')
        z=tuple((v,v) for v in vals)
        slo,shi=self.bounds_parsed(z,'no_peer');tau=self.tau
        bl,bu=self.domains[4];il,iu=self.obs[8];d0,d1=distance(z[:2],z[2:4])
        def clip(a,b):
            a=max(a,bl);b=min(b,bu)
            return None if a>b else [str(a),str(b)]
        if tau<slo:return {'outer':None,'inner':None,'status':'EMPTY_PROVED'}
        v=self.variance[8];rout=sqrt_bounds(v*(tau-slo))[1]
        outer=clip(il-d1-rout,iu-d0+rout);inner=None
        if tau>=shi:
            rin=sqrt_bounds(v*(tau-shi))[0];inner=clip(il-d0-rin,iu-d1+rin)
        return {'outer':outer,'inner':inner,'status':'EMPTY_PROVED' if outer is None else ('FEASIBLE_PROVED' if inner is not None else 'UNDECIDED')}

    def projections(self,nodes):
        retained=[n for n in nodes if n['kind'] in ('INSIDE','UNDECIDED','PENDING')]
        out={}
        for car,axes in [('p',(0,1)),('s',(2,3))]:
            rectangles=[{'leaf':n['id'],'box':[n['box'][k] for k in axes]} for n in retained]
            if not rectangles:
                out[car]={'rectangles':[], 'center':None,'radius':None,'radius_squared':None,'area_upper':'0'};continue
            boxes=[self.box(r['box']) for r in rectangles]
            lo=[min(b[j][0] for b in boxes) for j in range(2)]
            hi=[max(b[j][1] for b in boxes) for j in range(2)]
            c=[(lo[j]+hi[j])/2 for j in range(2)]
            r2=max(sum(max((b[j][0]-c[j])**2,(b[j][1]-c[j])**2) for j in range(2)) for b in boxes)
            area=min((hi[0]-lo[0])*(hi[1]-lo[1]),sum((b[0][1]-b[0][0])*(b[1][1]-b[1][0]) for b in boxes))
            out[car]={'rectangles':rectangles,'center':list(map(str,c)),'radius_squared':str(r2),'radius':str(sqrt_bounds(r2)[1]),'area_upper':str(area)}
        return out


def check(x,c):
    ctx=PreparedInput(x)
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
        return ctx.box(a)==ctx.box(b)
    need(equal(by[c['root']]['box'],x['domains'][:dim]),'ROOT_DOMAIN_MISMATCH')
    seen=set(); stack=[c['root']]; counts={k:0 for k in ('SPLIT','OUTSIDE','INSIDE','UNDECIDED','PENDING')}
    while stack:
        nid=stack.pop(); need(nid in by and nid not in seen,'MISSING_OR_REUSED_BRANCH'); seen.add(nid)
        n=by[nid]; need(len(n['box'])==dim,'BOX_DIMENSION'); b=ctx.box(n['box'])
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
            lo,hi=ctx.bounds_parsed(b,mode)
            if kind=='OUTSIDE': need(lo>tau,'FALSE_OUTSIDE')
            if kind=='INSIDE': need(hi<=tau,'FALSE_INSIDE')
    need(seen==set(ids),'UNREACHABLE_NODE')
    pending=[n['id'] for n in nodes if n['kind']=='PENDING']
    need(c['queue']==pending,'LOST_OR_REORDERED_QUEUE')
    keep=[n for n in nodes if n['kind'] in ('INSIDE','UNDECIDED','PENDING')]
    need(c['projections']==ctx.projections(nodes),'PROJECTION_OR_RADIUS_MISMATCH')
    contact=any(any(ctx.interval(t)[0]==ctx.interval(r)[0] or ctx.interval(t)[1]==ctx.interval(r)[1] for t,r in zip(n['box'],x['domains'][:dim])) for n in keep)
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
        need(r['result']==ctx.recovery(r['point']),'BIAS_RECOVERY_MISMATCH')
    return {'certificate_valid':True,'input_hash':x['input_hash'],'mode':mode,'counts':counts,
            'status':status,'cost_attestation':'structural counters checked; timing/RSS self-reported, not independently measurable from archive'}

if __name__=='__main__':
    import argparse
    import json
    from check import read_json
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('inputs',help='Frozen input array JSON or one input object JSON')
    p.add_argument('case_id');p.add_argument('certificate');a=p.parse_args()
    try:
        xs=read_json(a.inputs)
        if isinstance(xs,dict):xs=[xs]
        matching=[x for x in xs if x['case_id']==a.case_id]
        need(len(matching)==1,'INPUT_CASE_NOT_UNIQUE')
        print(json.dumps(check(matching[0],read_json(a.certificate)),ensure_ascii=False,indent=2))
    except (Invalid,KeyError,TypeError,ValueError) as e:
        print(json.dumps({'certificate_valid':False,'error':str(e)},ensure_ascii=False));raise SystemExit(1)

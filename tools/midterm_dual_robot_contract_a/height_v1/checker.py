"""Single-epoch fixed-height slant-range certificate verifier (standard library)."""
import argparse
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('a_height_tree', Path(__file__).resolve().parents[1]/'checker_v2.py')
V = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V)
K = V._core
F, need, q, iv = K.F, K.need, K.q, K.iv
VERSION = 'DUAL-FIXED-HEIGHT-1'
BASE = '8acffa9f4061e4740c18c7d0f1e09d28cf7f3155'


def read(path):
    def unique(pairs):
        obj = dict(pairs)
        need(len(obj)==len(pairs), 'DUPLICATE_JSON_KEY')
        return obj
    return json.loads(Path(path).read_text(), object_pairs_hook=unique)


def validate(x):
    fields = 'schema_version source_commit case_id frame units source_times heights anchors measurement_ids observations variance bias_domain arithmetic_policy domain_source budget input_hash'
    need(set(x)==set(fields.split()), 'INPUT_FIELDS')
    need(x['schema_version']==VERSION and x['source_commit']==BASE, 'VERSION')
    need(x['units']=='m' and x['frame']=='moon_map_z_up' and x['domain_source']=='joint_event_26', 'UNSUPPORTED_FRAME_OR_DOMAIN')
    need(x['arithmetic_policy']==K.POLICY, 'ROUNDING')
    need(set(x['heights'])==set(x['source_times'])=={'p','s'}, 'CAR_IDENTITY')
    for car in ('p','s'):
        q(x['heights'][car])
        q(x['source_times'][car])
    need(q(x['source_times']['p'])-q(x['source_times']['s'])==5,'SOURCE_TIME_ALIGNMENT')
    need(set(x['anchors'])=={'a0','a1','a2','a3'}, 'ANCHOR_IDENTITY')
    for xyz in x['anchors'].values():
        need(len(xyz)==3,'ANCHOR_DIMENSION')
        tuple(map(q,xyz))
    m=len(x['measurement_ids'])
    need(m in (8,9) and x['measurement_ids']==K.IDS[:m], 'MEASUREMENT_IDENTITY')
    need(len(x['observations'])==len(x['variance'])==m, 'OBSERVATION_COUNT')
    list(map(iv,x['observations']))
    need(all(q(v)>0 for v in x['variance']), 'VARIANCE')
    iv(x['bias_domain'])
    b=x['budget']
    need(set(b)=={'max_nodes','max_seconds','position_resolution'} and type(b['max_nodes']) is int and b['max_nodes']>0 and q(b['max_seconds'])>0 and q(b['position_resolution'])>0,'BUDGET')
    need(x['input_hash']==K.digest({k:v for k,v in x.items() if k!='input_hash'}),'INPUT_HASH')


def event_root(x):
    validate(x)
    result=[]
    for car_id,car in enumerate(('p','s')):
        axes=[[],[]]
        for i in range(4):
            row=4*car_id+i
            ax,ay,az=map(q,x['anchors'][f'a{i}'])
            upper=iv(x['observations'][row])[1]+K.sqrt_bounds(26*q(x['variance'][row]))[1]
            dz=q(x['heights'][car])-az
            if upper<abs(dz):
                return None
            radius=K.sqrt_bounds(upper**2-dz**2)[1]
            for axis,center in zip(axes,(ax,ay)):
                axis.append((center-radius,center+radius))
        for axis in axes:
            lo=max(a for a,b in axis)
            hi=min(b for a,b in axis)
            if lo>hi:
                return None
            result.append([str(lo),str(hi)])
    return result


class Context(V.PreparedInput):
    def __init__(self,x,root):
        self._rationals={}
        self._anchor_cache={}
        self.anchor_hits=self.anchor_misses=0
        self.domains=tuple(map(iv,root+[x['bias_domain']]))
        self.anchors=[tuple((q(t),q(t)) for t in x['anchors'][f'a{i}']) for i in range(4)]
        self.z=[(q(x['heights'][car]),)*2 for car in ('p','s')]
        self.obs=list(map(iv,x['observations']))
        self.variance=list(map(q,x['variance']))
        self.tau=F(26)

    def peer_distance(self,z):
        return K.distance((*z[:2],self.z[0]),(*z[2:4],self.z[1]))

    def bounds_parsed(self,z,mode):
        need(len(z)==4 and mode in ('4d','no_peer'),'MODE')
        _,lo,hi=self.anchors_for(0,(*z[:2],self.z[0]))
        _,sl,sh=self.anchors_for(1,(*z[2:],self.z[1]))
        lo,hi=lo+sl,hi+sh
        if mode=='4d':
            a,b=self.domains[4]
            l,u=self.obs[8]
            g,h=K.gap_bounds(self.peer_distance(z),(l-b,u-a))
            lo+=g*g/self.variance[8]
            hi+=h*h/self.variance[8]
        return lo,hi

    def recovery(self,point):
        need(len(point)==4,'RECOVERY_POINT_DIMENSION')
        vals=tuple(self.rational(t) for t in point)
        need(all(a<=v<=b for v,(a,b) in zip(vals,self.domains[:4])),'RECOVERY_POINT_OUTSIDE_DOMAIN')
        z=tuple((v,v) for v in vals)
        slo,shi=self.bounds_parsed(z,'no_peer');tau=self.tau
        bl,bu=self.domains[4];il,iu=self.obs[8];d0,d1=self.peer_distance(z)
        def clip(a,b):
            a=max(a,bl);b=min(b,bu)
            return None if a>b else [str(a),str(b)]
        if tau<slo:return {'outer':None,'inner':None,'status':'EMPTY_PROVED'}
        v=self.variance[8];rout=K.sqrt_bounds(v*(tau-slo))[1]
        outer=clip(il-d1-rout,iu-d0+rout);inner=None
        if tau>=shi:
            rin=K.sqrt_bounds(v*(tau-shi))[0];inner=clip(il-d0-rin,iu-d1+rin)
        return {'outer':outer,'inner':inner,'status':'EMPTY_PROVED' if outer is None else ('FEASIBLE_PROVED' if inner is not None else 'UNDECIDED')}


def check(x,c):
    root=event_root(x)
    need(c['schema_version']==VERSION and c['source_commit']==BASE and c['input_hash']==x['input_hash'],'CERT_IDENTITY')
    mode=c['mode']
    need(mode in ('4d','no_peer'),'MODE')
    m=9 if mode=='4d' else 8
    need(c['measurement_ids']==K.IDS[:m] and len(x['measurement_ids'])>=m,'MEASUREMENT_IDENTITY')
    K.threshold_check(c['threshold_certificate'],m)
    tau=q(c['threshold_certificate']['tau'])
    dim=4
    if root is None:
        need(set(c)=={'schema_version','source_commit','input_hash','mode','measurement_ids','threshold_certificate','status'} and c['status']=='EVENT_ROOT_EMPTY','EMPTY_ROOT_FORMAT')
        return {'certificate_valid':True,'status':'EVENT_ROOT_EMPTY','input_hash':x['input_hash'],'mode':mode}
    ctx=Context(x,root)
    need(mode=='4d' or c['bias_recovery']==[], 'N4_HAS_NO_BIAS')
    nodes=c['nodes']; need(isinstance(nodes,list) and nodes,'NO_COMPLETE_OUTER_CERTIFICATE')
    ids=[n['id'] for n in nodes]; need(all(isinstance(i,str) for i in ids) and len(set(ids))==len(ids),'DUPLICATE_NODE')
    by={n['id']:n for n in nodes}; need(c['root'] in by,'ROOT_MISSING')
    def equal(a,b):
        return ctx.box(a)==ctx.box(b)
    need(equal(by[c['root']]['box'],root),'ROOT_DOMAIN_MISMATCH')
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
    contact=any(any(ctx.interval(t)[0]==ctx.interval(r)[0] or ctx.interval(t)[1]==ctx.interval(r)[1] for t,r in zip(n['box'],root)) for n in keep)
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
    else: raise K.Invalid('STATUS_UNSUPPORTED')
    need(c['internal_semantics']==('forall_state_exists_observation' if mode=='5d' else ('forall_position_exists_bias_and_observation' if mode=='4d' else 'forall_position_exists_observation')),'QUANTIFIER_MISMATCH')
    for r in c['bias_recovery']:
        need(r['result']==ctx.recovery(r['point']),'BIAS_RECOVERY_MISMATCH')
    return {'certificate_valid':True,'input_hash':x['input_hash'],'mode':mode,'counts':counts,
            'status':status,'cost_attestation':'structural counters checked; timing/RSS self-reported, not independently measurable from archive'}

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('input')
    parser.add_argument('certificate',nargs='?',help='omit to compute certified root')
    args=parser.parse_args()
    try:
        x=read(args.input)
        print(json.dumps(check(x,read(args.certificate)) if args.certificate else event_root(x),indent=2))
    except (ValueError,KeyError,IndexError,TypeError) as error:
        print(json.dumps({'certificate_valid':False,'reason':str(error)}))
        raise SystemExit(1)

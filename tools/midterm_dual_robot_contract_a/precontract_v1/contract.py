"""Independent root-cover certificate + frozen P4 checker composition. No search."""
import copy
import importlib.util
import json
from pathlib import Path

_spec=importlib.util.spec_from_file_location('dual_a_locked_checker_v2',Path(__file__).resolve().parents[1]/'checker_v2.py')
V2=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(V2)
K=V2._core
F=K.F
VERSION='DUAL-P4-PRECONTRACT-V1'
A_START='50b592fbd672a1f19075147f53061a5861b3b892'
DIRECTIONS=tuple((car,axis,sign) for car in ('p','s') for axis in (0,1) for sign in (-1,1))
BUDGET={'per_direction_seconds':'1/2','total_seconds':'4'}
FALLBACKS={'FALLBACK_TIMEOUT','FALLBACK_UNCERTIFIED','FALLBACK_ERROR'}

class Rejected(ValueError):pass

def require(ok,code,detail=''):
    if not ok:raise Rejected(code+(': '+detail if detail else ''))

def rational(x):
    try:return K.q(x)
    except (ValueError,TypeError) as e:raise Rejected('INVALID_RATIONAL: '+str(e))

def interval(x):
    try:return K.iv(x)
    except (ValueError,TypeError) as e:raise Rejected('INVALID_INTERVAL: '+str(e))

def direction_id(car,axis,sign):return car+'_'+('x','y')[axis]+('_min' if sign<0 else '_max')

def dot(a,b):return sum((x*y for x,y in zip(a,b)),F(0))

def vec(x):
    require(isinstance(x,list) and len(x)==2,'VECTOR_DIMENSION');return tuple(map(rational,x))

class Model:
    def __init__(self,x):
        K.validate(x)
        self.x=x;self.domains=tuple(map(interval,x['domains'][:4]))
        self.anchors=tuple(tuple(map(rational,x['anchor_map']['a'+str(i)])) for i in range(4))
        self.ranges={};self.rows={};self.radii={}
        tau=rational(x['threshold_certificate']['tau'])
        require(tau==26,'ORIGINAL_Q9_CHANGED')
        for car,offset in [('p',0),('s',4)]:
            ranges=[]
            for i in range(4):
                l,u=interval(x['observation_intervals'][offset+i]);v=rational(x['noise_model']['variance'][offset+i])
                rho=K.sqrt_bounds(tau*v)[1]
                low=max(F(0),l-rho);high=max(F(0),u+rho)
                ranges.append({'measurement_id':x['measurement_ids'][offset+i],'rho_upper':str(rho),'lower':str(low),'upper':str(high)})
                self.radii[(car,i)]=high
            self.ranges[car]=ranges
            rows={}
            # Independent reconstruction from ORIGINAL observations; no supplied row coefficients.
            for i in range(4):
                ai=self.anchors[i]
                for j in range(4):
                    if i==j:continue
                    aj=self.anchors[j]
                    c=tuple(2*(aj[k]-ai[k]) for k in range(2))
                    rhs=rational(ranges[i]['upper'])**2-rational(ranges[j]['lower'])**2-dot(ai,ai)+dot(aj,aj)
                    rows[f'{car}:pair:a{i}:a{j}']=(c,rhs)
            car_domain=self.domains[0:2] if car=='p' else self.domains[2:4]
            for axis in (0,1):
                for sign in (-1,1):
                    normal=tuple(F(sign if k==axis else 0) for k in range(2));tag='-' if sign<0 else '+'
                    rhs=sign*car_domain[axis][0 if sign<0 else 1]
                    rows[f'{car}:domain:{axis}:{tag}']=(normal,rhs)
                    for i,a in enumerate(self.anchors):
                        rows[f'{car}:ball_axis:a{i}:{axis}:{tag}']=(normal,sign*a[axis]+self.radii[(car,i)])
            self.rows[car]=rows

    def support(self,car,axis,sign,proof):
        require(isinstance(proof,dict) and set(proof)=={'kind','linear','balls','residual','support_upper'},'INVALID_SUPPORT_FORMAT')
        require(proof['kind']=='rational_support_v1','UNSUPPORTED_SUPPORT_KIND')
        coeff=[F(0),F(0)];constant=F(0);used=set()
        for item in proof['linear']:
            require(set(item)=={'row_id','weight'},'INVALID_LINEAR_TERM')
            rid=item['row_id']
            require(rid in self.rows[car],'ROW_ID_OR_VEHICLE_MISMATCH',str(rid))
            require(rid not in used,'DUPLICATE_PROOF_ROW');used.add(rid)
            w=rational(item['weight']);require(w>=0,'NEGATIVE_MULTIPLIER')
            normal,rhs=self.rows[car][rid]
            for k in range(2):coeff[k]+=w*normal[k]
            constant+=w*rhs
        used_balls=set()
        for item in proof['balls']:
            require(set(item)=={'anchor_id','vector','t'},'INVALID_BALL_TERM')
            name=item['anchor_id'];require(name in ('a0','a1','a2','a3') and name not in used_balls,'INVALID_BALL_ANCHOR');used_balls.add(name)
            i=int(name[1]);w=vec(item['vector']);t=rational(item['t'])
            require(t>=0 and t*t>=dot(w,w),'SOC_DUAL_NOT_CERTIFIED')
            for k in range(2):coeff[k]+=w[k]
            constant+=dot(w,self.anchors[i])+t*self.radii[(car,i)]
        target=tuple(F(sign if k==axis else 0) for k in range(2))
        residual=tuple(target[k]-coeff[k] for k in range(2))
        require(vec(proof['residual'])==residual,'RESIDUAL_MISMATCH')
        domain=self.domains[:2] if car=='p' else self.domains[2:]
        correction=sum((residual[k]*domain[k][1 if residual[k]>=0 else 0] for k in range(2)),F(0))
        upper=constant+correction
        require(rational(proof['support_upper'])==upper,'SUPPORT_BOUND_MISMATCH')
        return upper


def verify_preprocessing(x,p):
    model=Model(x)
    required={'schema_version','source_contract_commit','original_input_hash','measurement_ids','original_domain','range_enclosures',
              'directions','contracted_domain','status','budget','cost'}
    require(isinstance(p,dict) and set(p)==required,'PREPROCESS_FIELDS')
    require(p['schema_version']==VERSION and p['source_contract_commit']==A_START,'PREPROCESS_VERSION_OR_SOURCE')
    require(p['original_input_hash']==x['input_hash'],'ORIGINAL_INPUT_HASH_MISMATCH')
    require(p['measurement_ids']==x['measurement_ids'],'MEASUREMENT_IDENTITY_MISMATCH')
    require(tuple(map(interval,p['original_domain']))==model.domains,'ORIGINAL_DOMAIN_MISMATCH')
    require(p['range_enclosures']==model.ranges,'RANGE_ENCLOSURE_OR_VEHICLE_MISMATCH')
    require(p['budget']==BUDGET,'PREPROCESS_BUDGET_CHANGED')
    require(set(p['cost'])=={'preprocess_seconds'} and rational(p['cost']['preprocess_seconds'])>=0,'INVALID_PREPROCESS_COST')
    require(isinstance(p['directions'],list) and len(p['directions'])==8,'EIGHT_DIRECTIONS_REQUIRED')
    adopted=[list(d) for d in model.domains];verdicts=[]
    for record,(car,axis,sign) in zip(p['directions'],DIRECTIONS):
        require(set(record)=={'id','car','axis','sign','status','original_endpoint','candidate_endpoint','adopted_endpoint','proof','reason','elapsed_seconds'},'DIRECTION_FIELDS')
        did=direction_id(car,axis,sign)
        require(record['id']==did and record['car']==car and type(record['axis']) is int and record['axis']==axis and type(record['sign']) is int and record['sign']==sign,'DIRECTION_ID_OR_SIGN_MISMATCH',did)
        idx=(0 if car=='p' else 2)+axis;side=0 if sign<0 else 1;original=model.domains[idx][side]
        require(rational(record['original_endpoint'])==original,'DIRECTION_ORIGINAL_ENDPOINT_MISMATCH',did)
        require(isinstance(record['reason'],str) and bool(record['reason']),'MISSING_DIRECTION_REASON')
        elapsed=rational(record['elapsed_seconds']);require(elapsed>=0,'NEGATIVE_DIRECTION_COST')
        if record['status']=='CERTIFIED':
            require(elapsed<=F(1,2),'DIRECTION_BUDGET_EXCEEDED_WITHOUT_FALLBACK',did)
            bound=model.support(car,axis,sign,record['proof']);candidate=rational(record['candidate_endpoint'])
            require(sign*candidate>=bound,'CANDIDATE_ENDPOINT_INWARD',did)
            endpoint=max(original,candidate) if sign<0 else min(original,candidate)
            reason='已验证非负组合/锥条件与原域残差修正，闭端点向外有效'
        else:
            require(record['status'] in FALLBACKS,'UNSUPPORTED_DIRECTION_STATUS',did)
            require(record['proof'] is None,'FALLBACK_MUST_NOT_USE_PROOF',did)
            if record['candidate_endpoint'] is not None:rational(record['candidate_endpoint'])
            endpoint=original;reason='未使用候选端点，保留原方向端点'
        require(rational(record['adopted_endpoint'])==endpoint,'ADOPTED_ENDPOINT_MISMATCH',did)
        adopted[idx][side]=endpoint
        verdicts.append({'id':did,'status':record['status'],'accepted_endpoint':str(endpoint),'reason':reason})
    empty=any(a>b for a,b in adopted)
    if empty:
        require(p['status']=='EMPTY_PROVED' and p['contracted_domain'] is None,'EMPTY_DOMAIN_REPRESENTATION')
        box=None
    else:
        box=[[str(a),str(b)] for a,b in adopted]
        require(p['status']=='BOX_CERTIFIED' and tuple(map(interval,p['contracted_domain']))==tuple(map(tuple,adopted)),'CONTRACTED_DOMAIN_MISMATCH')
    return {'accepted':True,'schema_version':VERSION,'status':p['status'],'original_input_hash':x['input_hash'],
            'contracted_domain':box,'directions':verdicts,'preprocess_hash':K.digest(p),
            'cost_within_declared_total':rational(p['cost']['preprocess_seconds'])<=4,
            'claim':'all original P4-compatible positions are inside contracted_domain, or original P4 set is empty'}


def restricted_input(x,p):
    result=verify_preprocessing(x,p)
    if result['status']=='EMPTY_PROVED':return None
    y=copy.deepcopy(x);y['domains'][:4]=result['contracted_domain'];return K.seal(y)


def check_composite(x,c):
    require(isinstance(c,dict) and set(c)=={'schema_version','original_input_hash','preprocessing','preprocess_hash','restricted_input_hash','search_certificate'},'COMPOSITE_FIELDS')
    require(c['schema_version']==VERSION and c['original_input_hash']==x['input_hash'],'COMPOSITE_ORIGINAL_IDENTITY')
    pre=verify_preprocessing(x,c['preprocessing'])
    require(c['preprocess_hash']==pre['preprocess_hash'],'PREPROCESS_HASH_MISMATCH')
    if pre['status']=='EMPTY_PROVED':
        require(c['restricted_input_hash'] is None and c['search_certificate'] is None,'EMPTY_MUST_NOT_INVENT_TREE')
        return {'accepted':True,'status':'EMPTY_IN_ORIGINAL_DOMAIN','original_input_hash':x['input_hash'],'preprocessing':pre,'tree':None,'original_domain_contact':False}
    y=copy.deepcopy(x);y['domains'][:4]=pre['contracted_domain'];K.seal(y)
    require(c['restricted_input_hash']==y['input_hash'],'RESTRICTED_INPUT_HASH_MISMATCH')
    cert=c['search_certificate'];require(isinstance(cert,dict) and cert.get('mode')=='4d','ONLY_P4_TREE_SUPPORTED')
    # Frozen checker enforces EXACT derived root, original observations/q/bias and all leaves/queue.
    tree=V2.check(y,cert)
    keep=[n for n in cert['nodes'] if n['kind'] in ('INSIDE','UNDECIDED','PENDING')]
    original_contact=any(any(interval(t)[0]==interval(r)[0] or interval(t)[1]==interval(r)[1] for t,r in zip(n['box'],x['domains'][:4])) for n in keep)
    return {'accepted':True,'status':'COMPOSITE_OUTER_CERTIFIED','original_input_hash':x['input_hash'],'preprocessing':pre,
            'restricted_input_hash':y['input_hash'],'tree':tree,'original_domain_contact':original_contact,
            'contracted_domain_contact':cert['domain_contact'],'projection_hash':K.digest(cert['projections']),
            'claim':'the retained boxes and complete pending queue contain all original P4-compatible positions'}


def load_json(path):
    def unique(pairs):
        result={}
        for k,v in pairs:require(k not in result,'DUPLICATE_JSON_KEY');result[k]=v
        return result
    return json.loads(Path(path).read_text(),object_pairs_hook=unique)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['pre','derive','composite'])
    parser.add_argument('input');parser.add_argument('certificate');a=parser.parse_args()
    try:
        x=load_json(a.input);c=load_json(a.certificate)
        out=verify_preprocessing(x,c) if a.action=='pre' else restricted_input(x,c) if a.action=='derive' else check_composite(x,c)
        print(json.dumps(out,ensure_ascii=False,indent=2))
    except (ValueError,KeyError,TypeError,IndexError) as e:
        print(json.dumps({'accepted':False,'reason':str(e)},ensure_ascii=False,indent=2));raise SystemExit(1)

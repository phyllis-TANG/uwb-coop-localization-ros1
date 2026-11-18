"""Use numerical candidates only to find witnesses; decide by exact interval bounds."""
from study import *
import numpy as np
from scipy.optimize import minimize


def support_points(x,center):
    z=np.array([float(F(x['heights'][c])) for c in 'ps'])
    a=np.array([[float(F(v)) for v in x['anchors']['a'+str(k)]] for k in range(4)])
    y=np.array([float(F(lo)) for lo,hi in x['observations']]);sigma=math.sqrt(F(x['variance'][0]))
    beta=list(map(lambda s:float(F(s)),x['bias_domain']))
    def objective(flat):
        xy=flat.reshape(2,2);xyz=np.column_stack([xy,z])
        anchor=np.linalg.norm(xyz[:,None]-a,axis=2).ravel()-y[:8]
        peer=np.linalg.norm(xyz[0]-xyz[1])-y[8]
        residual=np.r_[anchor,peer+np.clip(-peer,*beta)]/sigma
        return residual@residual
    init=np.array([float(F(v)) for car in center for v in car])
    start=minimize(objective,init,method='BFGS').x
    constraint=dict(type='ineq',fun=lambda v:26-1e-5-objective(v))
    candidates=[start]
    for car in range(2):
        for angle in np.arange(24)*math.pi/12:
            d=np.zeros(4);d[2*car:2*car+2]=[math.cos(angle),math.sin(angle)]
            r=minimize(lambda v:-v@d,start,jac=lambda v:-d,method='SLSQP',constraints=[constraint],options=dict(maxiter=60,ftol=1e-10))
            candidates.append(r.x)
    valid=[]
    for pos in candidates:
        pt=[str(F(p)) for p in pos];terms=score(x,pt,True)
        if upper(terms)<=26:valid.append(pt)
    return valid


def classify(lo,hi,t):
    return 'WITHIN' if hi<=t*t else 'EXCEEDS' if lo>t*t else 'UNRESOLVED'


def process(variant,name,I):
    obj=read(D/'inputs'/variant/(name+'.json'));x=obj['original'];center=obj['center']
    path=D/'runs'/variant/'results'/name/'solution.json.gz'
    result=read(path);assert result['original']==x
    cert=result['certificate'];clock=read(path.with_suffix('.receipt.json'))['run_and_verify_s']
    true=score(x,list(map(F,obj['truth'])),True)
    noise=score(x,list(map(F,obj['truth'])))
    def membership(terms):
        return 'YES' if upper(terms)<=26 else 'NO' if sum(F(l) for l,h in terms)>26 else 'UNRESOLVED'
    event=membership(noise);feasible=membership(true)
    verified=support_points(x,center)
    assert verified,'No feasible point: record unknown or implement further search'
    rows=[];evidence={}
    for i,c in enumerate('ps'):
        pub=list(map(F,center[i]))
        def pos(p):return list(map(F,p[2*i:2*i+2]))
        def dist(a,b):return sum((p-q)**2 for p,q in zip(a,b))
        aa,bb=max(combinations(verified,2),key=lambda ab:dist(pos(ab[0]),pos(ab[1])))
        far=max(verified,key=lambda p:dist(pub,pos(p)))
        low=dist(pub,pos(far));anylow=dist(pos(aa),pos(bb))/4
        rad=I.covering_radius(cert['projections'][c]['rectangles'],center[i])
        baseline=next(r for r in csv.DictReader((BASE/'paired.csv').open()) if r['case']==name and r['car']==c)
        evidence[c]=dict(points=[aa,bb,far],published_lower2=str(low),any_lower2=str(anylow),outer=str(rad))
        rows.append(dict(case=name,car=c,variant=variant,input_hash=x['input_hash'],publish_xy=center[i],baseline_outer_cm=100*float(baseline['fine_PL_m']),outer_cm=float(rad*100),outer_reduction_cm=100*(float(baseline['fine_PL_m'])-float(rad)),published_lower_cm=math.sqrt(low)*100,any_center_lower_cm=math.sqrt(anylow)*100,pl10=classify(low,rad**2,F(1,10)),pl20=classify(low,rad**2,F(1,5)),any10=classify(anylow,rad**2,F(1,10)),any20=classify(anylow,rad**2,F(1,5)),noise_event=event,true_feasible=feasible,assumption_failure=feasible=='NO',error_cm=math.sqrt(dist(pub,list(map(F,obj['truth'][2*i:2*i+2]))))*100,seconds=clock,nodes=len(cert['nodes'])))
    write(D/'bounds'/variant/(name+'.json'),dict(input_hash=x['input_hash'],true_noise_terms=noise,true_profiled_terms=true,generated_noise_statistic=str(sum(F(v)**2/F(w) for v,w in zip(obj['generated_noise'],x['variance']))),vehicles=evidence))
    return rows


def report(I):
    baseline={(r['case'],r['car']):r for r in csv.DictReader((D/'baseline.csv').open())}
    data={}
    for variant in ['tight','matched','zero']:
        data[variant]=[r for name in PLAN['cases'] for r in process(variant,name,I)]
        write_csv(D/(variant+'.csv'),data[variant])
    combined=[]
    for z,t in zip(data['zero'],data['tight']):
        name=z['case'];car=z['car'];w=read(D/'witnesses'/(name+'.json'))['vehicles'][car]
        combined.append(dict(case=name,car=car,baseline_cm=z['baseline_outer_cm'],baseline_any_lower_cm=100*float(baseline[name,car]['any_center_lower_m']),zero_outer_cm=z['outer_cm'],zero_reduction_cm=z['outer_reduction_cm'],zero_midpoint_any_lower_cm=100*math.sqrt(F(w['min_radius2'])),tight_outer_cm=t['outer_cm'],tight_reduction_cm=t['outer_reduction_cm'],tight_published_lower_cm=t['published_lower_cm'],tight_any_lower_cm=t['any_center_lower_cm'],tight_published_10=t['pl10'],tight_published_20=t['pl20'],tight_noise_event=t['noise_event'],tight_truth=t['true_feasible']))
    write_csv(D/'attribution.csv',combined)


if __name__=='__main__':
    with tempfile.TemporaryDirectory() as tmp:
        _,I,_=prior.setup(Path(tmp));report(I)

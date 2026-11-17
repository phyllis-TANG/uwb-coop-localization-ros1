"""Only anchor coordinates vary; all actual starts and noise pair across geometry."""
from common import *
CFG=read(DOC/'CONFIG.json')

def reference_geometry():
    geo=SOURCE['geometries']['weak'];a=np.array(geo['anchors'],float);center=a.mean(0);ev,v=np.linalg.eigh((a-center).T@(a-center));assert a.shape==(4,2) and ev[-1]>0 and abs(ev[0])<=1e-12*ev[-1], 'Source anchors not collinear'
    axis=v[:,-1]
    if axis[np.flatnonzero(abs(axis)>1e-12)[0]]<0:axis=-axis
    normal=np.array([-axis[1],axis[0]]);assert np.max(abs((a-center)@normal))<1e-12
    assert np.array_equal(a,[[-3,0],[-1,0],[4,0],[6,0]]) and np.array_equal(geo['initial_positions'],[[1,0],[2,0]]) and np.array_equal(geo['survey'],[1.2,.25,1.8,-.2]),'Fixed source construction changed'
    return a,axis,normal

def conditions():
    reference_geometry()
    return [dict(id=f'g{i:02}',geometry='weak',perturbation_m=d,motion=CFG['motion'],kind=CFG['kind'],bias_m=CFG['bias_m'],prior_sigma=CFG['prior_sigma'],mechanism=CFG['prior_mechanism']) for i,d in enumerate(CFG['perturbations_m'])]

def generate(q,seed):
    original,_,normal=reference_geometry();anchors=original+q['perturbation_m']*np.array(CFG['anchor_signs'])[:,None]*normal;geo=SOURCE['geometries']['weak'];truth=np.tile(np.array(geo['initial_positions'],float),(6,1,1));rs=CFG['range_sigma'];ms=CFG['motion_sigma']
    zr=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,0]))).normal(size=54);zm=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,1]))).normal(size=20)
    clean=np.column_stack([np.linalg.norm(truth[:,:,None,:]-anchors,axis=-1).reshape(6,8),np.linalg.norm(truth[:,1]-truth[:,0],axis=-1)]).ravel();oracle=np.zeros(54);oracle[8::9]=q['bias_m'];movement=np.diff(truth.reshape(6,4),axis=0).ravel()+ms*zm;survey=np.array(geo['survey']);start=np.vstack([survey,survey+np.cumsum(movement.reshape(5,4),axis=0)]).ravel()
    obs=dict(anchors=anchors.tolist(),ranges=(clean+oracle+rs*zr).tolist(),movement=movement.tolist(),prior_center=truth[0].ravel().tolist(),start=start.tolist(),kind=q['kind'],prior_sigma=q['prior_sigma'],range_sigma=rs,motion_sigma=ms)
    u=dict(condition=q,seed=seed,obs=obs,truth=truth.tolist(),oracle=oracle.tolist(),standard_noise=dict(range=zr.tolist(),motion=zm.tolist()),input_sha256=digest(obs))
    return dict(id=f"{q['id']}-s{seed}",input=u,initials=dict(I0=obs['start'],**initials(original,obs['start'])))

def validate_inputs(rows):
    original,axis,normal=reference_geometry();sharing={};maxerr=0.
    for rec in rows:
        u=rec['input'];o=u['obs'];q=u['condition'];assert digest(o)==u['input_sha256'];assert o['range_sigma']==CFG['range_sigma'] and o['motion_sigma']==CFG['motion_sigma'] and o['prior_sigma']==CFG['prior_sigma']
        expected=original+q['perturbation_m']*np.array(CFG['anchor_signs'])[:,None]*normal;assert np.array_equal(o['anchors'],expected)
        paired=dict(initials=rec['initials'],standard_noise=u['standard_noise'],truth=u['truth'],prior=o['prior_center'],motion=o['movement'],oracle=u['oracle'])
        if u['seed'] in sharing:assert paired==sharing[u['seed']],'Non-identical initialization/noise/controls across geometry'
        else:sharing[u['seed']]=paired
        truth=np.array(u['truth']);clean=[]
        for t in range(6):
            for car in range(2):
                for anchor in expected:clean.append(float(np.sqrt(sum((truth[t,car]-anchor)**2))))
            clean.append(float(np.linalg.norm(truth[t,1]-truth[t,0])))
        z=u['standard_noise'];er=np.array(o['ranges'])-clean-u['oracle']-o['range_sigma']*np.array(z['range']);em=np.array(o['movement'])-np.diff(truth.reshape(6,4),axis=0).ravel()-o['motion_sigma']*np.array(z['motion']);maxerr=max(maxerr,float(max(abs(er))),float(max(abs(em))));assert maxerr<1e-12
        survey=np.array(SOURCE['geometries']['weak']['survey']);start=np.vstack([survey,survey+np.cumsum(np.array(o['movement']).reshape(5,4),axis=0)]).ravel();assert np.array_equal(start,o['start']) and np.array_equal(truth[0].ravel(),o['prior_center']);assert rec['initials']==dict(I0=o['start'],**initials(original,o['start']))
        import inspect
        assert list(inspect.signature(initials).parameters)==['anchors','start']
    return dict(inputs_checked=len(rows),unique_noise_seeds=len(sharing),max_generation_identity_error=maxerr,paired_standard_noise='EXACT',paired_actual_initial_states='EXACT',paired_motion_prior_truth='EXACT',whitening='PASS',initialization_axis='UNPERTURBED_WEAK_ONLY',axis=axis.tolist(),normal=normal.tolist())

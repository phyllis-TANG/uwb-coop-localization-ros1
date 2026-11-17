"""Explicit Gaussian generation; only initialization consumes survey and observed motion."""
from common import *
CFG=read(DOC/'CONFIG.json')

def conditions():
    return [dict(id=f'n{i:02}',geometry=g,noise_scale=a,motion=CFG['motion'],kind=CFG['kind'],bias_m=CFG['bias_m'],prior_sigma=CFG['prior_sigma'],mechanism=CFG['prior_mechanism']) for i,(g,a) in enumerate((g,a) for g in CFG['geometries'] for a in CFG['noise_scales'])]

def generate(q,seed):
    geo=SOURCE['geometries'][q['geometry']];truth=np.tile(np.array(geo['initial_positions'],float),(6,1,1));anchors=np.array(geo['anchors'],float);a=q['noise_scale'];rs=a*CFG['range_sigma_base'];ms=a*CFG['motion_sigma_base']
    zr=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,0]))).normal(size=54);zm=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,1]))).normal(size=20)
    clean=np.column_stack([np.linalg.norm(truth[:,:,None,:]-anchors,axis=-1).reshape(6,8),np.linalg.norm(truth[:,1]-truth[:,0],axis=-1)]).ravel();oracle=np.zeros(54);oracle[8::9]=q['bias_m'];movement=np.diff(truth.reshape(6,4),axis=0).ravel()+ms*zm;survey=np.array(geo['survey']);start=np.vstack([survey,survey+np.cumsum(movement.reshape(5,4),axis=0)]).ravel()
    obs=dict(anchors=anchors.tolist(),ranges=(clean+oracle+rs*zr).tolist(),movement=movement.tolist(),prior_center=truth[0].ravel().tolist(),start=start.tolist(),kind=q['kind'],prior_sigma=q['prior_sigma'],range_sigma=rs,motion_sigma=ms)
    u=dict(condition=q,seed=seed,obs=obs,truth=truth.tolist(),oracle=oracle.tolist(),standard_noise=dict(range=zr.tolist(),motion=zm.tolist()),input_sha256=digest(obs));return dict(id=f"{q['id']}-s{seed}",input=u,initials=dict(I0=obs['start'],**initials(obs['anchors'],obs['start'])))

def validate_inputs(rows):
    sharing={};checks=0;maxerr=0.
    for rec in rows:
        u=rec['input'];o=u['obs'];q=u['condition'];a=q['noise_scale'];assert digest(o)==u['input_sha256'];assert o['range_sigma']==a*CFG['range_sigma_base'] and o['motion_sigma']==a*CFG['motion_sigma_base'] and o['prior_sigma']==.5
        key=u['seed'];z=u['standard_noise']
        if key in sharing:assert z==sharing[key]
        else:sharing[key]=z
        truth=np.array(u['truth']);anchors=np.array(o['anchors']);clean=[]
        for t in range(6):
            for car in range(2):
                for anchor in anchors:clean.append(float(np.sqrt(sum((truth[t,car]-anchor)**2))))
            clean.append(float(np.linalg.norm(truth[t,1]-truth[t,0])))
        er=np.array(o['ranges'])-clean-u['oracle']-o['range_sigma']*np.array(z['range']);em=np.array(o['movement'])-np.diff(truth.reshape(6,4),axis=0).ravel()-o['motion_sigma']*np.array(z['motion']);maxerr=max(maxerr,float(max(abs(er))),float(max(abs(em))));assert maxerr<1e-12
        survey=np.array(SOURCE['geometries'][q['geometry']]['survey']);expected=np.vstack([survey,survey+np.cumsum(np.array(o['movement']).reshape(5,4),axis=0)]).ravel();assert np.array_equal(expected,o['start']) and np.array_equal(truth[0].ravel(),o['prior_center'])
        assert rec['initials']==dict(I0=o['start'],**initials(o['anchors'],o['start']))
        # Initializer API explicitly excludes truth/center and shares no unit object.
        import inspect
        assert list(inspect.signature(initials).parameters)==['anchors','start'];checks+=1
    return dict(inputs_checked=checks,unique_noise_seeds=len(sharing),max_generation_identity_error=maxerr,paired_standard_noise='EXACT',whitening='PASS',initialization_no_truth_parameters='PASS')

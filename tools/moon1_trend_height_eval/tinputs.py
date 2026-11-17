"""Reference-aware generator; true ranges never use the perturbed heights."""
from tcommon import *
from tmodel import HEIGHT_MODE

def tracks():
 p=ROOT/'docs/research/moon1_bias_dynamics_eval/results/reference.json.gz'
 raw=subprocess.check_output(['git','show',BASE+':'+str(p.relative_to(ROOT))],cwd=ROOT);assert hashlib.sha256(raw).hexdigest()==filehash(p)
 ref=unpack(p);tt=[]
 for w in range(3):
  values=[v['track'] for v in ref.values() if v['window']==w];assert len(values)==40 and len({digest(t) for t in values})==1;tt.append(values[0])
 return tt,dict(mode='committed_PR120_reference_derived',fixed_commit=BASE,path=str(p.relative_to(ROOT)),sha256=filehash(p),tracks_sha256=[digest(t) for t in tt],same_window_records=40,NPZ_chain_reverified=False)

def make(track,cfg,condition,seed,height_sigma,noiseless=False):
 o,r=make_input(track,cfg,dict(id='normal',car2_motion_multiplier=1,peer_bias_m=0),seed,noiseless=noiseless)
 curve=np.array(condition['curve_m']);inj=np.zeros(54);inj[8::9]=curve;o['ranges_m']=(np.array(o['ranges_m'])+inj).tolist()
 eh=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,track['window'],3]))).normal(size=2)
 errors=height_sigma*eh;trueh=np.array(o['heights_m']);o['heights_m']=(trueh+errors[None,:]).tolist();o['height_mode']=HEIGHT_MODE
 r.update(condition=condition,injection_m=inj.tolist(),height_sigma_m=height_sigma,height_standard=eh.tolist(),height_errors_m=errors.tolist(),true_heights_m=trueh.tolist())
 return o,r

def verify(o,r):
 x=np.array(r['track']['antenna_xyz_m']);cleanrange=[]
 for t in range(6):
  for c in range(2):
   for a in o['anchors_xyz_m']:cleanrange.append(float(np.linalg.norm(x[t,c]-a)))
  cleanrange.append(float(np.linalg.norm(x[t,1]-x[t,0])))
 inj=np.zeros(54);inj[8::9]=r['condition']['curve_m'];np.testing.assert_array_equal(inj,r['injection_m'])
 np.testing.assert_allclose(o['ranges_m'],np.array(cleanrange)+.04*np.array(r['standard_noise']['range'])+inj,atol=1e-12,rtol=0)
 np.testing.assert_allclose(o['global_xy_increments_m'],np.diff(x[:,:,:2],axis=0)+.02*np.array(r['standard_noise']['motion']),atol=1e-12,rtol=0)
 np.testing.assert_allclose(o['prior_center_xy_m'],x[0,:,:2]+.5*np.array(r['standard_noise']['prior']),atol=1e-12,rtol=0)
 eh=np.random.Generator(np.random.PCG64(np.random.SeedSequence([r['seed'],r['window'],3]))).normal(size=2)
 np.testing.assert_array_equal(eh,r['height_standard']);np.testing.assert_array_equal(eh*r['height_sigma_m'],r['height_errors_m'])
 np.testing.assert_array_equal(x[:,:,2],r['true_heights_m']);np.testing.assert_array_equal(x[:,:,2]+np.array(r['height_errors_m'])[None,:],o['heights_m'])
 assert o['motion_sigmas_m']==[.02,.02] and o['range_sigma_m']==.04 and o['prior_sigma_m']==.5
 assert o['times_s']==r['track']['times_s'];np.testing.assert_allclose(o['times_s'],np.array([0,8,16])[r['window']]+np.arange(6)*.2,atol=1e-14,rtol=0)
 assert r['track']['display_antenna_xyz_m']==r['track']['antenna_xyz_m']
 return True

def plan(seeds):
 rows=[]
 for w in range(3):
  for seed in seeds:
   for h,conditions in [(0.,['normal','constant03','step03','ramp03']),(.05,['normal','ramp03']),(.15,['normal','ramp03'])]:
    for condition in conditions:rows.append(dict(id=f'u{len(rows):04}',window=w,seed=seed,height_sigma_m=h,condition=condition,part='A' if h==0 else 'B'))
 index={(r['window'],r['seed'],r['condition']):r['id'] for r in rows if r['height_sigma_m']==0}
 for r in rows:r['sigma0_unit']=index[(r['window'],r['seed'],r['condition'])]
 return rows

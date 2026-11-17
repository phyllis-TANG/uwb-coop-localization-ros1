"""Reference-aware input generation, separated from estimator."""
from bridge import *
from generate import make_input

def tracks():
 path=OLD/'results/reference.json.gz';base='27b0ecf4d76124d54912d26d33432e1718dca494'
 historical=subprocess.check_output(['git','show',base+':'+str(path.relative_to(ROOT))],cwd=ROOT)
 assert hashlib.sha256(historical).hexdigest()==filehash(path)
 ref=unpack(path);result=[]
 for w in range(3):
  matches=[v['track'] for v in ref.values() if v['window']==w]
  assert len(matches)==20 and len({digest(t) for t in matches})==1
  assert np.allclose(matches[0]['times_s'],np.array([0,8,16])[w]+np.arange(6)*.2,atol=1e-14,rtol=0)
  result.append(matches[0])
 return result,dict(mode='committed_reference_derived_not_NPZ_reverified',commit=base,path=str(path.relative_to(ROOT)),sha256=filehash(path),records=60,per_window_records=20,track_sha256=[digest(t) for t in result],inherited_npz_receipt=read(OLD/'results/FREEZE.json')['asset'])

def make(track,cfg,condition,seed,noiseless=False):
 obs,ref=make_input(track,cfg,dict(id='normal',car2_motion_multiplier=1,peer_bias_m=0),seed,noiseless=noiseless)
 injection=np.zeros(54);injection[8::9]=condition['peer_curve_m']
 obs['ranges_m']=(np.array(obs['ranges_m'])+injection).tolist()
 ref.update(condition=condition,injection_m=injection.tolist(),injection_mean_m=float(np.mean(condition['peer_curve_m'])),mean_note='descriptive curve mean only, not a true constant parameter')
 return obs,ref

def verify(o,ref):
 x=np.array(ref['track']['antenna_xyz_m']);ranges=[]
 for t in range(6):
  for c in range(2):
   for a in o['anchors_xyz_m']:ranges.append(float(np.linalg.norm(x[t,c]-a)))
  ranges.append(float(np.linalg.norm(x[t,1]-x[t,0])))
 inj=np.zeros(54);inj[8::9]=ref['condition']['peer_curve_m'];np.testing.assert_array_equal(inj,ref['injection_m'])
 np.testing.assert_allclose(o['ranges_m'],np.array(ranges)+o['range_sigma_m']*np.array(ref['standard_noise']['range'])+inj,atol=1e-12,rtol=0)
 np.testing.assert_allclose(o['global_xy_increments_m'],np.diff(x[:,:,:2],axis=0)+np.array(ref['standard_noise']['motion'])*.02,atol=1e-12,rtol=0)
 np.testing.assert_allclose(o['prior_center_xy_m'],x[0,:,:2]+np.array(ref['standard_noise']['prior'])*.5,atol=1e-12,rtol=0)
 assert o['heights_m']==x[:,:,2].tolist();assert o['motion_sigmas_m']==[.02,.02]
 assert o['times_s']==ref['track']['times_s']
 assert ref['track']['display_antenna_xyz_m']==ref['track']['antenna_xyz_m']
 np.testing.assert_allclose(x,np.array(ref['track']['body_xyz_m'])+[0,0,1.16],atol=1e-12,rtol=0)
 return True

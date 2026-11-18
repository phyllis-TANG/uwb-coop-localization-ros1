"""Post-freeze source-supported portable evidence, no optimizer invocation."""
import csv,json,shutil,tarfile
import numpy as np
from scipy.spatial.transform import Rotation
from coverage import DOC,ART,ROOT,write,sha

def main():
 sources=json.loads((DOC/'CONTINUOUS_SOURCES.json').read_text());rows=list(csv.reader(open(sources[0]['path'])))[1:];ns=np.array([int(r[0]) for r in rows],dtype=np.int64);gt=np.array([[float(v) for v in r[1:8]] for r in rows]);R=Rotation.from_quat(gt[:,[4,5,6,3]]).as_matrix();C=np.diag([1,-1,-1]);d=np.load(DOC/'terrain.npz');low=d['low']-1.6;high=d['low']+(np.asarray(d['terrain'].shape)-1)*.4+1.6;cloud=[];ids=[]
 for j,s in enumerate(sources[1:]):
  p=__import__('pathlib').Path(s['path']);assert sha(p)==s['sha256'];points=np.loadtxt(p,delimiter=',')[:,:3];i=np.argmin(abs(ns-int(p.stem)));w=((points+[1,0,-1.5])@R[i].T+gt[i,:3])@C;keep=np.isfinite(w).all(1)&(abs(w[:,2])<2)&(w[:,:2]>=low).all(1)&(w[:,:2]<=high).all(1);cloud.append(w[keep]);ids.append(np.full(keep.sum(),j,dtype=np.int16))
 np.savez_compressed(DOC/'CLOUD_SUPPORT.npz',world_xyz_m=np.concatenate(cloud),source_frame_index=np.concatenate(ids));write(DOC/'CLOUD_SUPPORT.json',dict(points=sum(len(x) for x in cloud),source_frame_manifest='CONTINUOUS_SOURCES.json entries[1:]',crop_min_xy=low.tolist(),crop_max_xy=high.tolist(),filter='finite, abs(world_z)<2m; exact float64 transformed points',sha256=sha(DOC/'CLOUD_SUPPORT.npz')))
 out=ART/'portable';out.mkdir(exist_ok=False);shutil.copytree(ART/'runs',out/'runs')
 for name in ['INPUTS.json.gz','ROUTE.json','PROTOCOL.json','FREEZE.json','terrain.npz','continuous_route.usda','CLOUD_SUPPORT.npz','CLOUD_SUPPORT.json','CONTINUOUS_SOURCES.json','CPU_REPLAY.csv','CPU_REPLAY.json']:
  shutil.copyfile(DOC/name,out/name)
 for path,h in json.loads((DOC/'FREEZE.json').read_text())['files'].items():
  p=ROOT/path;assert sha(p)==h;dest=out/'frozen_source'/path;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
 for s in json.loads((DOC/'SUPPLEMENT_RECEIPT.json').read_text())['files']:
  p=__import__('pathlib').Path(s['path']);dest=out/'supplement'/p.name;dest.parent.mkdir(exist_ok=True);shutil.copyfile(p,dest)
 files={str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()};archive=DOC/'EVIDENCE.tar.gz'
 with tarfile.open(archive,'w:gz') as tar:
  for name in files:tar.add(out/name,arcname=name,recursive=False)
 write(DOC/'EVIDENCE_MANIFEST.json',dict(archive=archive.name,archive_sha256=sha(archive),archive_bytes=archive.stat().st_size,files=files,run_freeze_sha='4d9003de7a9320d25374948f9093557b3364c3a3',new_method_runs=150,main_runs=120,optional_new_runs=30,optional_reused_runs=10))
 print(json.dumps(dict(files=len(files),archive_bytes=archive.stat().st_size,cloud_points=sum(len(x) for x in cloud))))
if __name__=='__main__':main()

"""Independent post-freeze scene pose/source checks; no scene edits or optimization."""
import csv,json
from pathlib import Path
import numpy as np
from pxr import Usd,UsdGeom,Gf
from coverage import DOC,write,sha
r=json.loads((DOC/'ROUTE.json').read_text());stage=Usd.Stage.Open(str(DOC/'continuous_route.usda'));yaw=np.asarray(r['dense_yaw_rad']);times=np.asarray(r['dense_times_s']);maxerr=0
for i,t in enumerate(times):
 assert abs(t-i/50)<1e-12
 cache=UsdGeom.XformCache(Usd.TimeCode(float(i)))
 for c in range(2):
  m=cache.GetLocalToWorldTransform(stage.GetPrimAtPath(f'/World/Car{c+1}'));x=np.asarray(m.TransformDir(Gf.Vec3d(1,0,0)));z=np.asarray(m.TransformDir(Gf.Vec3d(0,0,1)));ex=[np.cos(yaw[i,c]),np.sin(yaw[i,c]),0];err=float(np.max(abs(x-ex)));assert err<1e-12;np.testing.assert_allclose(z,[0,0,1],atol=1e-12);maxerr=max(maxerr,err)
  dims=stage.GetPrimAtPath(f'/World/Car{c+1}/Body').GetAttribute('xformOp:scale').Get();np.testing.assert_allclose(dims,r['body_dimensions_m'],atol=1e-7)
sources=json.loads((DOC/'CONTINUOUS_SOURCES.json').read_text())
for s in sources:assert sha(Path(s['path']))==s['sha256']
rows=list(csv.reader(open(sources[0]['path'])))[1:];ns=np.array([int(x[0]) for x in rows],dtype=np.int64);offsets=[]
for s in sources[1:]:
 n=int(Path(s['path']).stem);offsets.append(float(np.min(abs(ns-n))*1e-9))
C=np.diag([1.,-1.,-1.]);np.testing.assert_array_equal(C.T@C,np.eye(3));assert np.linalg.det(C)==1
coverage=list(csv.DictReader((DOC/'DENSE_COVERAGE.csv').open()));selected=[x for x in coverage if x['candidate']=='5-14' and r['source_times_car2_s'][0]<=float(x['time_s'])<=r['source_times_car2_s'][1]];assert len(selected)==444 and all(x['passed']=='True' for x in selected)
write(DOC/'SCENE_FINAL_CHECK.json',dict(status='PASS',pose_checks=444,max_rotation_axis_error=maxerr,source_hashes_verified=len(sources),max_frame_to_gt_offset_s=max(offsets),selected_coverage_rows=len(selected),body_pose='upright yaw-only proxy verified, not original 6DOF attitude',optimizer_calls=0))
print((DOC/'SCENE_FINAL_CHECK.json').read_text())

"""Isaac 6.2 kinematic replay entry; GPU path explicitly untested on blocked host."""
import argparse,json,subprocess,importlib.metadata,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--scene',type=Path,required=True);p.add_argument('--route',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
import torch
probe=subprocess.run(['nvidia-smi'],capture_output=True,text=True)
versions={k:importlib.metadata.version(k) for k in ['isaacsim','isaaclab','torch']}
status=dict(versions=versions,cuda_available=torch.cuda.is_available(),device_count=torch.cuda.device_count(),nvidia_smi_returncode=probe.returncode,isaac_executed=False,rendered=False,dynamics_executed=False)
(a.out/'driver.log').write_text(probe.stdout+probe.stderr)
if not status['cuda_available'] or probe.returncode:
 status.update(state='BLOCKED_GPU_UNAVAILABLE',reason='No usable CUDA GPU/driver; no SimulationApp launch attempted. CPU replay continues independently.');(a.out/'STATUS.json').write_text(json.dumps(status,indent=2)+'\n');print(json.dumps(status));raise SystemExit(2)
from isaacsim import SimulationApp
app=SimulationApp({'headless':True,'width':960,'height':540})
try:
 import omni.usd,omni.timeline,omni.replicator.core as rep
 from pxr import Usd,UsdGeom
 import numpy as np
 from PIL import Image
 ctx=omni.usd.get_context();ctx.open_stage(str(a.scene.resolve()))
 for _ in range(60):app.update()
 stage=ctx.get_stage();assert stage and UsdGeom.GetStageUpAxis(stage)=='Z' and UsdGeom.GetStageMetersPerUnit(stage)==1
 route=json.loads(a.route.read_text());q=np.asarray(route['dense_xyz_m']);fps=stage.GetTimeCodesPerSecond();tl=omni.timeline.get_timeline_interface();rp=rep.create.render_product('/World/Camera',(960,540));rgb=rep.AnnotatorRegistry.get_annotator('rgb');rgb.attach([rp]);rows=[]
 for i in np.linspace(0,len(q)-1,5).astype(int):
  tl.set_current_time(float(i/fps));tl.play();app.update();tl.pause();rep.orchestrator.step(delta_time=0.0,rt_subframes=4);actual=tl.get_current_time();tc=actual*fps
  cache=UsdGeom.XformCache(Usd.TimeCode(tc));got=np.array([cache.GetLocalToWorldTransform(stage.GetPrimAtPath(f'/World/Car{c+1}/Antenna')).ExtractTranslation() for c in range(2)]);expected=np.array([[np.interp(tc,np.arange(len(q)),q[:,c,k]) for k in range(3)] for c in range(2)]);error=float(np.max(abs(got-expected)));assert error<1e-6
  pixels=rgb.get_data();assert pixels.size>0;Image.fromarray(pixels).save(a.out/f'isaac_{i:03d}.png');rows.append(dict(requested_time_s=float(i/fps),actual_time_s=actual,antenna_xyz_m=got.tolist(),peer_distance_m=float(np.linalg.norm(got[1]-got[0])),cpu_max_difference_m=error))
 status.update(state='PASS',isaac_executed=True,rendered=True,checks=rows)
finally:
 (a.out/'STATUS.json').write_text(json.dumps(status,indent=2)+'\n');app.close()

"""CPU USD time-sample replay, independently composed world antenna transforms."""
import json,time,subprocess,sys,importlib.metadata
import numpy as np
from pxr import Usd,UsdGeom,UsdLux,Gf
from coverage import DOC,write,csvwrite

def export():
 r=json.loads((DOC/'ROUTE.json').read_text());d=np.load(DOC/'terrain.npz');q=np.array(r['dense_xyz_m']);yaw=np.array(r['dense_yaw_rad']);stage=Usd.Stage.CreateNew(str(DOC/'continuous_route.usda'));stage.SetStartTimeCode(0);stage.SetEndTimeCode(len(q)-1);stage.SetTimeCodesPerSecond(50);stage.SetFramesPerSecond(50);UsdGeom.SetStageUpAxis(stage,'Z');UsdGeom.SetStageMetersPerUnit(stage,1.)
 world=UsdGeom.Xform.Define(stage,'/World');stage.SetDefaultPrim(world.GetPrim());world.GetPrim().SetCustomDataByKey('identity','Moon_1 time-offset pair, procedural upright bodies; kinematic only')
 g=d['terrain'];ny=g.shape[1];pts=[[d['low'][0]+i*.4,d['low'][1]+j*.4,g[i,j]] for i in range(g.shape[0]) for j in range(ny)];faces=[]
 for i in range(g.shape[0]-1):
  for j in range(ny-1):k=i*ny+j;faces.extend([k,k+ny,k+ny+1,k+1])
 mesh=UsdGeom.Mesh.Define(stage,'/World/Terrain');mesh.CreatePointsAttr(pts);mesh.CreateFaceVertexCountsAttr([4]*(len(faces)//4));mesh.CreateFaceVertexIndicesAttr(faces);mesh.CreateSubdivisionSchemeAttr('none');mesh.CreateDisplayColorPrimvar(UsdGeom.Tokens.vertex).Set([(.48,.48,.48) if v else (.72,.25,.2) for v in d['observed'].ravel()]);mesh.GetPrim().SetCustomDataByKey('red_vertices','filled/unobserved; not independently supported')
 for c in range(2):
  parent=UsdGeom.Xform.Define(stage,f'/World/Car{c+1}');pos=parent.AddTranslateOp();rot=parent.AddOrientOp(UsdGeom.XformOp.PrecisionDouble)
  body=UsdGeom.Cube.Define(stage,f'/World/Car{c+1}/Body');body.CreateSizeAttr(1);body.AddScaleOp().Set(Gf.Vec3f(.8,.6,.4));body.CreateDisplayColorAttr([(0,.45,1) if c==0 else (1,.4,0)])
  ant=UsdGeom.Sphere.Define(stage,f'/World/Car{c+1}/Antenna');ant.CreateRadiusAttr(.065);ant.AddTranslateOp().Set(Gf.Vec3d(0,0,.96));ant.CreateDisplayColorAttr([(1,1,0)])
  mast=UsdGeom.Cylinder.Define(stage,f'/World/Car{c+1}/Mast');mast.CreateRadiusAttr(.018);mast.CreateHeightAttr(.96);mast.AddTranslateOp().Set(Gf.Vec3d(0,0,.48))
  for i in range(len(q)):
   pos.Set(Gf.Vec3d(*(q[i,c]-[0,0,.96])),i);rot.Set(Gf.Quatd(np.cos(yaw[i,c]/2),Gf.Vec3d(0,0,np.sin(yaw[i,c]/2))),i)
  curve=UsdGeom.BasisCurves.Define(stage,f'/World/Track{c+1}');curve.CreateTypeAttr('linear');curve.CreateCurveVertexCountsAttr([len(q)]);curve.CreatePointsAttr(q[:,c].tolist());curve.CreateWidthsAttr([.025]);curve.CreateDisplayColorAttr([(0,.6,1) if c==0 else (1,.3,0)])
 for i,a in enumerate(r['anchors_xyz_m']):
  p=UsdGeom.Sphere.Define(stage,f'/World/Anchor{i}');p.CreateRadiusAttr(.12);p.AddTranslateOp().Set(Gf.Vec3d(*a));p.CreateDisplayColorAttr([(1,.8,0)])
 peer=UsdGeom.BasisCurves.Define(stage,'/World/Peer');peer.CreateTypeAttr('linear');peer.CreateCurveVertexCountsAttr([2]);p=peer.CreatePointsAttr();peer.CreateWidthsAttr([.02]);peer.CreateDisplayColorAttr([(.7,.1,.8)])
 for i in range(len(q)):p.Set(q[i].tolist(),i)
 UsdLux.DomeLight.Define(stage,'/World/Light').CreateIntensityAttr(800)
 mid=q.mean((0,1));cam=UsdGeom.Camera.Define(stage,'/World/Camera');eye=mid+[4,-17,16];mat=Gf.Matrix4d().SetLookAt(Gf.Vec3d(*eye),Gf.Vec3d(*mid),Gf.Vec3d(0,0,1)).GetInverse();cam.AddTransformOp().Set(mat);cam.CreateClippingRangeAttr(Gf.Vec2f(.1,1000));stage.GetRootLayer().Save()

def cpu():
 start=time.monotonic();r=json.loads((DOC/'ROUTE.json').read_text());expected=np.array(r['dense_xyz_m']);stage=Usd.Stage.Open(str(DOC/'continuous_route.usda'));assert stage and UsdGeom.GetStageUpAxis(stage)=='Z' and UsdGeom.GetStageMetersPerUnit(stage)==1 and stage.GetTimeCodesPerSecond()==50
 assert stage.GetEndTimeCode()==len(expected)-1 and stage.GetStartTimeCode()==0
 out=[];sampled=[];maxerr=maxdist=0
 for tc in np.arange(0,len(expected)-.5,.5):
  cache=UsdGeom.XformCache(Usd.TimeCode(float(tc)));got=np.array([cache.GetLocalToWorldTransform(stage.GetPrimAtPath(f'/World/Car{c+1}/Antenna')).ExtractTranslation() for c in range(2)]);ex=np.array([[np.interp(tc,np.arange(len(expected)),expected[:,c,k]) for k in range(3)] for c in range(2)]);err=float(np.max(abs(got-ex)));dist=float(np.linalg.norm(got[1]-got[0]));de=abs(dist-np.linalg.norm(ex[1]-ex[0]));assert err<1e-10 and de<1e-10
  for c in range(2):
   body=np.array(cache.GetLocalToWorldTransform(stage.GetPrimAtPath(f'/World/Car{c+1}')).ExtractTranslation());np.testing.assert_allclose(got[c]-body,[0,0,.96],atol=1e-10)
  maxerr=max(maxerr,err);maxdist=max(maxdist,de);out.append(dict(time_code=float(tc),relative_time_s=float(tc/50),car1_x=got[0,0],car1_y=got[0,1],car1_z=got[0,2],car2_x=got[1,0],car2_y=got[1,1],car2_z=got[1,2],peer_distance_m=dist,position_max_error_m=err,distance_error_m=de))
  if tc.is_integer():sampled.append(got)
 for i,a in enumerate(r['anchors_xyz_m']):np.testing.assert_allclose(UsdGeom.XformCache().GetLocalToWorldTransform(stage.GetPrimAtPath(f'/World/Anchor{i}')).ExtractTranslation(),a,atol=1e-10)
 csvwrite(DOC/'CPU_REPLAY.csv',out);write(DOC/'CPU_REPLAY.json',dict(status='PASS',actual_cpu_usd_replay=True,queries=len(out),dense_keyframes=len(expected),max_position_error_m=maxerr,max_peer_distance_error_m=maxdist,seconds=time.monotonic()-start,usd_version=Usd.GetVersion(),mode='USD composed transforms at authored and half-frame time codes; not Isaac rendering or physical simulation'))
 # CPU-only replay visualization from reopened USD positions, not reference estimates.
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 from matplotlib.animation import FuncAnimation,PillowWriter
 d=np.load(DOC/'terrain.npz');g=d['terrain'];x=d['low'][0]+np.arange(g.shape[0])*.4;y=d['low'][1]+np.arange(g.shape[1])*.4;X,Y=np.meshgrid(x,y,indexing='ij');fig=plt.figure(figsize=(9,5));ax=fig.add_subplot(111,projection='3d');ax.plot_surface(X,Y,g,cmap='terrain',alpha=.55,linewidth=0);a=np.array(r['anchors_xyz_m']);ax.scatter(a[:,0],a[:,1],a[:,2],marker='^',color='gold');q=np.array(sampled)
 for c in range(2):ax.plot(q[:,c,0],q[:,c,1],q[:,c,2],alpha=.3)
 dots=[ax.plot([],[],[],'o',markersize=7,color=color)[0] for color in ['blue','orange']];line=ax.plot([],[],[],color='purple')[0];ax.set(xlabel='x [m]',ylabel='y [m]',zlabel='z [m]',zlim=(-.5,2));ax.set_box_aspect([3,1,.6]);frames=list(range(0,len(q),5))+[len(q)-1]
 def update(i):
  for c,dot in enumerate(dots):dot.set_data([q[i,c,0]],[q[i,c,1]]);dot.set_3d_properties([q[i,c,2]])
  line.set_data(q[i,:,0],q[i,:,1]);line.set_3d_properties(q[i,:,2]);ax.set_title(f'CPU USD replay (not Isaac) | t={i/50:.2f}s | peer={np.linalg.norm(q[i,1]-q[i,0]):.3f}m');return dots+[line]
 for i in np.linspace(0,len(q)-1,5).astype(int):update(i);fig.savefig(DOC/f'cpu_keyframe_{i:03d}.png',dpi=110)
 FuncAnimation(fig,update,frames=frames,interval=100).save(DOC/'cpu_replay.gif',writer=PillowWriter(fps=10));plt.close(fig)
 print(json.dumps(json.loads((DOC/'CPU_REPLAY.json').read_text())))
if __name__=='__main__':
 if '--check-only' not in sys.argv:export()
 cpu()

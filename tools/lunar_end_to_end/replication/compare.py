"""Read saved endpoints and produce paired tables and vector figures."""
from run import *
import csv,itertools
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from pxr import Usd,UsdGeom,Gf
def rows(p):return list(csv.DictReader(p.open()))
def save(name,data):coverage.csvwrite(D/(name+'.csv'),data)
conds=['normal','ramp_only','motion_only','both']
data={}
for r in rows(OLD/'FULL_RESULTS.csv'):
    if r['condition'] in conds and r['method'] in ['M0','M2','M3']:
        data['main',r['condition'],int(r['seed']),int(r['car']),r['method']]=(float(r['rmse_m']),float(r['peak_m']),r['state'],float(r['shared_peer_slope_m_s'] or 0))
inputs={x['observation']['id']:x for x in json.loads(gzip.decompress((D/'INPUTS.json.gz').read_bytes()))}
for z in json.loads(gzip.decompress((D/'ENDPOINTS.json.gz').read_bytes())):
    inp=inputs[z['task']['id']]
    audit(inp['observation'],z)
    m=metrics(inp['observation'],inp['reference'],z['x'],z['method'])
    assert m==z['metrics']
    for c in [1,2]:
        data['second',inp['reference']['condition'],inp['reference']['seed'],c,z['method']]=(m['rmse_m'][c-1],m['peak_m'][c-1],z['state'],m['bias_slope_m_s'] or 0)
seeds=range(2026111801,2026111811)
pairs=[]; summary=[]; trends=[]
for segment,cond,c in itertools.product(['main','second'],conds,[1,2]):
    for base,method in [('M2','M3'),('M0','M2'),('M0','M3')]:
        group=[]
        for seed in seeds:
            a,b=[data[segment,cond,seed,c,k] for k in (base,method)]
            group.append(dict(segment=segment,condition=cond,car=c,seed=seed,baseline=base,method=method,base_rmse=a[0],method_rmse=b[0],gain_m=a[0]-b[0],base_peak=a[1],method_peak=b[1],peak_gain_m=a[1]-b[1],baseline_state=a[2],method_state=b[2]))
        pairs.extend(group)
        for subset in ['all_finite','both_accepted']:
            rr=[r for r in group if subset=='all_finite' or r['baseline_state']==r['method_state']=='ACCEPTED']
            summary.append(dict(segment=segment,condition=cond,car=c,baseline=base,method=method,subset=subset,n=len(rr),planned=10,improved=sum(r['gain_m']>0 for r in rr),mean_gain_mm=1000*np.mean([r['gain_m'] for r in rr]),mean_base_rmse_m=np.mean([r['base_rmse'] for r in rr]),mean_method_rmse_m=np.mean([r['method_rmse'] for r in rr]),worst_base_peak_m=max(r['base_peak'] for r in rr),worst_method_peak_m=max(r['method_peak'] for r in rr),mean_peak_gain_m=np.mean([r['peak_gain_m'] for r in rr])))
    if c==1 and cond in ('normal','motion_only'):
        for seed in seeds:
            b=data[segment,cond,seed,c,'M3'][3];trends.append(dict(segment=segment,condition=cond,seed=seed,true_slope=0,estimated_m_s=b,motion_shift_m_s=b-data[segment,'normal',seed,c,'M3'][3]))
save('PAIRS',pairs);save('SUMMARY',summary);save('ZERO_BIAS',trends)
fig,axs=plt.subplots(2,2,figsize=(9,5.8),sharey=True,constrained_layout=True)
for i,segment in enumerate(['main','second']):
    for j,c in enumerate([1,2]):
        ax=axs[i,j];ax.axhline(0,color='.4',lw=.9)
        for k,cond in enumerate(conds):
            rr=[r for r in pairs if (r['segment'],r['condition'],r['car'],r['baseline'],r['method'])==(segment,cond,c,'M2','M3')]
            v=np.array([r['gain_m']*1000 for r in rr])
            for l,r in enumerate(rr):
                ok=r['baseline_state']==r['method_state']=='ACCEPTED'
                ax.scatter(k+(l-4.5)*.05,v[l],color='#146b82' if ok else '#ce4927',marker='o' if ok else 'x',s=18)
            ax.plot([k-.25,k+.25],[v.mean()]*2,color='black')
        ax.set_xticks(range(4),['Normal','Ramp','Motion','Both']);ax.set_title(f'{segment.capitalize()} segment · Car {c}')
        if j==0:ax.set_ylabel('RMSE(M2) − RMSE(M3) [mm]')
fig.savefig(D/'paired.pdf');fig.savefig(D/'paired.png',dpi=220);plt.close(fig)
fig,axs=plt.subplots(1,2,figsize=(11,4.3),constrained_layout=True);geom=[];plotrows=[];gridrows=[]
for ax,seg,path in zip(axs,['main','second'],[OLD,D]):
    route=load(path/'ROUTE.json');q=np.array(route['dense_xyz_m']);anchors=np.array(route['anchors_xyz_m']);g=np.load(path/'terrain.npz');low=g['low'];mask=g['observed'];xy=np.indices(mask.shape).transpose(1,2,0)*.4+low
    for (i,j),v in np.ndenumerate(mask):gridrows.append(dict(segment=seg,x=xy[i,j,0],y=xy[i,j,1],observed=int(v),height=g['terrain'][i,j]))
    ax.pcolormesh(xy[:,:,0],xy[:,:,1],mask,cmap=ListedColormap(['#f1c4a4','#ccd9cc']),shading='nearest',vmin=0,vmax=1)
    for j,p in enumerate(anchors):ax.scatter(*p[:2],marker='^',color='black',label='Designed anchors' if j==0 else None);ax.annotate(str(j),p[:2],xytext=(4,2),textcoords='offset points')
    for c in range(2):
        tr=q[:,c];delta=tr[-1,:2]-tr[0,:2];dist=np.linalg.norm(q[:,0]-q[:,1],axis=1)
        ax.plot(*tr[:,:2].T,color=['#165a8b','#b24723'][c],label=f'Car {c+1}');ax.annotate('',xy=tr[-1,:2],xytext=tr[-30,:2],arrowprops=dict(arrowstyle='->',color=['#165a8b','#b24723'][c]))
        for i,p in enumerate(tr):plotrows.append(dict(segment=seg,car=c+1,relative_s=route['dense_times_s'][i],x=p[0],y=p[1],z=p[2]))
        for j,p in enumerate(anchors):
            rel=p[:2]-tr[0,:2];geom.append(dict(segment=seg,car=c+1,anchor=j,anchor_x=p[0],anchor_y=p[1],anchor_z=p[2],start_bearing_deg=np.degrees(np.arctan2(rel[1],rel[0])),net_direction_deg=np.degrees(np.arctan2(delta[1],delta[0])),peer_min_m=dist.min(),peer_max_m=dist.max()))
    ax.set(aspect='equal',title=f'{seg.capitalize()} · {route["source_times_car2_s"][0]:.2f}–{route["source_times_car2_s"][1]:.2f} s',xlabel='moon_map x [m]',ylabel='y [m]');ax.legend(fontsize=8)
fig.savefig(D/'routes.pdf');fig.savefig(D/'routes.png',dpi=220);save('GEOMETRY',geom);save('FIGURE_TRACKS',plotrows);save('FIGURE_GRID',gridrows)
stage=Usd.Stage.Open(str(D/'continuous_route.usda'));route=load(D/'ROUTE.json');err=0
for i,yy in enumerate(route['dense_yaw_rad']):
    for c,y in enumerate(yy):
        mat=UsdGeom.XformCache(i).GetLocalToWorldTransform(stage.GetPrimAtPath(f'/World/Car{c+1}'))
        np.testing.assert_allclose(mat.ExtractTranslation(),np.asarray(route['dense_xyz_m'][i][c])-[0,0,.96],atol=1e-10,rtol=0)
        err=max(err,np.max(abs(np.asarray(mat.TransformDir(Gf.Vec3d(1,0,0)))-[np.cos(y),np.sin(y),0])))
assert err<1e-10
print('pose checks',2*(i+1),'max axis error',err)

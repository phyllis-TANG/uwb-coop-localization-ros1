"""Post-freeze visualization of actual supporting point crop and selected route."""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from coverage import DOC
r=json.loads((DOC/'ROUTE.json').read_text());q=np.asarray(r['dense_xyz_m']);t=np.asarray(r['dense_times_s'])+r['source_times_car2_s'][0];p=np.load(DOC/'CLOUD_SUPPORT.npz')['world_xyz_m'];d=np.load(DOC/'terrain.npz');fig,axs=plt.subplots(2,1,figsize=(12,7),constrained_layout=True)
ax=axs[0];cloud=ax.scatter(p[::3,0],p[::3,1],c=p[::3,2],s=.8,cmap='terrain',vmin=-.3,vmax=.1,alpha=.5);fig.colorbar(cloud,ax=ax,label='observed point height [m]');ix=np.argwhere(~d['observed']);ax.scatter(d['low'][0]+ix[:,0]*.4,d['low'][1]+ix[:,1]*.4,marker='s',s=14,color='red',alpha=.25,label='unobserved grid nodes')
for c,color in [(0,'blue'),(1,'orange')]:
 ax.plot(q[:,c,0],q[:,c,1],color=color,lw=2,label=f'Car{c+1}: source t+{5 if c==0 else 0}s');ax.scatter(q[[0,-1],c,0],q[[0,-1],c,1],color=color,s=35)
 axs[1].plot(t,q[:,c,2]-1.16,color=color,label=f'Car{c+1} ground height')
ax.set(xlim=(q[:,:,0].min()-1,q[:,:,0].max()+1),ylim=(q[:,:,1].min()-1,q[:,:,1].max()+1),xlabel='moon_map x [m]',ylabel='y [m]',title='Selected supported route 5.44–9.86 s; actual 12-frame point crop');ax.legend(loc='upper right',fontsize=8);ax.set_aspect('equal');axs[1].set(xlabel='Car2 source time [s]',ylabel='terrain height [m]',title='Continuous grid heights along retained route (not wheel-contact simulation)');axs[1].legend();fig.savefig(DOC/'selected_route.png',dpi=150);plt.close(fig)

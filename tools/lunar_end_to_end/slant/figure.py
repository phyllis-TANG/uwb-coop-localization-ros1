"""Compare certified projection contours, showing all twelve shared inputs."""
import gzip,json
import matplotlib.pyplot as plt
from fractions import Fraction as F
from matplotlib.collections import PatchCollection
from matplotlib.patches import Rectangle,Patch
from freeze_inputs import DOC
fig,axes=plt.subplots(4,6,figsize=(15,9),constrained_layout=True)
for i,meta in enumerate(json.loads((DOC/'INPUT_MANIFEST.json').read_text())['records']):
    key=meta['case']
    for car in range(2):
        ax=axes[(i%2)*2+car,i//2]
        for method,color in [('N4','#1774aa'),('P4','#e48020')]:
            path=DOC/'results'/f'{key}_{method}'/'certificate.json.gz'
            if not path.exists():continue
            data=json.loads(gzip.decompress(path.read_bytes()))
            rects={tuple(sum(r['box'],[])) for r in data['projections']['ps'[car]]['rectangles']}
            patches=[]
            for rect in rects:
                a,b,c,d=map(lambda s:float(F(s)),rect)
                patches.append(Rectangle((a,c),b-a,d-c))
            ax.add_collection(PatchCollection(patches,facecolor=color,alpha=.44,edgecolor='none'))
        pos=json.loads((DOC/'evaluation'/f'{key}.json').read_text())['xyz'][car]
        ax.plot(*[float(F(v)) for v in pos[:2]],'k+',ms=7)
        ax.set_aspect('equal');ax.autoscale_view();ax.tick_params(labelsize=6)
        if i%2==0 and car==0:ax.set_title(key.rsplit('_',1)[0])
        if i//2==0:ax.set_ylabel(('Normal' if i%2==0 else 'Ramp')+f' · Car {car+1}\ny [m]')
fig.legend(handles=[Patch(color='#1774aa',label='N4'),Patch(color='#e48020',label='P4')],loc='outside lower center',ncol=2)
fig.savefig(DOC/'regions.pdf');fig.savefig(DOC/'regions.png',dpi=160)

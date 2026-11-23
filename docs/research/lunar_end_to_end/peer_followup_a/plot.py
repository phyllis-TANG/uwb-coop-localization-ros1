"""Compare exact set verdicts and the two per-car radius intervals."""
import csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch

HERE=Path(__file__).resolve().parent

def rows(name):
    with (HERE/name).open() as f:
        return list(csv.DictReader(f))

joint=rows('by_input.csv')
cars=rows('by_car.csv')
widths=['60','50','30','15','5','0']
ids=list(dict.fromkeys(r['id'] for r in joint))
lookup={(r['id'],r['width_cm']):r['relation'] for r in joint}
states={'EQUAL':0,'STRICT_SUBSET':1,'UNDETERMINED':2}
colors=['#a8d4c4','#e78757','#bbbbbb']
fig,(ax,rad)=plt.subplots(1,2,figsize=(12,5.1),gridspec_kw={'width_ratios':[1.1,1]})
fig.subplots_adjust(left=.18,right=.97,bottom=.23,top=.80,wspace=.36)
fig.suptitle('When does the peer range remove feasible positions?',fontsize=19,weight='bold',y=.98)
ax.imshow([[states[lookup[k,b]] for b in widths] for k in ids],cmap=ListedColormap(colors),vmin=-.5,vmax=2.5,aspect='auto')
labels=[k.replace('equal_area_square','square').replace('_',' ') for k in ids]
ax.set(xticks=range(6),xticklabels=widths,yticks=range(8),yticklabels=labels,xlabel='Allowed bias half-width (cm)',title='Joint set vs. eight anchors')
ax.legend(handles=[Patch(color=colors[0],label='Identical'),Patch(color=colors[1],label='Strict subset')],loc='upper center',bbox_to_anchor=(.5,-.20),ncol=2,frameon=False)
for car,col,offset in [('1','#17628b',-.10),('2','#a64a26',.10)]:
    selected=[next(r for r in cars if r['id']=='holdout_14_original' and r['car']==car and r['width_cm']==b) for b in ['anchor']+widths]
    x=[i+offset for i in range(7)]
    lo=[float(r['L_cm']) for r in selected];hi=[float(r['U_cm']) for r in selected]
    rad.vlines(x,lo,hi,color=col,lw=2)
    rad.scatter(x,lo,color=col,marker='_',s=90)
    rad.scatter(x,hi,color=col,s=25,label='Car '+car)
rad.axhline(20,color='#666',lw=1,ls='--')
rad.set(title='Original layout, holdout 14 s',ylabel='Minimum covering radius bounds (cm)',xticks=range(7),xticklabels=['8 only']+widths,xlabel='Allowed bias half-width (cm)',ylim=(15,31))
rad.legend(frameon=False,ncol=2,loc='upper center',bbox_to_anchor=(.5,-.20))
fig.savefig(HERE/'comparison.png',dpi=180)

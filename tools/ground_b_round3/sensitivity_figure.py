"""Draw G1-centered outer radii and certified two-witness lower bounds."""
import csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

DOC=Path(__file__).resolve().parents[2]/'docs/research/ground_b_round3/sensitivity'


def main():
    with (DOC/'results.csv').open() as f:
        rows=list(csv.DictReader(f))
    plt.rcParams.update({'font.size':12,'pdf.fonttype':42})
    fig,axes=plt.subplots(1,2,figsize=(12,5.4),sharey=True)
    fig.subplots_adjust(left=.075,right=.98,bottom=.26,top=.77,wspace=.13)
    fig.suptitle('Ground protection radius under fixed measurements',x=.075,ha='left',fontsize=20,weight='bold')
    fig.text(.075,.85,'Seed 101   ·   State 30 s   ·   2.5 cm grid   ·   Shared nine-range event threshold 26',fontsize=12)
    colors=['#22648c','#a54828']
    for ax,scene,title in zip(axes,('nominal','peer_step'),('Nominal','Peer step (+60 cm)')):
        for r in (r for r in rows if r['scene']==scene and r['G1_outer_cm']):
            i=['baseline','zero_bias','tight_sigma'].index(r['case'])
            c=int(r['car'])-1
            x=i+(-.14,.14)[c]
            y=float(r['G1_outer_cm'])
            ax.scatter(x,y,marker='o',color=colors[c],s=58,zorder=4)
            ax.text(x,y+1,f'{y:.1f}',color=colors[c],ha='center',fontsize=10)
            ax.scatter(x,float(r['any_center_lower_cm']),marker='v',facecolors='none',edgecolors=colors[c],s=56)
        if scene=='peer_step':
            ax.text(1,17,'Empty region\nTruth excluded',ha='center',va='center',fontsize=10)
        ax.axhline(10,color='#62676b',ls='--',lw=1)
        ax.set_title(title,loc='left',weight='bold')
        ax.set(xlim=(-.5,2.5),ylim=(0,39),xticks=[0,1,2],xticklabels=['Baseline\n4 cm, ±60 cm','Zero bias\n4 cm, 0 cm','Tighter noise\n2 cm, ±60 cm'])
        ax.spines[['right','top']].set_visible(False)
        ax.grid(axis='y',alpha=.13)
    axes[0].set_ylabel('Radius (cm)')
    handles=[Line2D([],[],color=c,lw=3,label=f'Car {i}') for i,c in enumerate(colors,1)]
    handles.extend([Line2D([],[],ls='',marker='o',color='#333',label='G1-centered outer radius'),
        Line2D([],[],ls='',marker='v',markerfacecolor='none',color='#333',label='Any-center lower bound'),
        Line2D([],[],ls='--',color='#62676b',label='10 cm')])
    fig.legend(handles=handles,loc='lower center',ncol=5,frameon=False,fontsize=10)
    for ext in ('png','pdf'):
        opts={'metadata':{'CreationDate':None,'ModDate':None}} if ext=='pdf' else {'dpi':180}
        fig.savefig(DOC/f'radius_sensitivity.{ext}',**opts)
    plt.close(fig)


if __name__=='__main__':
    main()

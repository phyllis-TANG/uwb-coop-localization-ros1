import csv
from study import D
import matplotlib.pyplot as plt

def draw():
    rows=list(csv.DictReader((D/'attribution.csv').open()))
    names=['Main start','Main mid','Second start','Second mid']
    fig,axs=plt.subplots(1,2,figsize=(11,4.5),sharey=True,layout='constrained')
    for ax,car in zip(axs,'ps'):
        group=[r for r in rows if r['car']==car]
        for field,label,marker,off,color in [
            ('baseline_cm','Baseline outer','o',-.16,'#1f4664'),
            ('zero_outer_cm','Known-zero bias outer','s',0,'#c2611a'),
            ('zero_midpoint_any_lower_cm','Known-zero any-center lower','^',0,'#953d0c'),
            ('tight_outer_cm','Half-sigma assumption outer','D',.16,'#148074')]:
            ax.scatter([i+off for i in range(4)],[float(r[field]) for r in group],label=label,marker=marker,color=color)
        for limit in (10,20):ax.axhline(limit,ls='--',lw=1,color='#666666')
        ax.set_xticks(range(4),names,rotation=16);ax.set_title('Car '+('1' if car=='p' else '2'))
        ax.set_ylim(6,31)
    axs[0].set_ylabel('Horizontal radius (cm)')
    fig.legend(*axs[0].get_legend_handles_labels(),loc='outside lower center',ncol=2)
    fig.savefig(D/'attribution.png',dpi=160);plt.close(fig)

if __name__=='__main__':draw()

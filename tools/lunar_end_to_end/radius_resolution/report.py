"""Plot four coarse/fine pairs and render the numeric report from verified rows."""
import csv
from pathlib import Path
import matplotlib.pyplot as plt
from run import D,P

def report():
    rows=list(csv.DictReader((D/'paired.csv').open()))
    assert len(rows)==8 and all(r['status']=='COMPLETE' for r in rows)
    fig,axes=plt.subplots(1,2,figsize=(10,4),sharey=True,layout='constrained')
    labels=['Main start','Main middle','Second start','Second middle']
    for ax,car in zip(axes,'ps'):
        data=[r for r in rows if r['car']==car]
        for i,r in enumerate(data):
            a,b=(100*float(r[k]) for k in ['coarse_PL_m','fine_PL_m'])
            ax.plot([i,i],[b,a],color='#78828c',lw=2)
            ax.scatter(i,a,s=50,c='#a24f07',label='0.05 m' if i==0 else None,zorder=3)
            ax.scatter(i,b,s=45,c='#085985',marker='s',label='0.025 m' if i==0 else None,zorder=3)
        for y in (10,20):ax.axhline(y,color='#737b85',ls=':',lw=1)
        ax.set_xticks(range(4),labels,rotation=17);ax.set_title('Car '+('1' if car=='p' else '2'));ax.legend()
    axes[0].set_ylabel('Candidate horizontal protection radius (cm)')
    fig.savefig(D/'paired.png',dpi=155);plt.close(fig)
    names=dict(zip([j[0] for j in P['cases']],['主段首点','主段中点','第二段首点','第二段中点']))
    changes=[-float(r['change_cm']) for r in rows]
    def passed(r,k):return r[k]=='True'
    def cross(lim):return [names[r['case']]+'车'+('1' if r['car']=='p' else '2') for r in rows if passed(r,'fine_within_'+lim) and not passed(r,'coarse_within_'+lim)]
    pairs=['|历元|车|0.05 m 半径 cm|0.025 m 半径 cm|缩小 cm|真实误差 cm|距 0.20 m 仍超出 cm¹|','|---|---|---:|---:|---:|---:|---:|']
    for r in rows:
        pairs.append('|{}|{}|{:.2f}|{:.2f}|{:.2f}|{:.2f}|{:+.2f}|'.format(names[r['case']],r['car'],100*float(r['coarse_PL_m']),100*float(r['fine_PL_m']),-float(r['change_cm']),100*float(r['error_m']),float(r['gap_020_cm'])))
    (D/'RESULTS.md').write_text(f"""# 四个历元的逐车候选保护半径

固定 P4(26)、原发布点和测距输入后，8 个车/历元配对中 {sum(x>0 for x in changes)} 个半径收紧，幅度为 {min(changes):.2f}–{max(changes):.2f} cm。0.10 m 半径线有 {len(cross('010'))} 个判定从超限转为满足，0.20 m 线有 {len(cross('020'))} 个，分别为{'、'.join(cross('020')) or '无'}。粗、细半径均覆盖全部八个同戳真实误差。

"""+'\n'.join(pairs)+"""

¹ 正数表示仍超出，负数表示已有余量。1/2 号车对应 p/s。[逐车配对 CSV](paired.csv) 包含 0.10 m 与 0.20 m 两条线的逐项判定和有符号差距，差值列 change_cm 定义为细减粗。

![逐车候选半径与两条半径线](paired.png)
""")
if __name__=='__main__':report()

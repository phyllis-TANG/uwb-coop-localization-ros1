"""Plot the main paired comparisons from the archived per-vehicle CSV."""
import csv
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

source, destination = map(Path, sys.argv[1:3])
with source.open() as f:
    rows = {(r["car"],r["split"],int(r["epoch"]),r["layout"]):r
            for r in csv.DictReader(f) if r["mode"]=="peer_bounded"}
assert len(rows)==16
plt.rcParams.update({"font.family":["Noto Sans CJK JP","DejaVu Sans"],"font.size":12})
fig, axes = plt.subplots(1,2,sharey=True,figsize=(11,5.1))
fig.subplots_adjust(left=.08,right=.985,top=.74,bottom=.23,wspace=.12)
fig.suptitle("相同测距噪声下，改变锚点摆位如何影响逐车覆盖半径？",
             x=.052,y=.97,ha="left",fontsize=19,weight="bold")
conditions=[("dev",0),("dev",11),("holdout",4),("holdout",14)]
layouts=[("original","原矩形","#2482B5",-.13),
         ("equal_area_square","等面积正方形","#D37932",.13)]
for ax,car in zip(axes, ["Car1","Car2"]):
    ax.set_title("车 "+car[-1],fontsize=15,weight="bold",loc="left")
    ax.set_ylim(6.5,34);ax.set_xlim(-.45,3.45)
    ax.set_yticks([10,15,20,25,30]);ax.spines[["top","right"]].set_visible(False)
    ax.grid(axis="y",color="#E1E6E7",linewidth=.7);ax.set_axisbelow(True)
    ax.set_xticks(range(4),["原路线\n起点","原路线\n中点","新路线\n4 秒","新路线\n14 秒"])
    ax.axhline(10,color="#458456",ls="--",lw=1.8)
    for i,(split,t) in enumerate(conditions):
        for key,title,col,offset in layouts:
            r=rows[car,split,t,key];l,u=float(r["lower_cm"]),float(r["upper_cm"])
            x=i+offset
            ax.plot([x,x],[l,u],lw=3,color=col)
            ax.plot(x,l,"o",color=col,ms=6)
            ax.plot(x,u,"s",mec=col,mfc="white",mew=1.7,ms=6)
axes[0].set_ylabel("覆盖半径（cm）")
fig.legend(handles=[Line2D([],[],color=c,lw=3,label=t) for _,t,c,_ in layouts]
           +[Line2D([],[],color="#458456",ls="--",label="10 cm 目标")],
           loc="upper right",bbox_to_anchor=(.985,.902),frameon=False,ncol=3,fontsize=11)
fig.text(.055,.845,"四个选定时刻 · 测距噪声标准差 4 cm · 车间测距偏差允许 ±60 cm",fontsize=11)
fig.text(.053,.06,"实心圆为可行位置对给出的下界，空心方块为以发布点为圆心的覆盖上界。新路线为独立生成的合成轨迹。",fontsize=10.3)
fig.savefig(destination,dpi=165)

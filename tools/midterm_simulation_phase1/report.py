import json,csv,statistics,math,hashlib
from pathlib import Path
import numpy as np
from scipy.stats import t
P=Path(__file__).resolve().parents[2]/'docs/research/midterm_simulation_phase1'
def csvout(name,rows):
 with (P/name).open('x') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
rows=[]
for p in sorted((P/'s0').glob('*/*/RUN.json')):rows.extend(json.loads(p.read_text())['metrics'])
assert len(rows)==364
csvout('S0_PER_RUN.csv',rows);summary=[]
for phase in ['development','confirmation']:
 for layout in ['G1','G2']:
  for link in ['wall','peer']:
   for bias in [0,.1,.3,.5]:
    for car in ['car1','car2']:
     r=[x for x in rows if (x['phase'],x['layout'],x['link'],x['bias_m'],x['car'])==(phase,layout,link,bias,car)]
     if not r:continue
     item=dict(phase=phase,layout=layout,link=link,bias_m=bias,car=car,n_seeds=len(r),minimum_common_accepted=min(x['common_accepted'] for x in r),failed_publications=sum(x['failed_publications'] for x in r))
     for key in ['D_m2','M2_rmse_m','M3_rmse_m']:
      v=[x[key] for x in r];mean=statistics.mean(v);half=float(t.ppf(.975,len(v)-1))*statistics.stdev(v)/math.sqrt(len(v));item.update({key+'_mean':mean,key+'_low95':mean-half,key+'_high95':mean+half,key+'_min':min(v),key+'_max':max(v)})
     summary.append(item)
csvout('S0_SUMMARY.csv',summary)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig,axes=plt.subplots(2,2,figsize=(11,7))
for ri,layout in enumerate(['G1','G2']):
 for ci,car in enumerate(['car1','car2']):
  ax=axes[ri,ci]
  for link in ['wall','peer']:
   rs=[r for r in summary if r['phase']=='development' and r['layout']==layout and r['car']==car and r['link']==link]
   ax.plot([r['bias_m'] for r in rs],[r['D_m2_mean'] for r in rs],marker='o',label=link)
  ax.axhline(0,color='black',ls='--');ax.set_title(layout+' '+car+'; development n=2');ax.set_xlabel('injected range bias (m)');ax.set_ylabel('D=MSE(M3)-MSE(M2)');ax.legend()
fig.tight_layout();fig.savefig(P/'S0_BIAS_GAIN.png',dpi=140);plt.close(fig)
fig,axes=plt.subplots(2,2,figsize=(11,7))
for ri,layout in enumerate(['G1','G2']):
 for ci,car in enumerate(['car1','car2']):
  ax=axes[ri,ci]
  for link in ['wall','peer']:
   rs=[r for r in summary if r['phase']=='development' and r['layout']==layout and r['car']==car and r['link']==link]
   for method in ['M2','M3']:ax.plot([r['bias_m'] for r in rs],[r[method+'_rmse_m_mean'] for r in rs],marker='o',label=link+' '+method)
  ax.set_title(layout+' '+car);ax.set_xlabel('injected bias (m)');ax.set_ylabel('mean run RMSE (m)');ax.legend()
fig.tight_layout();fig.savefig(P/'S0_BIAS_ERROR.png',dpi=140);plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(10,4))
anchors=np.array([[3.26,.1],[5.28,5.16],[5.28,2.86],[.1,2.41]])
for ax,layout in zip(axes,['G1','G2']):
 offset=np.array([0,0]) if layout=='G1' else np.array([1.49,2.01]);a=np.array([1.5,4]);path=np.array([[2,2],[2.75,2],[3.5,2],[2,2]])+offset
 ax.scatter(anchors[:,0],anchors[:,1],marker='^',label='wall anchors');ax.scatter(*a,label='Car1 static');ax.plot(path[:,0],path[:,1],label='Car2 trajectory')
 ax.plot([a[0],anchors[1,0]],[a[1],anchors[1,1]],'r--',label='injected Car1-node_2')
 ax.plot([a[0],path[0,0]],[a[1],path[0,1]],'m:',label='injected Car1->Car2')
 ax.set_title(layout);ax.set_aspect('equal');ax.legend(fontsize=7);ax.set_xlabel('x m');ax.set_ylabel('y m')
fig.tight_layout();fig.savefig(P/'S0_LAYOUTS.png',dpi=140);plt.close(fig)
lines=['# 第一批中期实验补充结果','','## P-A0 基线与证据','实际main起点b23188de8f1d70829a34a093028f6d15ddf8dfaa。旧PR91 seed7/nominal/static_moving的96秒M2/M3复现，四个逐车MSE最大差2.50e-18，沿用1e-10读回规则。实测10静态包160配对行、5动态文件32停点行及已有20窗口范围比较数值重算通过，2300项检查最大差2.60e-15。','原包141来源中，139份可保持原字节或通过LF→CRLF精确重建登记SHA；两份历史setup说明未匹配。原默认验证器失败记录保留，当前是**数值复现通过、来源身份部分未解决**，不称141份全通过。没有改原文件、SHA或数值容差。','', '## P-R2 记录级稳健性','主五包G1=2/G2=3。D负为收益；C=hist-raw；T=G2-G1。每条记录、逐车、J/W025全部见FIELD_PER_RECORD；留一记录不把帧当独立。','Car1 J留一T范围[.078009,.081381] m²，Car2 J范围[-.139945,-.137456] m²，方向均保留；W025对应[.044847,.046196]及[-.107607,-.106103]。n小且同一场地/条件，不能推广总体因果。已有五种窗口方案独立读回，不新增按效果择窗。参考每轴±2cm仍仅操作者估计下的假设敏感性，不是已标定不确定度。','', '## P-S0 偏差传播','开发2 seed×2布局×2链路×4幅值=32条件，每条件配对M2/M3。0幅值两个链路标签是重复的同一正常输入，不能增加n。冻结后50个新seed、G2 nominal/单墙+.3/peer+.3，共150条件、300方法运行。统计单位始终是50个seed，不是150个独立重复或相邻时间帧。评价6..31的共同accepted样本、26秒预定分母及失败另列。扫描幅值为研究设计，不是现场标定；开发曲线n=2不作确认推断。','', '|主场景|车|D均值 m²|95% t描述区间|seed数|','|---|---|---:|---|---:|']
for r in summary:
 if r['phase']=='confirmation':lines.append(f"|{r['link']} +{r['bias_m']}|{r['car']}|{r['D_m2_mean']:.7f}|[{r['D_m2_low95']:.7f}, {r['D_m2_high95']:.7f}]|{r['n_seeds']}|")
lines+=['','全部逐运行误差、效应量范围及失败见S0_PER_RUN/SUMMARY。区间未校正多比较，仅描述该生成模型的独立seed变动。仿真能检验指定源偏差经协同因子改变两车误差，不能识别自然NLOS、真实固定校正漂移或解释现场全部角色方向。','', '## P-S1 可估计性','诊断状态为6时刻两车天线XY加一个常值测距偏差，共25维。数据/运动/初始prior信息分开，XY尺度1m、bias尺度.1m；全奇异值与弱方向见S1_INFORMATION。雅可比最大差9.25e-10；12条件×3初值×3 prior强度=108诊断拟合，无求解失败。该小型无噪声诊断不是增广方法效果比较。','弱共线几何在静止和共同直行时，测量秩13/25，加入位移运动信息为23/25，加入初始位置prior后才25/25。不能把后者当观测信息充分。所选转弯条件数据+运动为25/25，但仅对本设计局部线性化成立，不以运动本身证明一般可观。完整最弱方向与初始化结果均保留。','', '## 是否进入P-S2','**具备启动限定诊断原型对照的条件，不具备直接启动完整生产后端增广或实车性能声明的条件。** 可先限定单常值偏差、固定几何/运动/初始化协议，保留无增广M2/M3和共线弱信息负例，再预登记校准与独立确认；本批seed已暴露不能继续作为盲确认。尚需决定偏差先验/参数化与失败声明，若要迁移8维固定窗则需新雅可比/边缘化/噪声相关合同，不在本批顺带重构。没有新保护级或论文结论修改。']
(P/'REPORT.md').write_text('\n'.join(lines)+'\n')
print('\n'.join(lines[15:25]))

import csv,json,statistics,hashlib,subprocess
from pathlib import Path
P=Path(__file__).resolve().parents[2]/'docs/research/integrity_validation_20261030'
r=list(csv.DictReader((P/'SUMMARY.csv').open()));lines=['# 正常校准与模型条件验证','', '正常校准满足预登记工程取舍，最小合格尺度为1（与原尺度相同），不是概率保证。尺度.25两车最差正常运行报警占用13.11%/14.75%，故被排除；尺度1/2六次均零报警。校准未读故障/误差/AL，冻结提交f8e1f72早于验证。','', '完成6校准+24确认+40边界=70主单元。每个单元四图、profile和时间帧均不作独立重复。G1不接受监测反馈。三种主profile另加校准B2与原B2完全重合，不重复算作独立方法。','', '## 逐车全发布结果（8 seed均值；括号为min–max）','', 'HMI单位秒，AL=.05/.10/.20m仅是假设敏感性；全部63次发布为主分母，启动unknown保留。','', '|条件|车|方法|HMI .05|HMI .10|HMI .20|可用秒|报警秒|','|---|---|---|---|---|---|---|---|']
conditions=['nominal','peer_bias','car1_common_wall_bias','wall_015','wall_060','wall_short','wall_long','wall_ar07']
profiles=['B0','B1_network|engineering_0.2m|a=0.01','B2_local|scale=1.0|a=0.01']
def get(c,car,p,al):return next(x for x in r if x['condition']==c and x['car']==car and x['profile']==p and float(x['AL_m'])==al and x['period']=='all' and x['coverage']=='all_published')
def fmt(x,k):return f"{float(x[k+'_mean']):.2f} ({float(x[k+'_min']):g}–{float(x[k+'_max']):g})"
for c in conditions:
 for car in ['car1','car2']:
  for profile in profiles:
   values=[get(c,car,profile,a) for a in [.05,.1,.2]]
   lines.append('|'+ '|'.join([c,car,profile.split('|')[0]]+[fmt(x,'hmi_s') for x in values]+[fmt(values[0],'available_s'),fmt(values[0],'alarm_s')])+'|')
lines += ['', '## 解释与边界', '', '以seed为配对单位；PER_SEED含所有时段/共同可计算分母及XY/yaw/相对误差，PAIRED_NOMINAL按每种条件实际故障结束后10秒恢复窗及late进行相同索引正常配对。各单元episodes保留预先报警、延迟与删失；trajectory保留虚拟可获得时间和开销。混合bin与长故障后的2秒late均未删除。','', '尺度1在未用于本次调参的seed上进行确认；各故障、车辆和AL效果须按上表比较，不以“检测到了”代替所有HMI清零。增加偏差/持续时间可能同时增加越限与报警，可用率代价必须与HMI并读。AR(.7)仅改变两车墙raw噪声时序、边际sigma=.04保持；它是模型失配压力而非PR77实测估计。原peer/Odom/初始化随机流不变。','', '当前结果支持将含独立历史和共享噪声相关的工程SS作为当前比较方案；没有证据仅凭残余小AL HMI就必须新算法。剩余可研究机制是初始化可信性、时序相关下协方差有效性、持续故障与恢复历史的报警/可用性折中；本轮未新增门控、回滚、约束或学习模型。8个seed是小型模型条件验证，零事件不是零风险，不认证罕见风险/PL或实车闭环实时性。','', '## 实测与参考', '', 'T02_B1使用PR77已缓存ranges、固定操作窗、历史锚点和已记录天线高度；工程sigma=.2/alpha=.01，不迁移P1校正。receive秒桶是明确的离线条件诊断，不冒充已验证在线时钟。B2缺窗口绑定Odom、可信初始XY/yaw、外参及时钟映射，未伪造初始化。没有独立XY参考，因此不算实测位置HMI、真实故障FAR/FNR或精度提升。操作不是故障真值。','', 'T10人工末点(1.48,2.97)m及1.52m间距已恢复到已有记录；同次未移动停车窗绑定、读数/量具误差仍未找到新证据，accepted保持原状态。T09/T11/T13/T15没有用于调参。PR80的参考分辨能力与用途容差仍不可互相替代。','', '## 核验与版本', '', '15项PR81合同测试及2项配对adapter测试通过；4101与原生G1全部快照精确相同。四个预登记代表单元完整独立读回；其余保存紧凑分数、声明和评价。SCORE_CHECKS独立重算2x2分离分数与全部报警；METRIC_CHECKS从声明逐项重算HMI/unknown/可用等。原核19文件导入逐SHA核对，无公共源码/geometry/manifest改动。','', '原PR81完整审计目录在另一云环境，不声称已读回；本轮使用冻结生成器RAM复现并保存输入canonical SHA。未下载bag/video、未重复十包统计或PR68/78矩阵。','', 'PR82独立修复草稿PR84：统一贴地车体与天线位置；零噪声平地/斜坡测试通过，GUI/ROS运行未复跑，不声称月球物理或定位验证。']
(P/'REPORT.md').write_text('\n'.join(lines)+'\n')
# Plot seed-level pairing, not frame-level confidence intervals.
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig,axes=plt.subplots(1,2,figsize=(13,5))
for ax,car in zip(axes,['car1','car2']):
 for profile in ['B0',profiles[-1]]:
  vals=[get(c,car,profile,.1) for c in conditions]
  ax.plot(range(8),[float(x['hmi_s_mean']) for x in vals],marker='o',label=profile.split('|')[0])
 ax.set_xticks(range(8),conditions,rotation=60,ha='right');ax.set_title(car+' HMI AL=.10m, 8 seeds');ax.set_ylabel('seconds / 63 published');ax.legend()
fig.tight_layout();fig.savefig(P/'COMPARISON.png',dpi=130);plt.close(fig)

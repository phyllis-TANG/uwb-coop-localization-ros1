# 冻结模型、统计量与可用性

预登记提交6fc4bef在三场景计算前；在线执行提交d431ba1b44222e1e2d65247b2de6eb362f949b9b（完整SHA见RUN_INDEX），计算核74fa210e7cf6aa322eaebce19530510edb605d22，PR68的19文件SHA逐一相同。实际完整在线提交以RUN_INDEX的40位SHA为准。配置参数在原config.json，不修改公共文件。只有一个G1输出轨迹，以下监测不参与轨迹/权重/恢复时刻选择。

## 共同模型与输入

每秒联合状态x=[base1.x,base1.y,yaw1,base2.x,base2.y,yaw2]；20秒固定窗；原TRF、signed pseudo-Huber、Odom预测、原1秒接收等待、浮点中心bin/median、完整QR边界prior及Schur H/g/仿射项/常数保持。天线XY=base XY+R(yaw)lever；三维高度Car1 .17、Car2 .20m；lever分别[.08,−.06]、[.12,−.08]m。这是冻结仿真设计，不升级为真实base安装标定。锚点/初始化/偏差均原仿真值。原合成初始化是t=1设计摆位加seed扰动，不读人工终点。

seed101三个场景；原生成器同时生成config/events/truth，但传给估计器的只有config/events。truth只传给evaluate；故障场景名称只供生成器/评价分组，不参与在线假设、阈值或时刻选择。共同墙偏差逐字采用PR68唯一adapter：只改Car1四墙header在[24,38)s的1120个标量+.30m，原identity/顺序/receive不改；peer_bias用原生成器Car1→Car2 +1.2m。反向peer保留身份/时间作诊断，从不平均到主观测。

完整归档不可达，未下载。事件全部RAM生成，记录实际gzip及canonical payload SHA；不声称原归档读回。配置及truth文件SHA与登记精确相同；event gzip SHA不同，缺原件无法判定是否纯压缩差异。每场景126条G0/G1保存位姿/状态、全部peer median/q与PR68紧凑表匹配，最大位姿分量差1.72e−15 m/rad；这不等于已检查原始事件逐字节相同。包装器与同机同输入原生G1全部快照/位姿/消元常数精确一致。

## B0：原q，逐车广播

q=|本帧Car1→Car2 median−never-peer辅助预测三维斜距|/.2；q>3报警，两车共同收到同一声明。辅助从启动独立，自己的状态/预测/完整prior，永不吸收peer；这里复用B2的peer排除图，而非从主图删除当前peer。辅助未accepted/缺测/非有限为unknown并不可用；不是NIS、PL或可信车认证。主G1仍接纳原peer，不把报警反馈成G2门控。

## B1：原始四锚一致性，非后验残差

对每车，四个原bin median扣原固定bias，直接拟合已知高度h下的天线XY nuisance参数：

rho_j(XY)=sqrt((x−X_j)^2+(y−Y_j)^2+(h−Z_j)^2)，T1=min_XY Σ[(rho_j−z_j)/sigma_j]^2。

用平方斜距差的代数初值及普通平方损失，不用G1/辅助状态、先验、peer或pseudo-Huber目标。仅用于检验内部两个nuisance参数，不另行发布定位器。投影锚点不共线/局部秩2，已知高度与地图，名义独立高斯且协方差已知并可线性化时，参考df=4−2=2。高度未知会消耗冗余，不默认填零；本轮高度由仿真设计给定。

三种噪声解释全部预先冻结并报告：.2m继承工程尺度（主项）；.04m原生成器单条raw噪声尺度（没有把它冒称median真实sigma）；.04sqrt(pi/(2n_j))为IID等均值高斯median渐近近似。bin内有运动、median有限样本、非线性与时序相关，均使标称卡方/误报警保证不成立；因此均称经验工程检验。没有将各时帧当独立实验，也不在线估噪声挑阈值。

alpha=.05/.01/.001，T1>chi2_2(1−alpha)报警；主项alpha=.01。两种既有简单声明都交：B1_local只报警本车；B1_network任一车报警则两车报警，两边都可算且均无报警才可用。后者不给另一车故障归因，但避免只测本车而人为弱化强基线。理想模型下网络union误警预算至多2alpha，非全网络alpha；本轮不声称该概率成立。

## B2：含独立历史的工程SS适配

原文依据与缺口见LITERATURE.md。三个预置源组：Car1全部绝对墙距、Car2全部绝对墙距、单方向peer；从开始维护三张独立排除图。各图仍用原G1核及相同输入，排除peer图数值等于G0。被排除源不进该图的墙/peer缓存、预测初值、状态或边缘化prior；无共享内存和全图状态回灌。初始化prior和两车Odom假定可信，排除“绝对源组”特指墙距，**不包括初始prior**；初始化/Odom/共同地图/多组同时故障均不在风险保证内。没有人为给剩余地图/时钟不确定度填测量零误差，只在本合成条件把它们视作确定设计值。

全解和子解共享大量观测。统一噪声primitive列：6维初始prior白噪声、每车每相邻关键帧3维Odom白噪声、各车每帧每墙median白噪声、每帧peer白噪声；标准化尺度沿原prior/Odom/range工程sigma。主/子图使用同一primitive身份；仅排除源的列永不进入该子图。不是两个独立导航解。

冻结当前鲁棒与非线性线性化的残差 r≈r0+J dx+B eps，K=−(JᵀJ)^−1JᵀB。历史prior的B用该图实际消元的QR投影递推；保留完整6维交叉，不丢affine或常数，也不重复加入已消元因子。J与B包含signed pseudo-Huber的导数；不把鲁棒目标叫卡方。监测协方差属于GN/固定线性化近似，未对优化器的二阶Hessian、线性化点适应、实际median/Odom采样误差分布作精确采样分布推导。

逐车天线选择导数L_g含旋转lever。D=L_full K_full−L_sub K_sub，C_delta=D Dᵀ=Pfull+Psub−Ccross−Ccrossᵀ，Ccross=(L_full K_full)(L_sub K_sub)ᵀ。T2=deltaXYᵀ C_delta^−1 deltaXY。每个全/子图必须accepted、全列秩；C_delta须秩2，否则拒判。初始位置prior支撑的条件满秩，不称无prior绝对可观或真实可信。

每车三个源组均可算才声明监测可用，任一T2>chi2_2(1−alpha/3)报警；未可算不能填0。主项alpha=.01、协方差尺度1；全列出尺度.25/1/2（C乘尺度平方）的敏感性，尺度是工程假设，不是实测误差范围。额外交保守网络OR，不增加新策略。参考2D椭圆/三组Bonferroni是当前系统的工程适配，非原论文完整标量风险求和与风险可用性复现；不计算PL、条件HMI风险上界或10^-5认证。

## 声明与时间分母

available=main finite且accepted、所需测试可算、无报警。alarm与unknown独立记录；已知一边报警在另一边unknown时仍可广播，但不认证可用。startup 1/2秒、缺测、求解失败、秩不足均不可用，0–1秒无发布另列。此处available是冻结工程声明，不是达到某风险要求的认证。AL=.05/.10/.20m只在评价器中用于假设敏感性，从不影响在线判定。

HMI=(真天线XY误差>AL)且声明available且未报警。另报越限但未报警（含unknown）时长，避免用unknown掩盖报警能力。每个状态代表[t,t+1)并截于64，all为63秒、common为61秒，pre/fault/recovery/late分别[1,24)/[24,38)/[38,48)/[48,64)；原故障raw混合边界也保留。时帧相关，不是63次独立概率试验。

误报警只称nominal无注入场景的报警占用/事件，单已暴露seed不是校准集或独立验证。episodes给越限起点、预先存在的报警onset/提前量、状态/虚拟可获得时间延迟与右删失；不将“后来同一报警重复发布”当新的延迟。时序按state域HMI统计，另存每条声明可获得时间=原1秒等待＋实测包装器计算的虚拟队列模型；**不是物理当前时刻/闭环连续真值HMI保证或ROS实车时延**。首次序列以外没有虚构实时调度；可获得时间成本不含原始生成器、离线独立验证和图表时间。

最终交付的监测工具补充：缺Odom当前时刻只声明unknown，不重复上帧消元/linear证据；当前primitive固定相邻1秒边，若Odom缺帧产生跨关键帧边，则B2协方差支路明确失败/unknown并记录原因，直到新运行重建，B0/B1与原核可独立继续。原三案例均无此分支，执行源码仍以d431ba1及原SHA为准，不事后改报其算法版本。

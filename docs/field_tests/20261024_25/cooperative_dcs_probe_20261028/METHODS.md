# 方法、证据边界与复用身份

## 模型与输入

冻结源提交19f1bbaa42d6631cc3c2d8660953d13a17ae76de。原F0与PR68门控的19+10文件SHA逐个相等，运行的Git HEAD变化不触发基线重跑。RUN_PLAN.json是运行前冻结的36单元，RUN_INDEX.json是完成索引；27复用结果保留原G0/G1/G2命名和run.json，不改写旧归档。每个case四方法events/config字节相同；输入、标签、生成器及每个输出SHA均在索引/REUSE_RECEIPT。名义raw range sigma=.04m、估计器peer sigma=.2m，二者不可混用。旧生成器、+1.2m正向peer故障及Car1四墙+0.30m适配均沿用PR68；共同墙场景每seed逐字段核验1120个标量差值且其余全部相同。本轮未重生成输入。

固定[24,38)注入；按状态时刻pre[3,24)、fault[24,38)、recovery[38,48)、late[48,63]评价。原±.4秒聚合在24/38边界可能混合故障/正常消息，保留原聚合与分段，不根据误差重划。1秒接收等待、不可改写已发布bin、正向Car1→Car2单条peer与反向只诊断均继承。真值/标签只在文件核验和独立评价器读取，估计器execute仅取得events和config。所有四方法每帧六维，无gyro/bias扩展。

D3活动窗所有peer每次线性化重加权；D2只首次门控新因子，其后权重来自原pseudo-Huber。两个策略的历史政策不同，不能把拒绝新因子称为从未协同。D3没有G0辅助图，也未使用健康/故障标签选权。几何保留旋转杆臂和3D斜距。公式/曲率/常数见FORMULA_MAP.md，Phi没有调参，solver相关SciPy文件SHA锁在scipy_lock.json。

## 实现接口与真实目标

kernel.WindowGraph在自己目录构造原update函数的私有globals，复用原初始化/传播/窗口/接受与失败分支；不改全局模块或公共源。原Objective(peer=False)保留非peer所有残差；只增加名义peer行，由自定义loss施加DCS，未叠原pseudo-Huber。目标F=.5(sum非peer原残差²+sum rho(e²))，局部权冻结后的H=JᵀwJ、g=Jᵀwe。通用求导没有穿过s。原TRF/exact、max_nfev=50、三停止阈值1e−7未改变；rho接受目标是明确披露的标量适配，不把论文switch目标或s²e²假装成本轮真实目标。

例如Phi=1、e=3，chi²=9，s=.2，w=.04，rho=2.6，F=1.3，真实dF/de=.12，局部GN曲率=.04；直接把s(e)e平方求导会得到−.096，方向相反。e=1两支rho和梯度连续，曲率代理保持正半定；true rho二阶与GN代理不同。SciPy custom loss第三行0是有意的IRLS曲率代理，不声称rho''=0。测试验证真实SciPy内部缩放为sJ,se且trial cost取rho。

边缘化只消费最老联合帧incident因子，保留原完整6×6联合prior及affine项。DCS旧peer消元时用固定sJ,se；另保留rho−we²常数以匹配线性化点目标。常数是平方和约定，完整F除2；已消元项不能重权或撤销。最高求解21×6=126标量，消元前22×6=132；D2辅助图另有126。各更新实际窗口、active/prior身份、消元前后prior、常数、来源链均写updates。极小信息权触及SciPy EPS曲率下限时显式报错而非暗中裁剪；本轮未触发。

## 独立核验与共享范围

13项新合同通过：小/大/边界/极限、w应用、解析peer J与FD、真实梯度、关闭peer精确D0、关闭DCS名义peer、旧D0–D2非计时前缀一致（含gate/aux）、D3跨消元prefix、Schur完整系统/cross/affine/常数、保留不双算、缺测、TRF真实目标下降、禁止全局monkeypatch、36索引缺项/重复/失败负例。关闭DCS回到名义平方peer是接口测试，不等于D1的pseudo-Huber；D1独立回归检验。27项原F0合同也通过。容差见CHECKPOINT_01，未放宽。

独立读器evaluate.py/independent.py不导入在线求解器/Jacobian/前端，复用原独立audit.py的标量几何/原非peer残差与有限差分工具；DCS公式独立书写。共享输入schema、常量、原audit非peer公式，故不能声称全部实现无共同来源。所有2268 bin核验、2745 accepted完整目标（含D2辅助）、2835 prior链；所有378次DCS消元与1512次旧/辅助消元逐次FD检查，不抽样。DCS H/g/常数最大绝对差分别7.82e−8/4.12e−9/1.60e−14。2143 accepted线性化及2143 trial cost、38994个peer权更新、549个candidate目标均回读。原F0消元使用既有audit容差，DCS使用预登记容差。

新测试v1/v2/v3均通过，无正式运行失败或修复重跑；日志增强过程保存。最初v1只留日志，v2留源码，v3对应冻结19f1bbaa/source；不把后续源码冒称v1执行版本。评估/展示新增源码不改变九个运行的执行SHA。

## 评价与图表语义

位置base XY、天线XY分别算；yaw取wrap，relative XY为两天线位置差误差，distance为3D间距误差。无轨迹对齐。RMSE只对对应真值误差；三seed分别列出，无概率置信/独立链秒推断。全有限、每车accepted、四方法共同accepted均带原分母。图展示所有有限发布，灰色为两个启动预测；启动权值只是当时局部模型作用量，不冒称完成优化。图的peer残差为预测−测量（未白化），D0无peer因子也可计算诊断残差；无因子时信息比/作用量=0。

D3图信息比=w=s²，梯度作用psi=we。D1/D2原signed pseudo-Huber残差的实际GN信息比为(h+1)/(2h²)，h=sqrt(1+e²)；梯度权却是1/h，psi=e/h。因此不能把三种方法图上的曲率比都叫IRLS权。D2拒绝当前时显示0，不代表prior/旧因子无作用。内部权重统计计数是求解器相关更新数，不能当独立试验样本。

paired_contrasts的A=same_fault_input_vs_D0：同case/epoch比较方法；B=same_method_fault_vs_nominal：同method/seed/epoch比较注入与正常。取完全相同状态/共同accepted交集后分别RMSE再相减，非相对独立解位移，未把A写成B。normal全程共同61，全部有限63；fault14/recovery10/late16/pre21。72启动未删；18 unknown均为D2辅助尚未accepted，missing另记且本矩阵为0。

成本CSV保留原timing_origin与原耗时；D3本机9单元main更新总7.596秒、逐单元p95约16.7–25.1ms，含日志IO的总回放1.16–1.47秒/63发布。旧D0/D1/D2主图更新合计4.911/6.400/6.010秒、D2辅助4.921秒，来自旧时机，仅作账目。没有同机同期重跑，不做速度比；没有paced实车延迟主张。

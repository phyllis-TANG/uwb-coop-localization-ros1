# 文献到标量peer实现

来源：Agarwal, Tipaldi, Spinello, Stachniss, Burgard，*Robust Map Optimization using Dynamic Covariance Scaling*，ICRA2013，DOI[10.1109/ICRA.2013.6630557](https://doi.org/10.1109/ICRA.2013.6630557)。[作者全文](https://www.ipb.uni-bonn.de/wp-content/papercite-data/pdf/agarwal13icra.pdf)，8页，原PDF与完整提取文本存Git外literature。SHA见LITERATURE.json。下列公式的标量适配/积分目标为本轮明确的工程解释，未声称逐语句复现g2o。

|位置|原意/符号|本轮对应|
|---|---|---|
|III/式1|原约束的名义二次误差|e=(预测3D天线距−原聚合peer)/sigma，t=chi²=e²；sigma=.2m原值|
|III.A/式3–5|残差缩放与信息矩阵缩放不同|残差/Jacobian乘s，信息权乘w=s²；不把w当s，不先过pseudo-Huber|
|IV/式6|Phi为switch先验信息|本轮无额外switch变量，不把该完整switch目标误认为式15的代入目标|
|IV/式8与15|式8的驻点Phi/(Phi+t)与最终采用式15不同|实现严格s=min(1,2Phi/(Phi+t))；不能误用式8，也不复述“式15是式6直接驻点”的说法|
|IV/式15后、IV.A|每次按当前未鲁棒误差更新，信息缩放，与IRLS关系|每个accepted线性化按当前e重算w；局部正半定GN H=JᵀwJ、g=Jᵀwe|
|V/V.A|g2o Gauss–Newton实验，默认Phi=1|冻结Phi=1；本轮保留原SciPy TRF/exact，作为标量peer适配，不称同一SLAM求解实验|

为让接受准则与上述IRLS梯度一致，定义rho'(t)=w(t)、rho(0)=0，得到：

- t≤Phi：rho(t)=t；
- t>Phi：rho(t)=3Phi−4Phi²/(Phi+t)。

目标F=.5[非peer既有残差平方和+Σpeer rho(e²)]。梯度贡献Jᵀwe；影响量psi=w·e。rho在阈值连续一阶可导，极限3Phi；s→0、w→0、psi→0。rho不是s²t，也不是式6显式switch先验代入值。直接优化s(e)·e会导入ds/de，超过阈值后得到不同甚至相反的梯度；本轮禁止这种实现。

SciPy1.15.3的自定义loss接口用三行传递cost、梯度系数和曲率。适配器传[rho,w,0]：第三行**有意是IRLS/GN曲率占位，绝不是rho真实二阶导数**。在固定版本scale_for_robust_loss_function中这严格产生局部r'=s·e、J'=s·J；TRF trial actual reduction仍用真正rho cost。因而保留原TRF信赖域与原停止阈值，权重每次accepted线性化更新，不对s数值求导。小例子与直接公式证明该接口利用方式；版本/相关函数源码SHA记录。若换SciPy版本必须重验，不按一般custom-loss API保证推断兼容。

边缘化仍只消费旧联合帧incident因子。旧peer在当时状态计算s，用s·e、s·J与旧prior/墙/Odom共同6D QR；补入非负常数rho(t)−w·t以使线性化点目标一致。全cross/affine/常数与当时冻结s保留，已消元peer无法重新降权；这不是DCS的历史纠错能力。活动窗peer每次线性化可变权，不同于D2仅首次准入；这项差异必须与最终结果同时披露。

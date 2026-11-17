# 最优性认证：Safe and Smooth 与 CORA 的对象和迁移边界

访问日期：2026-11-17。实际全文为 Safe and Smooth **arXiv:2209.04266v5**（2024-09-02更新，10页含附录）与 CORA **arXiv:2302.11614v3**（2024-09-28更新，20页含附录）。以下公式页码用作者稿内部页，不冒充期刊页。PDF仅留临时目录，未提交。版本/代码SHA及访问结果见 [CERTIFICATION_ACCESS.json](CERTIFICATION_ACCESS.json)。本笔记没有执行定位、Monte Carlo、作者测试或新数值例。

## 1. 正式发表身份

- Frederike Dümbgen、Connor Holmes、Timothy D. Barfoot，*Safe and Smooth: Certified Continuous-Time Range-Only Localization*，IEEE Robotics and Automation Letters **8(2):1117–1124，2023**，DOI [10.1109/LRA.2022.3233232](https://doi.org/10.1109/LRA.2022.3233232)。[作者v5](https://arxiv.org/abs/2209.04266v5)页眉写2022，而作者仓引用及Crossref注册元数据均给2023年卷期；正文按实际v5核查，不把页眉年作为期刊卷期年。
- Alan Papalia、Andrew Fishberg、Brendan W. O'Neill、Jonathan P. How、David M. Rosen、John J. Leonard，*Certifiably Correct Range-Aided SLAM*，IEEE Transactions on Robotics **40:4265–4283，2024**，DOI [10.1109/TRO.2024.3454430](https://doi.org/10.1109/TRO.2024.3454430)。[作者v3](https://arxiv.org/abs/2302.11614v3)标accepted，正式身份另由[MIT作者组发表列表](https://marinerobotics.mit.edu/publications)及Crossref核对。未把较早2023 arXiv年份冒充正式发表年。

## 2. Safe and Smooth：认证平方测距目标，而非本项目原目标

### 可定位原文

|位置|原文对象|对项目的含义|
|---|---|---|
|p2式(1)、p3式(2)–(3)|已知固定锚点，测量函数是距离平方；代价为平方测距残差的加权二次型|不是原始距离残差的普通WLS；即使两种数据来自同一批测距，目标也不同|
|p3式(4)–(9)|用 $z_n=\|x_n\|^2$ 等价提升为QCQP，再放松秩得到SDP及对偶|提升矩阵与约束绑定该特定目标；不是任意FGO目标的通用插件|
|p4式(10)–(15)|原始可行、对偶证书矩阵PSD及驻点条件给充分最优性证书；由残差求乘子|满足所有条件才认证；失败可能来自松弛不紧或数值问题，不能判当前解一定错误|
|p4–5式(16)–(30)|零均值GP平滑项，LTV运动关系；位置可扩为位置＋速度等，正则为二次型|可借鉴“可认证二次运动先验”的结构，不能把项目理想全局位移直接称为该连续时间动力学|
|p6 §III-E、脚注2|利用块三对角箭头结构作LDL分解，固定每时刻维数时随N线性；实测加 $\beta I$ 稳定化|跨时刻稠密相关噪声可能破坏该稀疏复杂度；近似PSD阈值和严格PSD必须分开|
|p6–7 Fig.4–6/§IV|低噪声及较好信息下认证经常成功；高噪声存在未认证最小代价解；真实UWB预先去偏|这些是相应数据上的观察，不是当前B2常值/阶跃/斜坡偏差的保证|

### 目标函数差异（本次代数核查）

写原始距离残差 $e_r=\tilde d-r(x)$；文中平方测距残差满足

$$e_s=\tilde d^2-r(x)^2=(\tilde d+r(x))e_r.$$

因此 $e_s^2/w_s$ 一般不等于 $e_r^2/w_r$：多了依赖候选状态的因子。更不能把同一个数值sigma当两种残差的同单位权重。若原始测距加零均值Gaussian噪声，平方后的噪声并非自动零均值Gaussian。这里是模型代数提醒，不是新增随机实验，也不影响“给定确定代价的最优性”本身。

当前项目还有另一车辆的未知位置、共享自由偏差b、固定中心先验及确定的位移观测。Safe的原始known-anchor lifting并未直接覆盖未知peer端点或 $r(x)+b$。把B3真幅度扣掉后再平方仍然改变残差/权重；把B2增广b塞入原证书公式也没有依据。固定位置先验作为二次正则在原则上可重新构造QCQP，但需要重推数据矩阵、乘子和稀疏结构，并不等于现有库已认证项目原目标。

原文认证矩阵 $H(\rho,\lambda)$ 是提升后的Lagrange矩阵，维数 $N(K+1)+1$，**不是**项目原状态上的GN或精确目标Hessian。普通局部Hessian正定不能取代对偶可行性。

### 证书到底说明什么

- **原文已证明：** 对所列QCQP，原始可行＋驻点＋对偶PSD给全局最优的充分条件；给定代价的这条代数结论不需要把噪声设为Gaussian。
- **不随证书得到：** 唯一解、所有最优解/可行分支枚举、估计等于真值、任意概率覆盖或HMI。论文p2明确无需假定解唯一；乘子唯一也不等于位置解唯一。
- **失败：** 原文p4明确充分但不一般必要；未认证应与已证非最优分开。只有另找到更低的原目标可行解等反证，才能据此证明原候选非全局最优。
- **实验观察的局限：** p6–7模拟的“最优”标签由10次初值中的最小代价组定义，作者承认高噪声时该标签不可靠。不得把其经验零误报作为数学上穷尽所有解的验证。真实16次飞行约1600测量时刻/次、4锚点、先校准去偏，支持该场景可用性，不是尾风险试验。报告的平均5秒中认证约3.5秒是作者设置，不能据此预测本项目耗时。

## 3. 数值容差需要单列，不等于实数定理

Safe v5 p6脚注2实测令 $H\leftarrow H+\beta I$，取 $\beta=10^{-3}$；作者同时指出合适阈值可能随几何变化。固定代码 [certificate.py L12–13](https://github.com/utiasASRL/safe_and_smooth/blob/42def2d19403e08ec92d81377426d6e92d6355d7/poly_certificate/certificate.py#L12)给REG，[L75–76](https://github.com/utiasASRL/safe_and_smooth/blob/42def2d19403e08ec92d81377426d6e92d6355d7/poly_certificate/certificate.py#L75)在状态块加正则，[L237–265](https://github.com/utiasASRL/safe_and_smooth/blob/42def2d19403e08ec92d81377426d6e92d6355d7/poly_certificate/certificate.py#L237)将此默认用于认证；[decompositions.py L4](https://github.com/utiasASRL/safe_and_smooth/blob/42def2d19403e08ec92d81377426d6e92d6355d7/poly_certificate/decompositions.py#L4)还有 $10^{-10}$ 的LDL内部容差。未逐项证明整条浮点实现的严密性。

**本次推导：** $H+\beta I\succeq0$最多说明未扰动矩阵最小特征值不低于−β（代码只在部分块移位时需按实际移位矩阵表述），不说明 $H\succeq0$。原始可行和驻点也只在数值容差内成立时，必须给出误差界或标成容差意义下的认证。不能直接将库输出的正值/布尔值当保护级证书。为得到严格数值证书，需要可靠特征值下界、可行/驻点残差控制及必要的对偶修正；本轮没有实现这些环节。

### 一个原文版本记号不一致，不推断作者程序错误

已目视v5 p4 Example 1：文本把零速度模型写为 $A(t)=F(t)=I$，同时给 $\Phi(t,t')=I$。按其式(18)，常 $A=I$ 的状态转移应为 $\exp((t-t')I)$；零确定漂移应取A=0才与给出的Φ一致。这是符号方程核验，没有运行例子。固定代码 [gaussian_process.py L56–57](https://github.com/utiasASRL/safe_and_smooth/blob/42def2d19403e08ec92d81377426d6e92d6355d7/poly_certificate/gaussian_process.py#L56)对zero-velocity返回I，故不能由稿件这处文字直接推断代码同错。该记录仅绑定读到的v5，不声称已核对期刊最终排版或取得作者勘误。

## 4. CORA：更接近原始range代价，但有两层松弛与投影

### 目标与认证链

原文v3 p4式(1)–(4)的状态含 $R_i\in SO(d)$ 与平移 $t_i$，量测为相对位姿/距离；代价包含

$$\sum_{(i,j)\in E_r}\sigma_{ij}^{-2}(\|t_j-t_i\|-\tilde r_{ij})^2,$$

加旋转和相对平移项。它保留**原始range**残差，且可处理未知peer位置，比Safe的known-anchor平方测距更接近项目的无偏差测距项。但其Langevin旋转/各项Gaussian生成模型、标量精度、未知姿态与相对里程计并不等于项目已知全局位移＋固定survey＋共享b的全部目标。

p4式(5)引入单位向量 $u_{ij}$，将range项改为 $\|t_j-t_i-\tilde r_{ij}u_{ij}\|^2$，同时放松 $SO(d)$ 为 $O(d)$；p4式(6)再作SDP秩松弛。p5–6式(10)–(15)、Theorem1及Algorithm1认证的是rank受限问题与SDP的共同最优解。**Theorem1的LICQ与乘子唯一不是地图唯一/可观测性定理。**

原文p8明确：SDP解可能不是rank d；需投影回原可行集再局部精化。若原目标的可行值与可靠下界相等，才闭合原目标最优性；有gap时可以给次优程度上界，不能因SDP已解最优就说原MAP已解最优。SO/O放松还要求投影的旋转满足原SO约束，不能只检查rank。

**迁移代数条件：** 对非负量测 $\tilde r\ge0$，$\min_{\|u\|=1}\|v-\tilde r u\|^2=(\|v\|-\tilde r)^2$。若把可正可负的校正量 $\tilde r-b$直接代入，通式是 $(\|v\|-|\tilde r-b|)^2$；不能不检查符号就宣称等价。共享未知b还产生b与u的乘积，超出原文该二次表示。这里是项目推广条件的推导，未断言作者的正常正距离实现错误。

### 适用边界与可靠负面结果

- **多解/覆盖：** 原目标全局最优不说明唯一；仍有整体坐标规范自由度或距离几何歧义。SDP高秩可以来自松弛不紧或多个解，不能直接解释成几个物理分支，也不返回全部误差允许可行集。两算法均没有在此处给真值覆盖、PL或HMI保证。
- **数值条件：** v3 p6 Algorithm1测试 $S+\beta I$ 的Cholesky，固定代码 [CORA_utils.cpp L17–58](https://github.com/MarineRoboticsGroup/cora/blob/015dc43340ca3aed07226bee1727ea929536fd01/src/CORA_utils.cpp#L17)同样对移位矩阵判断；与实数PSD定理应分开。原始可行性、驻点和projection gap都须核查，不能只读is_certified。
- **相关误差：** 原式以独立因子标量权重给目标；将真实跨时刻/跨车量测相关性写成完整联合二次型，可能改变数据矩阵及算法结构。集中式联合优化本来就通过共享状态保留信息耦合，不能因CORA可多机器人就推断必须改分布式滤波。
- **故障/固定偏移：** 原文不是NLOS模式/持续bias的安全管理方法，也未给固定survey偏移域依据。当前B2/M2共享常偏差、B3已知真注入信息与它的正常测距模型须分开；moon1的M1是原始测距模型，不具有B3的真值注入信息。改目标后获得认证不能解释旧原目标各端点是否全局最优。
- **不利结果保留：** p12–13的参数扫描显示缺少车间相对位姿回环时松弛常不紧；增加测距并非总能令gap为零。以相对gap小于 $10^{-5}$ 定义数值零，不是严密等号。这些结果限制低信息网络中的直接迁移，不是文献证据薄弱。
- **实验公平性：** p11在同一机器单核、同初始化下比较完整CORA与一次GTSAM LM，控制有据，但工作量/输出保证不同；并非所有数据CORA都更快。p12每扫描条件20实例、4000pose，回环条件200条，属于作者数值实验，不是罕见概率保证。论文的SDP变量规模 $k=n(d+1)+l$（l为range边数）与多阶低秩阶梯成本，不能外推为任意网络线性实时。

## 5. 作者代码：固定身份和可运行性检查实际做到哪一步

|项目|固定SHA/许可|本轮静态检查|没有做到的事项|
|---|---|---|---|
|[Safe作者仓](https://github.com/utiasASRL/safe_and_smooth)|`42def2d19403e08ec92d81377426d6e92d6355d7`；根[LICENSE](https://github.com/utiasASRL/safe_and_smooth/blob/42def2d19403e08ec92d81377426d6e92d6355d7/LICENSE)为BSD-2-Clause，子模块许可未审计|README关联RA-L；setup.cfg要求Python≥3.10、SciPy1.10.0等；environment.yml要求poly_matrix子模块。25个Python文件仅用AST解析，全部通过；核平方观测生成和认证容差|没有初始化/安装依赖或子模块、没有import求解代码/pytest/生成数据。语法可解析≠运行可用，更非论文复现。当前提交不等于原论文实验提交|
|[CORA作者仓](https://github.com/MarineRoboticsGroup/cora)|`015dc43340ca3aed07226bee1727ea929536fd01`；完整已取主仓tracked文件列表未发现LICENSE/COPYING，部分源头含其他项目版权说明|CMake为C++17、Eigen/SPQR/BLAS及Optimization/Preconditioners等子模块；默认examples/tests/experiments选项开启；README构建段仍使用旧cora-plus-plus路径；证书移位源码已核|没有配置/编译/运行，子模块未初始化；主仓复用许可尚未确认，不默认可复制。依赖各有许可且未完整审计；公开可读不等于可整套移植|

固定子模块指针记录在JSON。未提交任何作者源码或版权PDF。代码在临时独立clone只读，状态均clean。CORA的许可判断仅指上述固定主仓树未找到相应许可文件；[Symbol.cpp L3–8](https://github.com/MarineRoboticsGroup/cora/blob/015dc43340ca3aed07226bee1727ea929536fd01/src/Symbol.cpp#L3)仍含GTSAM版权及“见LICENSE”的指向，不能据此假定整个主仓获得相同许可，也不能推断所有作者代码均无许可。

## 6. 对当前路线的决策材料

**可借鉴模块：** 原始可行性—驻点—对偶PSD—上下界差的认证接口；把“未认证”作为单独结果状态，并把所认证目标、数值容差、projection状态随结果保存。这有助于区分数值求解问题和模型/覆盖问题。CORA的原始range辅助变量可作为未来重推项目目标的数学入口，而不是现成B2证书。

**当前不优先做整套迁移：** A端已显示局部非线性项和直接仿射差别，B端已具低维全盒证据；首先需要保持同一原始目标/可行集身份。换成平方距离或不同运动先验再认证，不能回答原目标的全局问题。当前全局最优证书也不代替外包或相关误差传播，故不将Safe/CORA作为前两项验证的必选完整系统。

**若以后单独准入：** 先只在一个固定无偏差、正测距、已明确先验的低维原目标上登记等价变换，独立核原始可行性和对偶下界，再评估共享b能否保持等价；任何代价/权重不一致或只通过移位PSD却无误差界，都不能标成严格原目标认证。本轮只提出条件，没有执行此验证。

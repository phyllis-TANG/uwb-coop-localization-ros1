# 矩阵合同与解释

本轮复用PR106的只读`information`和`block_metrics`，B的只读`readback.objective`重建r/J，另用原型目标独立核对。新增部分为明确的数据行映射、真实Ω构造、三视图统计，不修改旧函数。

状态为24位置按时间、车、XY顺序排列；B2第25维是自由常偏差，单位m。数据测距行t*9+l，l=0..3为car1-anchor0..3，4..7为car2-anchor0..3，8为peer。B0保留每时刻0..7，共48行；其他方法54行。随后20行相邻时刻四坐标位移，末4行固定首时刻位置先验。估计器测距除.04m、位移除.02m、先验除.5m。

设数据Jacobian为A、先验为L，H=AᵀA+LᵀL。SVD在JD上进行，D=diag(1,…,1,.1)，非B2没有偏差维；阈值与敏感性不变。设JD=USVᵀ，满秩时H⁻¹=D V S⁻² Vᵀ D，避免通过正规方程判秩。直接solve(H,I)仅作代表点交叉验证。秩亏、非有限或非正定边缘返回不可用，不用ridge或伪逆。

三视图：A_total=H⁻¹；B_iid=G Gᵀ；C_true_noise=G Ω Gᵀ，G=H⁻¹Aᵀ。这里固定同一个保存终点和同一个H；没有将目标换成真实协方差，也没有优化新的状态。

完整白化测距Ω_r：iid004为I54，iid008为4I54，AR为Ω_r[(t,l),(s,k)]=1[l=k]0.7^|t−s|。各链路独立、AR首项平稳，创新标准差为.04sqrt(1−.7²)。选取实际测距行的选择矩阵S_m，最终Ω=diag(S_m Ω_r S_mᵀ,I20)，不含先验块。B0的删行与Jacobian同源索引显式验证。方差乘4仅适用于测距，不能将整状态协方差直接乘4。

局部线性误差可写 e≈Gη+μ，其中η是估计器白化坐标噪声，μ包含未建模注入和固定先验中心误差。若真实原噪声协方差R*已知，则Ω=W R* Wᵀ；C仅是局部中心波动协方差，MSE矩阵还含μμᵀ。非线性时真实Hessian有残差二阶项，分支与终点变化使代入保存点的G只是近似。C不是误差界或自动校准后验，知道Ω的离线计算尚未解决实际噪声估计及漂移。

二维选择F得边缘P=F C Fᵀ，q=eᵀP⁻¹e；阈值chi²_2(.95/.99)，半轴sqrt(阈值×特征值)、面积π×阈值×sqrt(det P)。不得以H对应2×2块的逆代替边缘。常b区间半宽sqrt(chi²_1×C_bb)，仅zero/constant且实际注入确实全在候选常值上时评价真b覆盖。模型不适用不是数值区间失败，not_applicable与unavailable分列。

POINTS中covariance最后维是xx,xy,yy（m²）；error是估计−真值（m）；q无量纲。reason代码0 AVAILABLE、1 RANK_DEFICIENT、2 NONFINITE_MARGINAL、3 NONPOSITIVE_MARGINAL、4 NO_FINITE_ESTIMATE。每块的可用性与数值接受标签独立。非B2及失配常值模型的bias_q/bias_error为NaN，不参与偏差覆盖。

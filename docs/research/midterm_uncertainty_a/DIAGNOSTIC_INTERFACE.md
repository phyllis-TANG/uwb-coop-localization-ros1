# 附加交付：可复用的当前模型诊断接口

入口 `tools/midterm_uncertainty_a/interface.py:assess_saved`；底层 `diagnostics.py:diagnose`，只读输入，返回 NumPy 矩阵/字典，不调用优化器。批量保存、覆盖分母与 seed 聚类汇总分别由 analyze.py、summarize.py 负责。接口局限在当前米制状态与固定先验，不扩展成通用估计框架。

必须显式传入：

- `state,error`：同一明确状态排列的一维数组，error=估计−真值，仅离线评价使用。
- `Layout`：唯一状态名、单位（当前仅m）、每个 `(car,time,x_index,y_index)`、bias_index或None、物理尺度、数据/先验行数、白化说明。没有根据长度判定方法或状态顺序。
- `j_data,j_prior`：估计器已白化的 A、L，列与状态一致；不能再次白化。当前位置24维，B2偏差最后第25维；测距/位移分量分别除 .04/.02 m，先验除实际 sigma。
- `Noise`：明确 kind=identity 或 full，dimension等于数据行数；full covariance 是估计器白化坐标中的实际 Ω，不是原单位 R。原单位需调用者明确提供 W 并计算 WRWᵀ。对称PSD校验，不估计新噪声。
- `prior_spec`：centre、centre_mode=fixed、precision_description、position_indices。中心信息作来源记录，A/L决定曲率；本接口不从误差推断或改变中心，不验证历史估计是否由它产生，调用者须像 analyze.py 一样核对原结果来源。
- `numerical_status`：保存原数值标签，不按接受标签删样本；rank rtol默认1e-8，并列敏感性阈值。

输出包括数据/总信息秩、完整奇异谱、尺度化Jacobian条件数、零空间、三类可用协方差、每个位置/偏差边缘、q、95/99覆盖与尺寸、耦合。每条记录返回计划位置块数、可用/不可用/覆盖数；全矩阵的独立单位仍是每条件50seed，不能把单记录块数当n。

秩亏→协方差None和RANK_DEFICIENT；边缘非正定→NONPOSITIVE_MARGINAL；非有限输入→NONFINITE_INPUT、不可用数=计划数、覆盖数0。契约错误（行列、单位、噪声定义）抛ValueError，应视为调用错误而非估计失败。底层函数对非有限state/error会抛错，外层统一记录此类证据。缺失的覆盖率用null；不可用不是覆盖成功。没有ridge或用伪逆绘制全状态区间。

复用例子见 `check_interface.py`；满秩、秩亏、非有限及NOT_STATIONARY标签保留均实际检查。主批次采用同一底层矩阵实现，附加包装未改变主分析结果。

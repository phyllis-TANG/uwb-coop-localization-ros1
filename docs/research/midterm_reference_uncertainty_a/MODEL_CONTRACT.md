# 实现前数学接口合同（未实现完整求解器）

状态、观测和集合必须显式命名，禁止由数组长度猜测。所有来源绑定固定SHA，输出应记录实际输入哈希、算法/算术版本、风险合同与计算状态。

|层|状态/参考|参考集合语义|包含事件|能声称的内容|
|---|---|---|---|---|
|A0|p或(p,b)；s=s0已知|单点且真实位置恰在该点|Eε|域/模型/表示前提下，PR124目标投影≥1−αε|
|A1|(p,s,b)，再投影p|事先声明确定S且s*∈S|Eε，域前提确定成立|精确联合集合或经证明松弛的条件性外包|
|A2|(p,s,b)，S=S(Z,Y)|同一采样总体下P(s*∉S)≤αs的随机集合|E_s∩Eε|不需独立，覆盖≥max(0,1−αs−αε)|

A0不是把协方差设为0后的近似；必须真正已知s。A1只是一项确定有界假设，不是已标定事实。A2的证书必须说明对哪些固定真参数成立、是否统一、是否条件于接受/输出，以及数据依赖性。只有经验椭圆或本地Hessian时，A2证书字段为MISSING，不填写αs。

## 输入字段

1. `model_id/state_order/units/frame/epoch/antenna_reference`：A0 `[px,py,(b)]`；A1/A2 `[px,py,sx,sy,b]`。固定b可以消去但必须记录。以m、同一坐标系同一时刻为默认，不满足则转换须有误差合同。
2. `measurement_ids`：有序、唯一的原始数据身份，包含车/锚点/时刻/peer候选；`observations`为精确数或有包含依据的表示区间，`representation_basis`单列。相同数据ID不能伪装成独立两行。
3. `bias_incidence`：声明哪些行共享同一b，`bias_domain`及来源；b在模型均值中，不加到噪声协方差。错链/多链路模型不在该合同中，若允许必须新增nuisance及风险条件。
4. `reference_set`：`kind=known_point/deterministic_set/probability_set`；完整集合或有证明外包、是否有界/空、共享ID/轨迹关系、时间和参考点；A2还需`data_ids/coverage_alpha/coverage_scope/certificate_basis/selection_policy`。固定S内包不够；输出参考集合的外包才可继承包含。
5. `target_domain/bias_domain/fixed_center_set`：各自真假包含依据；不存在固定先验时明确null，不能补一个无来源“弱先验”使问题满秩。若存在，定义δc=c−Eθ∈D_c，不作为随机观测。
6. `noise_model`：明确ε维数m、顺序、零均值Gaussian前提、已知正定R及其来源、相关结构；`threshold_tau`与尾概率证书。一般R接口只定义数学，本轮认证实现只限小型有理代数例和4维阈值证明。
7. `risk_events`：Eε、E_s及任何概率域/表示/故障事件；每项有效上界与联合方式。不得将经验最大误差变成确定域、将经验覆盖变成αs，或默认独立相乘。
8. `relaxation_mode`：`joint_shared_reference`优先；可选`independent_range_envelope`必须附联合像包含证明与共享结构丢失说明；严禁默认`single_widened_shared_bias`，因为一般不保守。

## 输出字段与状态

输出包含`joint_outer_set/target_projection/reference_projection`及必要的不连通组件；可另报包围圆，但中心只能由数据/集合决定，圆须覆盖全部外包。不得只保留最接近真值或当前估计的支。应记录`noise_dimension/threshold/risk_lower_bound/assumption_status/outer_certificate/remaining_queue/boundary_contact/representation_status`。

计算状态和统计资格分开：

- `OUTER_CERTIFIED`表示声明域内外包关系得到证明，不等于区域足够小或可部署。
- `WIDE_OR_BUDGET_OUTER`只有完整未决队列保留且证书有效时仍是外包；大区域计入可用性评估，不删除分母。
- `EMPTY_IN_DECLARED_DOMAIN`仅表示域内集合为空，不能输出零误差/零保护级，也不说明真实状态不存在或噪声模型必错。
- `DOMAIN_CONTACT`是界接触的保守提示；无域依据时不能声称域外无解。
- `UNBOUNDED/UNIDENTIFIABLE`可返回集合/方向结构，但不能制造有限半径；紧域截断得到有限集合并不等于数据可辨识。
- `INVALID_REFERENCE_SET`、`R_NOT_POSITIVE_DEFINITE`、`R_NOT_CERTIFIED`、`MISSING_COVERAGE_BASIS`、`INPUT_REPRESENTATION_UNKNOWN`、`NO_COMPLETE_OUTER_CERTIFICATE`必须明确保留，不以ridge或默认数值风险绕过。

两个统计层：若每次都有有效外包，风险下界是无条件集合包含语义；若算法有拒绝输出事件A，需另报P(A)、P(A且失包含)，不能将同一下界直接写为P(覆盖|A)。本轮没有给任务AL/PL/HMI或罕见风险数值。

## 继承与必须重推

可继承PR124的精确区间算术思想、可靠下界才剔除、完整树/队列外包不变量、投影全部保留盒、空集和边界分层。不可直接继承其2/3维硬编码目标、已知s、独立逐行白化、固定m=4阈值、2/3维性能与盒预算结论。二维目标投影的圆顶点证明可复用，但必须先覆盖新联合外包的全部投影，不能假设局部中心可行。

本轮脚本是数学验证，不接收实车数据求位置、不实现一般R区间剪枝、不启动5维或9维搜索。下一阶段最小输入/输出及结束标准见DUAL_ROBOT_NEXT_SPEC。

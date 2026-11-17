# 冻结模型与拒绝状态

规范实现：core.validate、core.bounds、core.recovery、core.check。输入 schema_version=DUAL-A-V1，model_id=dual_robot_single_epoch_diagonal_v1。五维state_order固定，四维实现只消去最后一维。所有数值以有理数字符串表示；拒绝float、NaN、Infinity。观测顺序见input.schema.json与固定输入。

唯一原始ID为t0/p/a0…a3、t0/s/a0…a3、t0/p/s/peer，最后一行是唯一peer原始数据。双向转发同一个读数不能作为第二条独立观测。bias_incidence必须[0,0,0,0,0,0,0,0,1]。锚点和位置域是研究假设。

明确拒绝：UNSUPPORTED_R_OR_NOISE_FIELDS（非对角R/相关输入）、UNSUPPORTED_BIAS_LINKS（错误或多条偏差链路）、UNSUPPORTED_NOISE_OR_TIME_VARYING_BIAS（时变偏差/非本Gaussian合同）、R_NOT_POSITIVE_DEFINITE、UNSUPPORTED_PRIOR_OR_MOTION、UNSUPPORTED_UNITS_FRAME_EPOCH、INPUT_KEYS_MISMATCH_OR_TRUTH_LEAK。具体异常字符串是机器状态，不自动ridge、删交叉项或转用近似模型。

有效的退化闭域/偏差单点允许；反向区间拒绝。所有零距离直接使用距离区间，不计算Jacobian。闭集相切保留。真值域外不是扩大域理由，只表示覆盖前提不成立；搜索器不接收该真值。

OUTER_CERTIFIED：树/叶核查有效且无PENDING，不意味着所有未决叶达到请求分辨率或半径可用。
BUDGET_OUTER：存在完整PENDING队列，仍保留全部域内可能解；测量成本/停止原因须如实保存。
EMPTY_IN_DECLARED_DOMAIN：所有叶被可靠排除，不推出域外空，不输出零误差。
证书缺失/破损：NO_COMPLETE_OUTER_CERTIFICATE或具体拒绝，不能报定位失败率为零。

独立性边界：A核只用标准库有理数，未导入B或历史求解器。B可以读合同，不应把A的bounds函数直接当作自己的求解内核后再声称实现独立；若复用，必须披露共因缺陷风险。逻辑独立证书检查不是形式化验证，也不认证平台模型。

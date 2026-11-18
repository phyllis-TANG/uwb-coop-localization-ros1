# 中期报告技术摘要

**研究问题。** 在月球合成双车定位中，peer常偏差/趋势状态是否把运动误差吸收为UWB偏差，以及较低拟合残差是否意味着更好定位？实测PR130提供弱朝向、外参和异步缺测的证据边界，不提供连续轨迹真值。[SOURCE_MAP、OBSERVATION_CONTRACT]

**方法。** 复核PR125的M0独立、M1协同、M2常偏差、M3线性趋势方程；6时刻、固定高度、XY状态，统一Gaussian目标。对比等边际方差白噪声/AR1、5%尺度和局部.15m运动异常。条件与数值门槛在评价前冻结；独立循环残差和差分Jacobian核验，不调用优化器。[MODEL_AND_PARAMETERS、PROTOCOL、FREEZE]

**实验条件。** LuSNAR Moon_1的10帧LiDAR、1094行GT、120.064s；同序列三个几何窗口、错时5s人工第二车、人工锚点；核心1920方法及240单因素扩展，共10个独立seed簇，窗口和方法不充当独立样本。2160项均有限，2123数值接受、37未驻点，无中断或未执行。[SCENE_AUDIT、PROGRESS、figures/scene_coverage.png]

**主要结果。** ramp/white中Car2 M3相对M2平均改善6.50mm；ramp/slip_proxy中反而恶化2.89mm且该30对均数值通过。相同异常使正常peer的M3趋势多出约.05m/s，说明误差吸收。±50ms偏移可形成约±.13m的看似peer常偏差。[PAIRED_SUMMARY、MOTION_ABSORPTION、SENSITIVITY_BIAS、figures/core_rmse.png]

**适用范围。** 这是观测层合成验证；全局增量不是实际轮速/IMU，短时异常不是月壤动力学。没有独立第二序列、完整朝向状态或真实噪声标定。GPU不可用，仅导出并读回运动学USD，Isaac实际渲染/物理未执行。局部协方差不是安全保护界。[SCENE_EXECUTION、LOCAL_COVARIANCE、REPORT]

**下一步。** 首先研究运动相关/尺度/短时异常的显式模型与peer偏差可辨识性，再设计带连续位置/朝向参考和统一时间基准的采集约束参数；本轮结果不能直接成为认证安全区域。[DECISION_MEMO、AB_INTERFACE]

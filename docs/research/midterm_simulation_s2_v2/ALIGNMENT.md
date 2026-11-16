# A/B固定来源对齐

A PR99 ed17e3ad177b5d52c1470e85da9f7a8645dbada9；B PR98 8174445e3b8e473bef15a82d345b7a7e1d94ac05；共同PR97 df323eccdffd375a2fb255ebbfd734b6c2be4aac。A独立detached稀疏checkout只读使用；读取REPORT、S2_INTERFACE、CONFIG和design实现。B复读REPORT、MATH、CONFIG、prototype、VALIDATION_PROTOCOL_DRAFT。来源文件SHA见SOURCE_LOCK.json。

|项|共同点|差异及本轮处理|
|---|---|---|
|状态|6时刻[x1,y1,x2,y2]，m，B2末尾一个自由b|B0/B1/B3为24维；A主要25维|
|模型|48墙+6peer欧氏距离；wall=Car1-anchor0或peer六行增距；强全局XY位移20行|非未知航向实车模型，禁止外推|
|几何运动|good/weak及static/straight/turn公式一致|A增near，锚点(-3,0),(-1,.01),(4,-.01),(6,.02)，车初始(1,.01),(2,-.01)；本轮补入，static/turn受控|
|噪声|range .04m，motion .02m，独立Gaussian实际注入|A场景索引参与SeedSequence；B四固定流跨场景共享，本轮共同面板严格用B generate|
|位置先验|仅t0四坐标|B noisy center=truth+噪声(+偏移)，sigma .05；A固定survey和.05/.5/5。补充采用A survey，.5/.05/无prior，非现场标定|
|初值|带噪运动积分|B原center改变也改变start，不能独立归因；补充固定survey积分start，改center/weight均不改start|
|b|无prior、无非负限制|B2预知链路，B3再知真实注入；不是故障识别|
|尺度秩|XY1m/b.1m，白化JS，相对1e-8|A全零空间及1e-6..1e-12敏感性和偏差有效信息；B原只最弱方向。本轮添加完整诊断|
|失败|保留所有结果、上限/异常|A success+finite，位置RMSE>.5与abs(b误差)>.1分别统计；B再要求optimality<=1e-5。本轮保留B数值口径，另列A误差阈值|
|结论边界|局部秩不等于有限噪声精度|weak/static数据+运动23/25但b可辨识；不能称为结构性b不可辨识。A peer-only另模型才有混淆，本轮不删除墙观测|
|种子|均开发|B 26011601..03、A 621160101..112、PR97 16101/16102/17101..17150已暴露；本轮只26011601，n=1|

常值注入加c且自由b同步加c，预测减观测不变，位置目标相同；它是目标函数平移等价，不是未知故障泛化。固定b初值0未同步平移时优化路径可能不同，不能把数值差异误作代数性质失效。

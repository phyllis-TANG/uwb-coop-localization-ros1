# 月球仿真完整流程

开发基线 `3ad69c8137183c1986012e354857b73527978c48`，独立分支 `research/lunar-end-to-end-validation`。本轮是观测层仿真，不是月壤轮地动力学验证或真实噪声标定。历史 PR125/130 优化未重跑。

阅读顺序：SOURCE_MAP → SCENE_AUDIT → OBSERVATION_CONTRACT / MODEL_AND_PARAMETERS → PROTOCOL / FREEZE.json → REPORT → DECISION_MEMO / HANDOFF。机器清单包括 INPUT_SOURCES、WINDOWS、INPUT_MANIFEST、RUN_PLAN、SEEDS；每次运行的完整状态及估计保存在便携归档中。

复现环境：Python 3.10、numpy 2.2.6、scipy 1.15.3、matplotlib 3.10.9、usd-core（版本见交付环境清单）。`tools/lunar_end_to_end/checker.py <归档> --output <json>` 解包并独立重算，不调用优化器，不依赖本地原始数据路径。重新建场景需要 INPUT_SOURCES 所列原始文件；不要向历史输出目录写入。

冻结分两步：提交全部代码、协议、输入身份和清单获得40位提交；FREEZE.json 随后记载该提交及文件哈希。FREEZE 自身不列入自引用哈希。评价只允许从冻结提交 HEAD 运行，最终交付提交可以更晚。

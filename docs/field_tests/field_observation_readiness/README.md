# 实测观测与当前研究接口：选用及独立复读

结论：仓库已有数据足够开始有边界的实测接口/一致性分析，暂不需要上传更多重复包。静态013206检查观测；015334检查一静一动；033248交换角色；050447用于双车同动；045116保留挑战对照。选包依据实验角色，不依据结果是否改善。

先读[REPORT](REPORT.md)、[INPUT_CONTRACT](INPUT_CONTRACT.md)、[DECISION_MEMO](DECISION_MEMO.md)。本次没有新定位解算，optimizer_calls=0、formal_runs=0。旧求解器和历史统计不变，所有包均为已暴露开发数据。

## 实际执行

基线2049084cd58588fd33fecccf5c965e9810a2ed26；冻结源码2fad8a05acd54623b1769feb580e0b5938c2e9e8。工作树/home/ubuntu22/uwb-field-observation-readiness，分支research/field-observation-readiness，初始干净；origin为项目GitHub仓库。无祖先/树内AGENTS。原moon1工作树未修改。沙箱可见进程仅codex及检查进程，不能据此推断宿主机；初始可用21GiB。
独立venv与结果在/home/ubuntu22/uwb-field-observation-readiness-artifacts，Python3.10.12、NumPy2.2.6、SciPy1.15.3、rosbags0.10.11。CPU、BLAS单线程，无ROS启动、GUI或驱动修改。

```bash
# 原始bag只读；输出目录必须不存在
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /home/ubuntu22/uwb-field-observation-readiness-artifacts/venv/bin/python  tools/field_observation_readiness/audit.py  --out /home/ubuntu22/uwb-field-observation-readiness-artifacts/audit001

# 便携复核，无优化器；无需ROS运行环境
PYTHONDONTWRITEBYTECODE=1 /home/ubuntu22/uwb-field-observation-readiness-artifacts/venv/bin/python  tools/field_observation_readiness/verify.py  docs/field_tests/field_observation_readiness/results
```

两条命令均已实际完成。原始SHA/运行版本见SOURCES/RUN；交叉复核见CROSSCHECK。便携复核通过5包、74353条导出消息、25组配对分母及重复/无效链路/边界测试。

results各case下measurements.jsonl.gz只保存观测字段，reference.json保存历史备注索引，不混入连续真值或故障标签。quality非有限值编码null；仅用于审计，不作权重。此导出是审计schema，尚不是可直接运行Moon_1求解器的measurement文件。
TOPICS、CARS、LINKS、PAIRING保留完整分母；原bag额外8386条辅助topic消息只计数不解码，未称全部逐字段核验。结果约2.4MB，无需提交原始bag副本。

交付分支仅含本次两个新增目录。为避免把未合并的Moon_1 PR125捎入本次PR，交付提交将移植到已核对的main=30f9379249a4e695acf75910c40862a770e6f4ce；所用原bag、冻结解析器及场次配置在两基线间逐字节相同。运行来源SHA仍保留原值，不改写历史回执。

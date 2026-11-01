# 读取既有证据，无需再运行定位

从仓库根执行，使用Python3.12、NumPy2.2.6、SciPy1.15.3；实际模块路径和完整环境在checks/ENVIRONMENT.json。已有相同环境可直接使用，否则在独立venv安装锁定版本：

```bash
python3.12 -m venv /tmp/geometry-review-venv
/tmp/geometry-review-venv/bin/python -m pip install numpy==2.2.6 scipy==1.15.3
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
PY=/tmp/geometry-review-venv/bin/python
# --output必须是不存在的目录；逐归档/成员SHA校验后安全解包。
$PY docs/research/geometry_correction_20261101/verify_published.py --output /tmp/geometry-review-evidence
$PY tools/geometry_correction_20261101/metric_readback.py --matrix /tmp/geometry-review-evidence/geometry-correction-20261101-private/matrix-v1 --analysis /tmp/geometry-review-evidence/geometry-correction-20261101-private/analysis-v1 --output /tmp/geometry-review-evidence/METRIC_READBACK.json
```

五份tar.gz均须解包，路径互不重叠；ARTIFACTS.json列出732个成员的精确hash，包括原私有FULL_ARTIFACT_MANIFEST本身，其余731个文件与原交付逐字节一致。分装仅改变tar/gzip容器hash，原私有整包hash保留于checks/DELIVERY_RECEIPT.json。archive内源码快照、SOURCE.patch、日志和每seed全部随机原语/输入/初始化/真值/三方法输出均完整保存。

新执行原48单元的入口是tools/geometry_correction_20261101/matrix.py，全部实际argv保存在results/RUN_INDEX.json；审查无需重新执行。协议和科学指标代码都在结果前提交63701fee，不随交付改变。

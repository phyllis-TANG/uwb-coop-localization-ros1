# 交付与验收

固定起点：`30f9379249a4e695acf75910c40862a770e6f4ce`。
冻结SHA：`7fa34bf382698c60945039ca7d06690a5658ee3c`。
分支：`research/profiled-region-efficiency-b`。
工作区：`/home/ubuntu22/uwb-profiled-region-b`。
Git外原始结果：`/home/ubuntu22/uwb-profiled-region-b-artifacts/results`。
交付SHA见PR完整HEAD，避免自引用哈希。

实际完成：确定性26输入/52记录（8旧记录复用，新搜索44次）；随机600输入/1200方法运行；本轮新搜索共1244次。没有重复搜索PR124八例，没有追加seed或预算。开发11项合成测试独立计账；不计入随机样本。非线性局部优化器调用0。

阶段二全部证书和包含判据通过才进入随机阶段。随机1200完成、0未执行、0证书失败、0数值失败、0搜索预算中止、0整体空集；各条件外包真位置包含100/100，但精确固定位置可行b仅97/98，不能声称罕见风险保证。确定性中保留原空集及两方法强制16盒中止。完整分母见库存表及SUMMARY。

## 便携结果

8个分片共约95.2MB，含3763个原始输入/树/attempt/receipt/阶段文件，逐文件SHA登记在evidence/MANIFEST。Git外原始结果仍保留；Git内分片用于可携带独立验收。解包拒绝已有目标、路径穿越、链接及哈希不一致：

```bash
export PY=/path/to/venv/bin/python
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
$PY tools/midterm_profiled_region_b/unpack.py \
 --archive docs/research/midterm_profiled_region_b/evidence --out /tmp/profiled-evidence
$PY tools/midterm_profiled_region_b/readback.py \
 --results /tmp/profiled-evidence/deterministic --out /tmp/deterministic-check.json
$PY tools/midterm_profiled_region_b/readback.py \
 --results /tmp/profiled-evidence/random --out /tmp/random-check.json
$PY tools/midterm_profiled_region_b/analyze.py \
 --results /tmp/profiled-evidence --out /tmp/profiled-analysis
$PY tools/midterm_profiled_region_b/audit_delivery.py \
 --results /tmp/profiled-evidence --analysis /tmp/profiled-analysis --out /tmp/counters-check.json
$PY tools/midterm_profiled_region_b/union_audit.py \
 --results /tmp/profiled-evidence --out /tmp/union-check.csv
sha256sum -c docs/research/midterm_profiled_region_b/SHA256SUMS
```

以上入口没有搜索或优化器调用；原始随机全量证书读回约143秒。已在独立解包目录核验全部3763文件字节一致。无需为了验收重跑搜索。硬中断用inventory.py列出不确定attempt/缺失receipt，不自动重跑。

冻结执行源码、公式、输入、预算及统计代码原样保留。新增union_audit/describe_regions/audit_delivery/pack/unpack均为冻结后的只读解释或归档入口，见POSTFREEZE_ANALYSIS，不能冒称预登记新实验。主表面积上界与精确并集面积必须分开解读。

仅新增指定两个目录，没有改历史定位器、历史结果、中期正文或其他窗口。普通PR目标main，不自动合并。

# 验收交接

分支 research/midterm-inset-validation-b，来源PR116固定提交34f364d77c0964f22563bad6e5869567fe5f163c。起始时PR116尚未进入main；本分支继承它但没有合并任何PR。相对固定来源只新增两个本轮目录。正式冻结SHA：34172c52107711b562eb7210bfd4edd5e9b30ce6。交付SHA以PR分支完整HEAD为准，避免自引用哈希。

开发20方法/40真实调用，正式600方法/1200真实调用；正式600仿射直接解。正式600有限、596接受、4未驻点；失败和不可用均保留。正式运行已全部结束，不要以验收为由重复优化。全部阶段已持久化，恢复新调用0。独立读回真实优化器调用0。

按README依赖环境及命令执行 analyze.py --archive 和 verify.py。前者输出新目录，后者核对身份、保存状态、独立线性解、残差/Jacobian、局部噪声协方差及覆盖；验收结果必须PASS。输入及输出清单在results，完整源与结果哈希在SHA256SUMS；校验命令在仓库根目录：

```bash
sha256sum -c docs/research/midterm_inset_validation_b/SHA256SUMS
# 冻结后新增的可用时刻交集描述，非预登记主分析：
PY=/path/to/python bash tools/midterm_inset_validation_b/describe_common.sh /tmp/inset-readback /tmp/inset-common
```

外部原始目录：/home/ubuntu22/uwb-midterm-inset-validation-b-artifacts/formal；原始ledger及事件不能覆盖，便携证据已进Git。依赖版本、来源文件SHA和执行根记录在RUN.json，输入/配置/源码/依赖/阶段及实际P0端点进入恢复身份。有attempt无结果时停止并人工核查，禁止自动重跑。

阅读REPORT时务必保留weak首时刻4800条候选区域不可用的分母信息，以及全有限/accepted两个口径。COMMON_AVAILABLE_*是冻结后的描述补充，不能取代原主表或声称六时刻覆盖。没有修改任何冻结执行Python源，没有追加实验，也没有修改中期正文。

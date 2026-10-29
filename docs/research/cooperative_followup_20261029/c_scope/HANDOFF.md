# 任务C交接，2026-10-28

**结论**：最近工作已覆盖解分离/prior故障、质量折减、坏移动参照子集和低冗余拒判；ASR 2026公开预览还声称配置一致prior与可信检查点，但全文仍缺。PR72单seed最小开发相对同预算裁剪无已证必要优势，贡献尚未成立。10月30日优先补独立参考；通过A才用连续轨迹，通过B只用停点，C仅诊断。

## 文件归属、版本与证据级别

- 本工作树 `/home/ubuntu22/uwb-cooperative-c-scope-20261029`；独立分支 `research/20261029-c-scope`；起点远端`main`完整SHA `0ef38e8b84dc88cb7b0e26fea595ac05c5162676`。它已合并PR72，晚于PR71的`aa6d272f9dcb7180d7548a06cb11d5d28445b2dd`；本分支只新增本目录。原主工作树HEAD `115b17deb2f848e596d1638a0b45cf360deae947`无改动。长期ROS/rosbag进程未操作。
- PR67只读固定HEAD `71e31e61d6a49e0f738c37b5c909e43a89a282d2`，通过`git show origin/pr67-readonly:docs/research/paper_scope_20261028/literature/{README.md,PAPERS.md,READING_LOG.md,COMPARISON.csv,BASELINES.md}`查看。未把PR67文件加入本分支；其README blob SHA256 `3cbe85b8ea0bafa366f927f534a85c23138f8a22395bfac589d7613bcbcbb495`。
- PR72固定HEAD `1cc7713a7e48776474788a07a1b41040f9df9330`，执行源码 `312180ef51c6ea4ba394bc85618674ec36ff786d`。只读报告、方法、冻结配置与原交接；**未重算定位结果**。C_SCOPE中数字均引用PR72 REPORT，不把测试、预算满足或求解收敛当实测精度。
- [C_NEAREST_WORK.csv](C_NEAREST_WORK.csv)为本轮方法对照，前三篇核对一手公开来源；QA-DSE/DECLARE/DCS仅核对PR71已有审阅摘要。[C_SCOPE_ONE_PAGE.md](C_SCOPE_ONE_PAGE.md)是会议建议；[LAB_PRECHECK_20261030.md](LAB_PRECHECK_20261030.md)是新补证草案，未执行现场量测。

## 实际阅读、障碍和复核命令

已读PR71路线README、PHASE0_ANALYSIS；PR72 REPORT、METHODS、FROZEN_CONFIG、HANDOFF；RESULT_CONTRACT、geometry.json、视频MISSING_EVIDENCE及PR71两次实验室采集方案。上述文件SHA256按顺序分别为：`1b05ce5dde381b6bda47a4d16326d9821ef505acea3550122a9bbaafe3de22fc`、`c7ee68f321ef010d857062760c48b6cc3d5c64f9d21e546cf3ccac4799cb2f8f`；`8c92fcbb938164006ee8f915476f76fdb426d44f1a8346a06ed5a1552ce43cc6`、`d0b96f792427e4a9eb39eefa3fa5e8df19d0c8c8313c807c2abc8df3a1c5c7ad`、`d474b5af06260ca3b38a133b4f5a006662de42979c535a7901d0a6ad9c17db68`、`ced24722f0fb662fa2ac738683cbdc1f488c222860ad6c1d64e383546f4c58ee`；`f8daef477973b46cf7eb22a45eb36d24a28e62ee09548750be4ec3530905e355`、`bd59d654a6794cc61a5680816d479a7ae3a4b5a0376a3d5ebd517b6c3842266c`、`332d5e6674988040705b07f21c0dab875c659b8c4c20d76bb7d33adb8eb6c76e`。采集方案已读但此处不逐项列哈希。

本轮没有调用定位器、下载bag/视频或生成大证据。文献只读检索：

```sh
git fetch origin main refs/pull/67/head:refs/remotes/origin/pr67-readonly refs/pull/72/head:refs/remotes/origin/pr72-readonly
git show origin/pr67-readonly:docs/research/paper_scope_20261028/literature/PAPERS.md
git show origin/pr67-readonly:docs/research/paper_scope_20261028/literature/COMPARISON.csv
sha256sum docs/field_tests/20261024_25/{RESULT_CONTRACT.md,geometry.json}
git diff --check
python3 -c 'import csv,pathlib; p=pathlib.Path("docs/research/cooperative_followup_20261029/c_scope/C_NEAREST_WORK.csv"); r=list(csv.reader(p.open(encoding="utf-8",newline=""))); assert len(r)==7 and len({len(x) for x in r})==1; print(len(r)-1,"rows",len(r[0]),"columns")'
```

一手来源：[ASR出版社公开预览](https://www.sciencedirect.com/science/article/pii/S0273117726013074)、[Hafez等NSF公开全文](https://par.nsf.gov/servlets/purl/10203881)、[Olawoye–Gross出版社全文](https://www.mdpi.com/2076-3417/16/10/5137)。当前网络读取ASR出版社正文返回403，页面只展示摘要、引言和章节预览；MDPI直开返回429，搜索引擎所索引的官方HTML可核对§4.2.3–4.2.4，且PR67已记录全文阅读；NSF直开返回502，PR67已记录全文8页和页节定位。没有以摘要/索引片段冒充本轮阅读全文，也未绕访问限制或下载出版社PDF。

## 10月29日需决定、剩余事项

1. 若能合法取得ASR全文，专门核对其候选隔离集、可信检查点来源、prior重建与再准入公式；否则相关新颖性判断保持悬而未决。
2. 冻结真正要分辨的效应`Δ_min`、参考用途与总不确定度容差。现场先预检两车天线、板/相机、独立Q和时钟，失败按B/C降级；不把新数据填回旧场次。
3. 若没有可判定、对简单裁剪/固定缩权确有必要的需求，停止候选机制扩张，保留影响合同及负结果作为研究记录。第二次7小时访问日期未定，按首访参考验收结果决定用途。

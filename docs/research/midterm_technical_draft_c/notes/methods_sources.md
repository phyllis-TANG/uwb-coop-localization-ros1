# 第 1–3 章来源核查与编号说明

只读来源固定提交：`c51411433d30dc379bd69cf5fb20a11e196b7182`。以下 M 编号是本文资料引注，不是外部文献编号或原实验编号。路径均相对仓库根目录；正文汇编时保留本表以定位所有引注。

| 代号 | 文件与定位 | 用途及限制 |
|---|---|---|
| M01 | `docs/research/paper_evidence_completion_20261103/README.md` 第 9–25、37–41 行；`dynamic/reserved/RESERVED_RESULTS.json`；`verification/dynamic_all_32_stop_rows.json` | 静态/动态状态区别、天线转换、停点参考和 B2 中断身份；保存估计轨迹不是真值轨迹 |
| M02 | `tools/midterm_simulation_phase1/identifiability.py` 第 16–29 行；`tools/midterm_simulation_s2/prototype.py` 第 44–67 行；`tools/midterm_prior_mechanism_b/math_model.py` 第 6–15 行 | 六时刻 XY、候选墙链/peer、相邻位移因子、B0–B3。PR109 math_model 专用于 peer，不泛化到任意 wall 故障 |
| M03 | `tools/midterm_simulation_validation/core.py` 第 43–70 行；`docs/research/midterm_uncertainty_a/THEORY.md` 第 7–11 行；`docs/research/midterm_prior_mechanism_b/CONFIG.json` noise/priors 字段 | 真实生成与假定权重区分、首时刻先验、固定 survey 积分初值；非真实噪声估计 |
| M04 | `docs/research/midterm_prior_mechanism_b/PROTOCOL.md` 第 7–27、31–40 行；`tools/midterm_prior_mechanism_b/adapter.py` 第 9–16 行 | 三种先验中心机制、控制变量、线性解析身份、P0/P1 接受规则和随机单位 |
| M05 | `docs/research/conference_paper_v003_20261101/MODEL_AND_CALCULATIONS.md` 第 13–43、47–61、74 行 | 单次收益公式，D/C/T 原定义、符号、参考敏感性及 G1 车2分解。正文用 beta 表示位置偏差，以免与增广测距偏差 b 混淆 |
| M06 | `docs/research/paper_evidence_completion_20261103/verification/static_scope_20_readback.json` `scope=five_N_bags_normal` 四条记录；上述 MODEL 第 65–74 行 | 表2-1均来自保存值，六位小数展示；记录级等权，范围不当CI |
| M07 | `docs/research/midterm_simulation_phase1/REPORT.md` 第 8–10 行；`docs/research/paper_evidence_completion_20261103/README.md` 第 39 行 | 留一记录敏感性与每轴±2cm假设身份；数值读回不抹去历史来源校验缺口 |
| M08 | `docs/research/conference_paper_v003_20261101/MODEL_AND_CALCULATIONS.md` 第 76–86 行；`docs/research/geometry_correction_20261101/REPORT.md`；`results/DECISION.json` | PR91偏差传播、PR92交互及车1方向复现失败；保留四seed与合成模型限制 |
| M09 | `docs/research/midterm_simulation_s1b/REPORT.md` 第 3–24、30–42、68–72 行；`tools/midterm_simulation_phase1/identifiability.py` 第 26–29 行 | 全状态秩与偏差可辨识性不同，peer-only反例，全局位移强假设、偏差分解 |
| M10 | `docs/research/midterm_uncertainty_a/THEORY.md` 第 9–57 行 | GN曲率、Schur边缘、固定先验噪声传播、系统偏移、点椭圆。正文用 Sigma 表示矩阵以区分静态 C_i |
| M11 | `docs/research/midterm_uncertainty_a/NOISE_MISMATCH_THEORY.md` 第 7–27 行 | sandwich及时间相关、固定偏移、先验相关交叉项；真实Omega是理想诊断 |

## Git 历史与实际可读性

- `MODEL_AND_CALCULATIONS.md` 的最近来源提交为 `505cc435e77e39e5f71d420deb7cfbf8237f4c00`，提交说明为会议稿 v003 与 PR92 证据交接。
- 旧 v003 的部分 `outputs/...` 是 Windows 环境路径，不代表当前树内文件。后续补证目录由 `70dbb5ffad75f525dbfb870342d0b7c67742bba7` 引入；本稿引用实际存在的 `verification/` 和 `dynamic/reserved/` 数据，不把旧文稿的缺失声明沿用到已补齐项目。
- PR109 的 `adapter.py` 只读导入 `midterm_simulation_validation/core.py`，后者复用 `midterm_simulation_s2/prototype.py`，再复用 `midterm_simulation_phase1/identifiability.py` 的测距及位移定义；上述目标函数、维数和运动模型已按这一调用链核查，不仅依据文件名。

## 原始方案与编号检索范围

已对固定树 docs、tools 的 Markdown、TXT、Python 进行 `师兄`、`原始方案`、`HCPL`、`E1–E4` 搜索，查看已跟踪 PDF/TeX/Word 文件名；另只读列举 `/home/ubuntu22/下载`、`/home/ubuntu22/桌面`、`/home/ubuntu22/文档` 中 PDF/DOCX/TeX/PPTX 候选文件，未找到可识别的师兄方案原文件。没有读取个人聊天数据库或用聊天摘要替代原文。既有 `midterm_uncertainty_a/THEORY.md:3` 与 `HANDOFF.md:19` 亦明确记录未找到原文。本次结论是“在这些可访问来源中未找到”，不是断言原文件不存在。

`paper_scope_20261028/evidence/MIDTERM_OUTLINE.md` 使用 F1–F6 等证据标识，`paper_evidence_completion_20261103/incoming/Outline_readable.txt:59–99` 使用 R1–R9 与 S1–S6。后者 S1=早期接口模拟，S2=三 seed 旧固定窗合成；本轮 P-S1/P-S1b/P-S2 为另一系列，绝不合并计数。未能确认用户所说 E1–E4 的原始文件编号映射，列入资料缺口，不能自行命名四项实验并宣称已对齐。

## 本分稿静态检查

本分稿只新增正文与本说明；未运行定位求解器、未修改原论文或任何旧实验脚本/结果。公式残差符号统一为预测减观测，因此误差传播均值使用正的观测漏项及先验中心偏移；D/C/T 均以协同减独立定义。矩阵 Sigma 与实测 C_i 区分，时间集合采用花体 T 与交互 T_i 区分。编译及完整引用检查由主整合流程执行。

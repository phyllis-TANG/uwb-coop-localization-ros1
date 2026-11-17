# 小车协同定位中期报告——C端技术初稿

研究题目：**Safety Quantification for Multi-Agent Cooperative Localization in Lunar Exploration**。

这是面向中期答辩委员会的方法、实测动机、仿真与技术讨论初稿。绪论和文献综述由其他窗口负责；本稿只保留技术衔接。**本次新增定位运行0，新增真值线性化诊断0。** 文中运行数全部指历史固定批次。本交付只新增本目录，不修改论文定稿、实验脚本及已有分析结论。

## 阅读顺序

1. `TECHNICAL_DRAFT_ZH.md`：合并技术正文；`TECHNICAL_REPORT_ZH.pdf`：中文排版版本（正文20页，总23页）。
2. `CLAIM_EVIDENCE.csv`：逐条结论、适用条件、来源位置、固定提交、限制和拟放章节。
3. `FIGURE_TABLE_INDEX.md`：图表、全矩阵入口与独立样本口径。
4. `OPEN_QUESTIONS.md`：尚缺的原始方案、现实先验/噪声证据和A/B插入要求。
5. `HANDOFF.md`：交付与审查记录；`notes/`：环境、来源核查与自动检查。

正文不附完整大矩阵，完整表在固定来源和本目录 `evidence/` 的必要PR108副本中。图如原样复制，其字节哈希需与固定提交一致；不重新求解。

## 固定来源

|来源|已审查提交|作用|
|---|---|---|
|PR106|`d39c99589bd15938484d64871981d45a9dd74efe`|原确认批不确定性分析、解析假设和覆盖|
|PR107|`afafabbd2b7f8f25fe38ba99f539dab8baf2491c`|故障压力与独立噪声探索|
|PR108|`41ba0d3a6e69897ef6330cc9ad218253c7fb80ea`|补充的43200既有结果覆盖分析|
|PR109|`c51411433d30dc379bd69cf5fb20a11e196b7182`|本分支固定开发起点；先验机制与真值处线性诊断|

PR108使用独立detached checkout `/home/ubuntu22/uwb-midterm-technical-c-pr108-readonly` 读取，没有提交或修改。固定PR109不含PR108新增目录，不能只读本分支误以为补充材料不存在。GitHub状态的实查记录见 `notes/ENVIRONMENT.json`；PR106–109在本次检查时已合并，但来源仍锁定上述已审查提交，并非假定合并或使用最新主线。

## 编辑与编译

可编辑正文分片在 `sections/`；用 `build_report.py --assemble-only` 合并成完整Markdown，避免手工修改合并文件后被覆盖。`TECHNICAL_REPORT_ZH.tex` 是交付的完整可编辑LaTeX源码，`typeset/report-template.tex` 是简洁中文模板。固定仓库未找到适合本报告的LaTeX模板，因此新建此模板，没有改写会议论文。

依赖：Python3、Pandoc 3.14、Tectonic 0.17.0（或XeLaTeX）、Noto Serif/Sans CJK SC 和 DejaVu字体。首次Tectonic构建需要下载TeX依赖；已缓存后可复用。

```sh
cd docs/research/midterm_technical_draft_c
python3 build_report.py --pandoc pandoc --engine tectonic
# 或使用已有XeLaTeX环境，两遍编译由脚本执行
python3 build_report.py --pandoc pandoc --engine xelatex
# 只编译已交付的可编辑源码
tectonic TECHNICAL_REPORT_ZH.tex
# 证据、路径、公式/数字锚点、目录边界检查，不调用定位器
python3 verify_delivery.py
```

所有图均从本目录相对路径读取；完整矩阵使用原始固定提交链接或本目录必要副本定位。编译不需要ROS，不导入定位脚本，不触发历史读回脚本里的任何运行命令。

## Overleaf上传包

`OVERLEAF_PROJECT.zip`包含main.tex和图片，可上传为新项目，选择XeLaTeX。与本地已编译源码一致；尚未登录或验收Overleaf远程环境，不需要在聊天中提供账号密码。

## 必须保留的解释边界

B2只增广指定候选链路的单一常值偏差。真值线性化、真实噪声协方差、正确先验中心和B3均为理想诊断。每条件seed数与方法调用数分开，车辆、时刻、初值与配对模型不增加独立样本。95%/99%经验覆盖不是罕见风险保证；点覆盖与轨迹全覆盖不同。数值未接受与奇异传播块保留。现有室内证据及简化仿真不构成月面验证，也未完成PL/HCPL/HMI保证。

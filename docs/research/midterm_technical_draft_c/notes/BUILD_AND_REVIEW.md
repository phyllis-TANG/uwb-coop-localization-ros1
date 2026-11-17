# 编译与最终审查记录

日期：2026-11-17。正文由sections/三文件合并，使用Pandoc 3.14和Tectonic 0.17.0实际编译。工具位于临时目录/tmp/midterm-c-typeset，没有改动项目依赖、ROS或实验代码。正文约18–22页目标已满足：**技术正文20页，封面1页、目录2页，总23页A4**。

## 实际检查

- LaTeX最终编译退出0；无Overfull、Missing character、undefined或TeX错误，中文标题、行内/展示公式和目录可提取。
- Tectonic仅提示读取系统字体绝对路径，表示跨机器复现需要相同字体；不是缺字。字体为Noto Serif/Sans CJK SC、DejaVu Serif/Sans/Mono。
- 初始排版中的表格宽度、长英文条件换行、重复章节编号和PDF页锚点已修复；中间caption包兼容性错误已移除，最终使用简洁标题宏重新编译成功。
- PDF检查23页，正文页码1–20；抽查正文系统模型/公式页与先验结果表页，图像源另经独立目视核验。正文表格跨页保留续表表头，不截断数据。
- 55条CLAIM来源路径均在固定提交存在；20份表图副本与Git对象逐字节相同；合并Markdown与sections严格一致；两处正文图片引用存在。
- `evidence/verify_sources.py`直接解析保存CSV/JSON核查代表数值与完整行数，PASS；没有重新求解、产生观测或重采样。
- 独立技术审阅见INDEPENDENT_REVIEW.md；包含静态12个显示值、先验12个MSE/24格覆盖、m28/n32及公式/图注核查。
- 改动仅在指定新增目录，补充PR108 checkout状态干净、HEAD未变；原工作区未改动。
- OVERLEAF_PROJECT.zip完整性检查通过，main.tex与交付LaTeX逐字节相同，包含4张图片和上传说明。本地已编译；没有登录Overleaf或取得用户账号，远程环境未验收。

## 重现命令

```sh
python3 build_report.py --pandoc pandoc --engine tectonic
python3 verify_delivery.py
python3 evidence/verify_sources.py
```

验证脚本读固定来源与保存表，不导入定位求解器。完整机器检查在DELIVERY_CHECKS.json及evidence/NUMERIC_READBACK.json。本记录验证的是技术初稿与证据的一致性，不把旧仿真重新包装为新验证。

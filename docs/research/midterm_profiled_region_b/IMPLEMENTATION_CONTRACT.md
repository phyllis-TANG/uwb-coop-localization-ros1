# 实现与来源合同

本轮只新增指定两个目录。只读调用PR124 interval.py/invert.py/check.py/inputs.py；冻结清单记录这些依赖SHA。不复制或修改历史定位器。数学路线来自PR124完整噪声事件反演；PR123说明驻点接受和仿射局部区域不能解决全局非线性分支问题，本轮因此直接在原距离模型反演。

- OLD：原PR124三维搜索器（历史已知偏差四例为二维），原上下界、分割和保守中止逻辑。
- PROFILED：同搜索骨架，域只含XY；新的严格profile上下界，使用原B整个区间。
- certificate.py：独立Fraction距离到区间计算，逐叶认证，完整树父子域覆盖检查；旧方法用PR124独立Fraction验收。
- profiled.recover_bias：固定位置可行b的内/外包。`FEASIBLE_PROVED`仅内区间非空，`EMPTY_PROVED`仅外区间空，其他情况未决；输出不是某个选优b。
- execute.py：阶段二门槛、2小时总预算、attempt/身份/独占、原八例只读复用、分项计时。
- readback.py：不调用搜索器，核对冻结源/输入/输出哈希、所有证书、完整分母和投影/偏差恢复。
- inventory.py：对任何中断目录独立列出计划与未完成状态。
- analyze.py：全部成本和分母，按seed配对，不剔除失败后宣称加速。

可信算术条件：Python任意精度整数及Decimal/Fraction实现正确、有效有限输入、正sigma、固定有界X/B及本轮独立噪声结构。原平方根10³⁵上下界和checker10⁴⁵上下界保留。普通float仅用于计时、绘图与统计，不参与排除或包含判定；阈值是精确十进制9.488。异常留未知，不加ridge。

独立venv使用Python3.10.12及系统包；核心不需SciPy。NumPy2.2.6仅用于冻结Gaussian输入和bootstrap；Matplotlib3.10.8只用于图。代码未引入外部优化器或新的开源集合反演库。来源库许可证沿PR124 SOURCES：Python PSF/libmpdec BSD、NumPy BSD-3-Clause、Matplotlib基于PSF。源版本与环境文件哈希在ENVIRONMENT及FREEZE_MANIFEST。

输入表是实际执行来源。CONFIG描述矩阵、阈值、预算及统计设置；准备脚本把这些写入冻结INPUTS，执行时不再重新抽噪声。采用相同XY分辨率不代表两个有限外包精度完全相同，所以同时报告面积界、半径及未决盒，并明确旧b分辨率。

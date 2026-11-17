# 来源、版本和使用边界

本轮重新核对原始全文关键段落，没有只依赖PR118摘要：

- Nicola & Jaulin，*Guaranteed nonlinear parameter estimation with additive Gaussian noise*：[作者17页全文](https://webperso.ensta.fr/jaulin/paper_region.pdf)，§2、式(1)–(7)，完整噪声向量白化与球事件反演；2020书章DOI [10.1007/978-3-030-31041-7_19](https://doi.org/10.1007/978-3-030-31041-7_19)。本轮访问的是仍带2018模板的作者稿，不冒充正式出版版。核对全文服务中的原文；直接下载该PDF失败，未伪造PDF哈希。没有采用§3的Hessian协方差措辞或高维卡方近似。
- Jaulin & Walter (1993)，*Set Inversion via Interval Analysis for Nonlinear Bounded-error Estimation*，Automatica 29(4):1053–1064：[期刊排版全文](https://webperso.ensta.fr/jaulin/paper_automatica93.pdf)，§3.3自然包含扩张与舍入、§5算法及式(36)内外包含。作者托管PDF已下载到Git外并记录SHA256。本文不是其高维性能复现；本轮独立推导在预算停止时保留队列的有限步不变量。
- [Python 3.10 Decimal官方文档](https://docs.python.org/3.10/library/decimal.html)：Context向负/正无穷舍入、精确字符串构造及异常规则。平方根和阈值改用整数/有理数证明，不依赖未经认证的float sqrt或scipy chi2.ppf。

以上借鉴理论，不复制外部SIVIA源码。interval.py/invert.py为本轮小实现；可信核心仅依赖Python标准库decimal、fractions和math.isqrt。CPython/标准库为PSF许可证，libmpdec为BSD风格许可证，具体版本及二进制文件哈希见ENVIRONMENT.json。NumPy（BSD-3-Clause）只用于非认证局部仿射直接解；Matplotlib（基于PSF的许可证）只用于绘图，不参与剪枝/保证。没有安装Codac、IBEX或引入其模块，不宣称得到第三方软件认证。

固定仓库来源：PR118的METHOD_OPTIONS、THEORY_AUDIT；PR119的REPORT、PROTOCOL内数学定义（不存在独立MATH.md）；PR121的REPORT、MATH。均从共同起点f9c27436836b814afdea47945887015dcb55fca5读取，来源文件SHA记录在冻结清单。PR119说明有限初值不能排除未发现分支；PR121的局部候选不能代替本轮全域包含。

本轮MATH中四维卡方阈值的有理数证书、输入表示裕量、具体距离区间、队列保留不变量、投影面积界与顶点半径为本轮实现对应的推导，不能归称原论文已经证明了当前平台安全。

# 查证记录

访问日期 2026-11-17。只使用官方文档、作者仓库/论文和固定本地代码；外部链接用于解释，不在线动态改变冻结输入。

|问题|来源/版本|采用方法、验证与边界|
|---|---|---|
|LuSNAR生成背景与许可|https://github.com/zqyu9/LuSNAR-dataset ；https://arxiv.org/abs/2407.06512|明确是合成Unreal/AirSim数据；只发现Moon_1本地序列；README学术引用和商业联系条件保留；尝试main/LICENSE返回404，不据此虚构许可全文|
|坐标/地形与天线|固定PR125及开发基线 sim/isaac_lab/moon1/README.md、prepare_moon1.py、antenna_geometry.py|C=diag(1,-1,-1)，源点投影后再转换；det/单位/杆臂方向检查；世界竖直杆不是完整姿态外参|
|求解终止与尺度|https://docs.scipy.org/doc/scipy-1.15.3/reference/generated/scipy.optimize.least_squares.html ，与安装1.15.3一致|trf、显式x_scale，两次预定调用；第二阶段ftol=None禁用cost终止；仍按独立梯度门槛拒绝未驻点结果，不用success独立宣称通过|
|GPU是否可实际执行Isaac|https://docs.isaacsim.omniverse.nvidia.com/latest/installation/requirements.html （访问时latest）|本地IsaacSim6.2.0.0/Lab3.0.0；nvidia-smi失败、torch cuda_available=False。保留CPU定位与USD导出，Isaac实际渲染/物理未执行；未修改驱动|
|USD尺度|https://openusd.org/release/api/group___usd_geom_linear_units__group.html |显式设置metersPerUnit=1和Z-up，CPU pxr重新打开文件核对。仅运动学timeSamples，不等同Isaac执行|
|AR1同边际方差|递推直接推导Cov=σ²ρ^|i-j|，不依赖额外第三方参数|100000条开发创新样本验证，最大单位方差协方差误差见DEVELOPMENT.json；rho=.8是假设|

不采用网上未匹配车型的质量、惯量、摩擦参数；程序示意车与真实PR130小车分开。没有可用GPU或经匹配证据支持的动力学模型，本轮不执行接触冒烟，不调摩擦来追求预期结论。

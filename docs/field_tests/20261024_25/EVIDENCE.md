# 安装与参考视频的视觉留证

这些JPEG是为仓库阅读而生成的缩小预览，已移除元数据；**不是原始标定图像，不能用其像素直接替代原4K帧做精度计算**。
来源、原文件SHA256、原尺寸、预览尺寸及预览SHA256在[evidence/provenance.json](evidence/provenance.json)。
完整视频使用manifest中的Release附件。安装人工读数与不确定项使用geometry.json，不从透视照片反推厘米值。

| 文件 | 内容与用途 |
| --- | --- |
| [car1_side.jpg](evidence/car1_side.jpg) | Car1侧上方安装；黑框中心37cm、天线17cm为操作员读数 |
| [car1_top.jpg](evidence/car1_top.jpg) | Car1近俯视安装与图案/车体相对方向；不以照片证明精确轴向或水平 |
| [car2_marker_crop.jpg](evidence/car2_marker_crop.jpg) | IMG_7365.MOV约5秒原4K帧局部裁切；标记承载面有弯曲迹象，需排查平面模型及检测 |
| [reference_contact_sheet.jpg](evidence/reference_contact_sheet.jpg) | 八段参考视频各四个时刻的构图及默认ArUco抽样检测概览 |

Car1视觉ID0在参考抽样中可检测；Car2视觉ID1尚未通过提取检查。检测失败不等于压缩包损坏，
板面弯曲也不是由一张图片就已证明的唯一失败原因。先检查已有原片与替代提取方案，
再由独立检查点决定能报告何种精度；当前不要求现场重录。

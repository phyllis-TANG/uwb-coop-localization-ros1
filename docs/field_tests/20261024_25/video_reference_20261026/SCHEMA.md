# B端输出解释

- SI单位；epoch ns字符串，视频PTS整数和有理time_base；未知JSON为null、CSV为空。
- 主观测：encoded_pixels，角点按ArUco字典规范方向顺时针0–3，不是屏幕左上角排序。detected=1只用于自动解码；tracked=1仅跟踪；失败保留空角点和原因。
- reference片中未出现/不应出现的另一辆车标not_applicable，不计检测有效率。异常身份仍保留质量标志。
- manual_timing_*独立文件只供时序探索，人工角点顺序为暂定，不用于PnP/位置精度；其失败也保留。
- T_room_camera将相机光学坐标映至右手room；相机x向右/y向下/z向前，room z向上。候选与已批准矩阵分开，未知协方差不置零。
- 视频显示矩阵遵守PyAV的逆时针角度；IMG7337=-90，编码3840x2160、显示2160x3840。未拉伸竖幅，未直接把编码K用于旋转后图像。
- time_mapping.model=null为未批准；candidate_model或candidate_offset_family均非已验收时钟。单边界无法测漂移或消除阶段歧义。
- P用于暂定房间关系；Q仅作名义检查，不参与拟合。没有经独立尺量验证的误差值，不插值制造连续真值。

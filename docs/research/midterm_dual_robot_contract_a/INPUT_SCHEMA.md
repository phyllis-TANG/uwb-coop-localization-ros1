# 机器接口

input.schema.json、output.schema.json提供结构；core.validate/check执行更强身份、精确算术、树与语义检查。JSON重复键由check.read_json拒绝。规范化哈希为UTF-8 JSON、sort_keys=True、separators=(',',':')、ensure_ascii=False；input_hash排除其自身字段。不得把文件字节SHA与规范化输入哈希混淆。

输入包含schema_version、model_id、state_order、measurement_ids、anchor_map、bias_incidence、domains、observation_intervals、noise_model、threshold_certificate、arithmetic_policy、budget、input_hash、source_commit，以及case_id/units/frame/epoch/antenna_reference/representation/position_prior/motion。未知顶层字段拒绝以防真值泄露。预算100001个已处理节点、120秒、位置请求分辨率1/8m、偏差请求分辨率1/20m；强制小预算例max_nodes=1。实际根域相同，预算不是按真值裁剪。

输出：schema_version,input_hash,source_commit(共同起点),mode=5d/4d/no_peer,measurement_ids,threshold_certificate,root,nodes,queue,projections,counts,status,domain_contact,internal_semantics,bias_recovery,cost。
节点id唯一；box有理闭区间；kind=SPLIT/OUTSIDE/INSIDE/UNDECIDED/PENDING。SPLIT附axis(零基)、cut、children=[左ID,右ID]；不允许零宽轴切分。保存lower/upper仅供诊断，检查器不信任。叶列表输出顺序决定queue和projection矩形顺序；检查器精确核对该顺序，不接受静默遗漏。
projections由core.projections规定：每车rectangles=[{leaf,box}]，center、radius、radius_squared、area_upper；空集前三项null，面积0。
counts包括五种kind；processed_nodes=全部节点数−PENDING数，必须≤max_nodes；cost还有search_seconds、certificate_write_seconds、peak_rss_bytes（有理字符串），distance_evaluations（非负整数）。时间/RSS只能核查非负与归档身份，不能从证书独立证明测量真实；原始计时日志应一并归档。证书读回时间由A另记，不替换B原始成本。
bias_recovery是零个或多个{point:[四位置坐标],result:core.recovery返回值}；可选，不提供时不得声称完成偏差恢复数值展示。B正式4D记录建议至少一个按数据选定域内点，不能由真值选支。

RESULTS_READY接口见results_ready.schema.json。files为相对文件路径→SHA256字典，archive_hash=digest(files)，不包括RESULTS_READY自身，避免自引用。source_commit是B完整Git SHA，不是A起点；记录stage、records。每阶段每输入恰好三模式；即使失败/未运行也必须有记录与reason。证书source_commit字段仍为A共同起点，B代码身份通过外层manifest锁定。

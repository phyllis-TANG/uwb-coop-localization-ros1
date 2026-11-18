# 证书格式与检查入口

`preprocessing.schema.json`、`composite.schema.json`定义结构；`contract.py`实施全部数值、身份、量词和闭集语义检查。JSON数字量用精确有理字符串（整数/分数/有限十进制；时间允许科学计数法），不接受浮点证书端点。JSON重复键拒绝。哈希沿冻结K.digest：UTF-8、sort_keys=True、紧分隔符、ensure_ascii=False。

预处理对象：schema_version=DUAL-P4-PRECONTRACT-V1、source_contract_commit=50b592fbd672a1f19075147f53061a5861b3b892、original_input_hash、measurement_ids、original_domain(四维)、range_enclosures、directions(恰8)、contracted_domain(四维或null)、status、budget、cost。

range_enclosures按p/s各4行，含measurement_id/rho_upper/lower/upper。检查器从当前原输入逐项重建；混用另一车观测或方差会拒绝。

方向固定顺序：p_x_min,p_x_max,p_y_min,p_y_max,s_x_min,s_x_max,s_y_min,s_y_max。每项含id/car/axis(0或1)/sign(−1下或+1上)/status/original_endpoint/candidate_endpoint/adopted_endpoint/proof/reason/elapsed_seconds。原端点与输入逐方向一致，采用值由检查器算出，不能自行填更窄数。

CERTIFIED必须有proof且单方向记录耗时≤.5秒。回退状态为FALLBACK_TIMEOUT、FALLBACK_UNCERTIFIED、FALLBACK_ERROR；proof=null；candidate_endpoint可记录被丢弃的值或null；adopted_endpoint必须原值。耗时只是运行者记录，不是数学外界证明。

proof字段恰为kind=rational_support_v1、linear、balls、residual、support_upper。linear项为row_id/weight，weight非负。可用行ID：`p:pair:a0:a1`（全部12个有向pair）、`p:domain:0:+`（axis=0/1, ±）、`p:ball_axis:a0:0:+`（4锚点×2轴×2符号）；s同理。行ID必须属于当前方向车辆。ball_axis是单位方向球支持的不等式，不是未经证明的球切线。

balls项为anchor_id(a0…a3)、vector=[w_x,w_y]、t；检查精确t≥0及t²≥w_x²+w_y²。多个球项可合成；同一球需先合并，禁止重复ID造成不清楚来源。residual必须等于v−Σλc−Σw；support_upper必须等于带原域支持修正的H。success、普通原始可行点、浮点最优值均不能替代这些字段。

非空状态BOX_CERTIFIED，contracted_domain恰等于八采用值组成的闭盒；空状态EMPTY_PROVED仅在八端点有严格交叉时可用，contracted_domain=null。退化宽度0允许。

复合对象字段恰为schema_version、original_input_hash、preprocessing、preprocess_hash、restricted_input_hash、search_certificate。search_certificate使用原V2格式、mode=4d、原阈值；根必须等于按证书推导的域，其input_hash为受限输入新哈希。所有非域字段沿原输入保持。预处理证空时后两字段必须null。

API：verify_preprocessing(original_input, pre)、restricted_input(original_input, pre)、check_composite(original_input, composite)。通过返回accepted=true和可读方向原因；拒绝抛ValueError子类。CLI返回accepted=false/reason并exit 1。check_composite的状态COMPOSITE_OUTER_CERTIFIED说明包含，原树的预算/空集状态仍见tree.status，不宣称全部盒达到分辨率。

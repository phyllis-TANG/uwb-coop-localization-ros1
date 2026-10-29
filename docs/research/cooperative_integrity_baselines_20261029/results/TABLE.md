# 固定主轨迹的强基线对照

仅seed101受控复现，非原归档读回；AL是假设值；未作罕见风险认证。

|场景|车|监测|分母s|AL m|报警s|unknown s|可用s|越限s|HMI s|
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
|nominal|car1|B0|63|0.1|0|2|61|2|0|
|nominal|car1|B1_local|63|0.1|0|2|61|2|0|
|nominal|car1|B1_network|63|0.1|0|2|61|2|0|
|nominal|car1|B2_local|63|0.1|0|2|61|2|0|
|nominal|car1|B2_network|63|0.1|0|2|61|2|0|
|nominal|car2|B0|63|0.1|0|2|61|2|0|
|nominal|car2|B1_local|63|0.1|0|2|61|2|0|
|nominal|car2|B1_network|63|0.1|0|2|61|2|0|
|nominal|car2|B2_local|63|0.1|0|2|61|2|0|
|nominal|car2|B2_network|63|0.1|0|2|61|2|0|
|car1_common_wall_bias|car1|B0|14|0.1|0|0|14|11|11|
|car1_common_wall_bias|car1|B1_local|14|0.1|0|0|14|11|11|
|car1_common_wall_bias|car1|B1_network|14|0.1|0|0|14|11|11|
|car1_common_wall_bias|car1|B2_local|14|0.1|8|0|6|11|3|
|car1_common_wall_bias|car1|B2_network|14|0.1|8|0|6|11|3|
|car1_common_wall_bias|car2|B0|14|0.1|0|0|14|3|3|
|car1_common_wall_bias|car2|B1_local|14|0.1|0|0|14|3|3|
|car1_common_wall_bias|car2|B1_network|14|0.1|0|0|14|3|3|
|car1_common_wall_bias|car2|B2_local|14|0.1|7|0|7|3|0|
|car1_common_wall_bias|car2|B2_network|14|0.1|8|0|6|3|0|
|peer_bias|car1|B0|14|0.1|14|0|0|7|0|
|peer_bias|car1|B1_local|14|0.1|0|0|14|7|7|
|peer_bias|car1|B1_network|14|0.1|0|0|14|7|7|
|peer_bias|car1|B2_local|14|0.1|11|0|3|7|0|
|peer_bias|car1|B2_network|14|0.1|11|0|3|7|0|
|peer_bias|car2|B0|14|0.1|14|0|0|10|0|
|peer_bias|car2|B1_local|14|0.1|0|0|14|10|10|
|peer_bias|car2|B1_network|14|0.1|0|0|14|10|10|
|peer_bias|car2|B2_local|14|0.1|11|0|3|10|0|
|peer_bias|car2|B2_network|14|0.1|11|0|3|10|0|

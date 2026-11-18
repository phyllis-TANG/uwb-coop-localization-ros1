# 给B的固定SHA接入说明

本轮只交付A的数学/格式/独立检查，未启动NEXT_PERFORMANCE_EXPERIMENT的7例×两组实验。B应从READY.json取implementation_commit，按完整40位SHA读取本轮文件及原core.py/checker_v2.py，验证file_hashes。不要用旧PR是否合并作为读取固定对象的障碍。

建议流程：

1. 保留原P4输入x及input_hash。可以用propose.py产生候选，也可由B求解器提供有理乘子；都必须先经verify_preprocessing验证。
2. 得到预处理p后用restricted_input(x,p)生成y。若返回None，前半段已证原域空，按空复合封套返回；不启动搜索、不制造零半径。
3. B沿原搜索器使用y的四位置域作为根；q9、原9观测、variance、B、0.05m搜索规则、50000盒/30秒及总120秒/1GiB均保留。原A输入中的1/8请求分辨率及100001上限也不得静默替换，B已有更严设置沿其冻结协议处理；本接口没有增加预算许可。
4. 为树构造原A格式certificate，绑定y.input_hash、mode=4d。建议让原a_bridge使用case['a_input']=y，其余原观测/阈值完全不变。不能把旧原域hash塞给小根树。
5. 复合封套绑定x.input_hash、K.digest(p)、y.input_hash及该certificate，调用check_composite(x,envelope)。任何检查失败都不能交付已缩域结果；应保留失败记录，若任务允许回退则重新使用原域方案，不能把失败证书标成功。

未知方向回退可以在搜索前独立执行，其余已认证方向仍可用。propose.py默认最多每方向.5s、总4s，超时将该方向部分候选全部丢弃。计时检查在枚举产出/结束/采用前进行，单次大整数操作不可抢占；它是协作式软截止，非操作系统硬实时承诺。B应将前处理、独立认证、搜索、树认证、投影和I/O成本分别纳入原总预算，外层进程限时负责硬截止。硬中断无完整预处理证书时不能采用未认证域。

如果整个前处理记录超过4秒，数学包含与成本合规分别返回：cost_within_declared_total=false，不能据证书数学通过声称实验预算通过。某方向耗时超过.5秒却仍标CERTIFIED会被拒绝。静态证书不能独立证明历史计时真实。

调用示例：

```sh
python tools/midterm_dual_robot_contract_a/precontract_v1/propose.py INPUT.json PRE.json
python tools/midterm_dual_robot_contract_a/precontract_v1/contract.py pre INPUT.json PRE.json
python tools/midterm_dual_robot_contract_a/precontract_v1/contract.py derive INPUT.json PRE.json > RESTRICTED_INPUT.json
# B在这里运行其已冻结的P4搜索并组装COMPOSITE.json；A不在本交付运行该步骤。
python tools/midterm_dual_robot_contract_a/precontract_v1/contract.py composite INPUT.json COMPOSITE.json
```

Python入口可按文件路径importlib加载contract.py；内部显式路径加载冻结V2/core，避免与B的同名模块冲突。仅标准库。原V2_READY与全部冻结文件保留，未增加随机样本、先验或车间偏差候选。

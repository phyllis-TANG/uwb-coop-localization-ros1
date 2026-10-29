# 交接：第一轮已完成，不自动续跑

工作树 /home/ubuntu22/uwb-history-recovery-minimal-20261029；分支 analysis/20261029-history-recovery-minimal；起点main ad99174c4f5b111e3e14ce7c2fe56b200c56e794。原STATIC-TO-METHOD工作树不改。已有rosmaster/rosbag不操作。机器余量约14GB，沿用既有venv，无安装。未发现本树及上级适用AGENTS；云环境状态工具和network-policy文件不可用，不据此假定授权，使用已有Git远端正常鉴权。

完成：10个归档单元SHA复用、2新回放、8快照、1前缀合同、6组派生发布（2条件×3），全部预登记。没有失败单元或漏项；不存在新seed/动态/真实包。REPORT给结论；主要新证据是历史prior影响与初值效应分离。未建立新的硬约束或可信判断机制必要性。不要把这个归因干预改写为在线回滚算法胜出。

复现与读取见COMMANDS.md、ARTIFACTS.json。原PR72归档SHA保持50c671e3687c3342b8abe99986ecd6a6488de23e24fe112b16b44d9f8fb3f320，本轮只读。大证据在独立Git外目录。本机NAS路径只读检查返回Host is down；没有上传、重试、修改网络或要求凭据。新归档已在本机保留，远端可取得性尚未建立；这不影响已提交紧凑逐时刻数据/快照数值的查看，不伪称NAS已备份。

下一步需讨论具体用途合同，暂不自动运行：若只要求相对I的XY预算，简单发布投影已能表达；若要求yaw、相对几何、内部历史恢复，须先给独立用途依据与同信息基线，再另登记。实测可信角色判定仍继承PR77的G3边界，不增加采集。本轮草稿PR不自动合并，不改其他PR。

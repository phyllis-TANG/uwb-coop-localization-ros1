"""Package complete saved stages and generate the final factual summary."""
import gzip,csv,subprocess,platform
from fcommon import *

def deliver(batch,recovery):
 batch=Path(batch);recovery=Path(recovery)
 with (DOC/'results_p2/NUMERICS.csv').open() as f:num=list(csv.DictReader(f))
 with (DOC/'results_p2/P1_TO_P2.csv').open() as f:changes=list(csv.DictReader(f))
 check=read(DOC/'results_p2/READBACK.json');ok=[r for r in num if r['accepted_stationary_fullrank']=='True'];bad=[r for r in num if r['accepted_stationary_fullrank']!='True']
 payload={}
 for label,path in [('batch',batch),('recovery',recovery)]:
  for p in sorted(path.rglob('*.json')):payload[label+'/'+str(p.relative_to(path))]=read(p)
 archive=DOC/'portable.json.gz'
 with archive.open('xb') as b:
  with gzip.GzipFile(fileobj=b,mode='wb',mtime=0) as f:f.write(json.dumps(clean(payload),separators=(',',':'),allow_nan=False).encode())
 manifest={'archive_sha256':digest(archive),'archive_bytes':archive.stat().st_size,'archive_json_files':len(payload),'original_batch_commit':read(batch/'RUN.json')['commit'],'recovery_commit':read(recovery/'RUN.json')['commit'],'report_generation_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'python':platform.python_version(),'numpy':np.__version__,'scipy':__import__('scipy').__version__,'total_optimizer_calls':check['total_calls'],'formal_runs':0,'result_hashes':{str(p.relative_to(ROOT)):digest(p) for folder in ['results','results_p2'] for p in sorted((DOC/folder).glob('*')) if p.is_file()}}
 write(DOC/'DELIVERY.json',manifest)
 lines=['# 五包实测处理完成报告','',f'本批五包的数据审计、四动态包全段四模型比较与数值恢复均已完成；16个全段最终结果中{len(ok)}个通过“求解器成功＋物理梯度≤1e-5＋局部满秩”，{len(bad)}个未通过，全部保留。处理完成不等于所有数值结果接受，更不等于具备连续真值。','', '## 实际完成','', '- 五包原bag与便携归档逐字段一致；33/93/56/108/113个固定网格时刻分别对应013206/015334/033248/050447/045116。原始消息、边界、方向缺测、插值跨度和时间差均有记录。','- 静态013206完成几何与方向差审计，因它参与过历史墙校正，不作为独立定位验证。其两方向原测距中位数比人工几何分别大0.26047m和0.31147m。','- 四动态包F0/F1/F2/F3全段对照完成，所有方法共享输入/校正/初始化。F2自由常偏差、F3自由线性趋势，均不读取故障标签。','- 旧六短窗统一继续一次后6/6通过梯度门槛，最大天线变化约0.103mm，主要是停止条件与验收不一致；旧端点仍保留。',f'- 原批38调用、统一恢复16调用，合计{check["total_calls"]}，formal_runs=0。原批P1只有8/16接受，P2结果单列；没有把追加恢复伪装成原协议内执行。','- 每阶段独立残差算术与方向Jacobian、完整目标/梯度/数值状态、计数和来源哈希读回通过。最终零求解器复核残差最大差'+str(check['max_independent_residual_difference'])+'，方向Jacobian最大差'+str(check['max_independent_directional_jacobian_difference'])+'。','', '## 全部最终状态','', '|包|方法|梯度无穷范数|P2评估次数|数值接受|peer扣偏差后RMS/m|','|---|---|---:|---:|---|---:|']
 for r in num:lines.append('|'+ '|'.join([r['case'],r['method'],format(float(r['gradient_inf']),'.3g'),r['nfev'],'通过' if r['accepted_stationary_fullrank']=='True' else '未通过',format(float(r['peer_corrected_rms_m']),'.5f')])+'|')
 lines += ['', '残差RMS是拟合诊断，不是位置精度。方法自由度不同，较低残差也不直接代表更好预测或更高安全性。所有未接受项在CSV保留，不把误差填零。', '', '## 数值与可辨识性', '', '一静一动两包P1最弱信息方向超过99.9%集中在静止车yaw，缩放条件数约7.6e3—3.5e4；双动两包约1.2e3—1.4e3。短静态切片能呈现精确秩亏；全段噪声拟合产生的微小运动可能让机器阈值下满秩，但不形成强实测朝向信息。没有强加朝向先验掩盖该缺口。详见STATE_IDENTIFIABILITY及WEAK_MODES。', '', '## 与以前相同和不同的条件', '', '现在相同的是：来源可追溯、reference/measurements/estimates隔离、四模型配对、固定输入与求解预算、全部状态和失败可复算。不同的是：实测只有局部SE(2) odom/工程噪声/有限人工参考，Moon_1拥有受控轨迹与注入真值。实测全段目标移除了起点先验，且使用历史伪Huber测距；不能把两套数值横向混成同一统计试验。', '', '安装原始记录明确odom原点对应待核实；系统时钟状态是三机先后读取。没有从这些文件补造外参或同步标定。045116便携reference不含可追溯数值起终点，本批不借用050447；只在另外三包最终评价读取旧人工末点。末点差不是全程RMSE、不是正式风险验证。', '', '045116存在一个网格peer缺测，最大原odom间隔约1.637s/1.401s；本轮保留插值和缺测痕迹而非隐藏。两方向header/receipt差不是网络延迟或可直接应用的时钟修正。', '', '## 完整图与交付', '', '![全部四包四方法轨迹、残差和偏差](results_p2/full_batch.png)', '', '图保留所有方法，包含未接受项；应先看状态表再解释。F3的直线偏差只是模型假设，不是已证实真实故障趋势。', '', 'README给出零优化器解包和复核命令，DELIVERY记录归档与结果哈希、两个运行前冻结提交和版本。原始batch/recovery均只读，所有attempt均有端点。代码与历史结果未改写，无需再重复处理原bag。']
 (DOC/'REPORT.md').write_text('\n'.join(lines)+'\n')
 (DOC/'DECISION_MEMO.md').write_text('# 当前可以讨论什么\n\n本批数据已到“可追溯、四模型可比较、全部数值状态可复核”的处理终点。可以讨论实测残差时间结构、常偏差/线性趋势能吸收多少不一致、逐车估计变化及弱激励；不能讨论有真值支持的全程精度改善、覆盖率或月面风险保证。\n\n本批不再增加包、自动调参或扩大网格。所有最终未通过项保持失败标记。下一次决策应先看全段结果和观测合同，再决定是采用更适合静止车辆的状态定义、补实际外参与同步证据，还是准备有连续真值的独立验证。该决策不在本次自动启动。\n\n未知的安装原点/同步/连续真值需要实际证据，不能通过软件清洗达到Moon_1理想条件。更多同轨迹重复bag也不自动补足这些缺项。\n')
 print(json.dumps({'accepted':len(ok),'not_accepted':[r['case']+'_'+r['method'] for r in bad],'calls':check['total_calls'],'archive_bytes':archive.stat().st_size}))
if __name__=='__main__':deliver(*sys.argv[1:])

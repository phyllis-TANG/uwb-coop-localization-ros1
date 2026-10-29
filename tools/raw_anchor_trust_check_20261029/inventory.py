#!/usr/bin/env python3
"""Read pinned indexes/notes only; never opens bag/video bytes."""
import argparse,re
from common import *
SEP='docs/field_tests/20260927_FIELD_TEST_SUMMARY.md'
CONF='datasets/field_raw/provenance/user_confirmations_20261020.md'
# Each enrichment is a source-qualified correction, never a new bag acceptance.
SEPT={
'B001':'接口试录；未找到此条专属完整实验验收，话题仅文件名提示，不据此确认。',
'B002':'单链静态1.56m，聚合前；与B003不同录制时段，不隔离聚合收益。',
'B003':'单链静态1.56m，median后；原报告人工距离，不是房间XY。',
'B004':'单链静态1.5m首录，有效比例低约13.6%；保留采集诊断，不判文件损坏。',
'B005':'单链静态1.5m重复；报告有人工距离，不同录制不是独立几何。',
'B006':'单链静态2m；人工距离仅支持相应距离诊断。',
'B007':'单链静态3m；人工距离仅支持相应距离诊断。',
'B008':'单链2m人体遮挡，开录约1秒后进入；不能整包统一健康标签。',
'B009':'单链2m人体预置重复；与B008操作时序不同。',
'B010':'手推试录；没有此条独立终点或完整参考，不能从文件名补造。',
'B011':'手推试录，报告74.9秒与双向UWB；无连续位置真值。',
'B012':'手推重复试录；独立终点/完成证据未核实。',
'B013':'Car1旋转90度静态，人工间距2m；单次方向诊断。',
'B014':'名义2m文件；原ground_truth备注卷尺实为1.77m（约±0.01m）；不得按文件名2m算误差。',
'B015':'摄像无遮挡静态，原ground_truth备注1.85m（约±0.01m）；不是连续房间坐标参考。',
'B016':'两车相向静态，报告人工间距2m；不是四锚房间定位。',
'B017':'正式手推，Car2静止Car1推移，初始间距2m；报告双车UWB/Odom/IMU/电压，无TF或CMD；无连续真值。',
'B018':'静态接口包，报告5533条与两车UWB/Odom/IMU；无绝对XY。'}
EXTRA={
'B023':'失败尝试，无终点；已关闭的缺项不反复要求补旧终点。',
'B024':'手动反向L完成；旧安装N8缺测仅三墙，人工终点[3.17,2.60,0.20]。',
'B025':'低电中断/有cmd而odom不动属于实验执行问题，不等于文件损坏。',
'B027':'卷尺位移1.020m对应既定前进段；后段转弯，不能全包当纯直线。',
'B029':'0.950m来自前次摆放关系，非新卷尺独立参考。',
'B033':'自动L完成、N8缺测；人工终点[2.95,3.11,0.20]不是连续真值。',
'B036':'控制器完成转向；Odom角不是外部yaw真值，旧记录缺项已关闭。',
'B045':'P5原[1.5,4,1]更正为[2.02,4,1]；保留更正前备注。',
'B046':'与B045同一点重复，不是新增空间位置。',
'B047':'P15更正[2,3,0.20]，与P23重复点。',
'B048':'P1[2,2,0.20]曾用于旧Car2校正拟合，不能当其独立验证或跨日/跨车通用校准。',
'B050':'P4更正[3,3,0.20]，不再采用旧[3.5,4,0.20]。',
'B051':'充电桌面检查，位置未知，不作房间标定。',
'B052':'已完成L形但N10异常；不因误差大排除。',
'B053':'A点[2,2,0.20]来自用户条件确认和历史一致性，非独立测量认证。',
'B054':'005135单车正常完成包；不得当双车对照。',
'B055':'004023是N10异常但完成的单车包；必须保留，不因误差大排除。',
'B056':'延续015334终点摆放，非重新独立量测。',
'B057':'015334双车开发；Car1高度旧备注0.20m后确认0.17m；近似坐标/卷尺/跨车时钟有假设。',
'B058':'030837运动有朝向偏差，保留完成后的人工终点，不改称理想直线。',
'B059':'033248 aligned双车开发；空间与时间仍为候选，不能称已验收同步。',
'B060':'手动返回遇线缆，近似终点；旧精确X缺项已关闭，勿捏造。',
'B061':'几何推距约1.480m与卷尺1.55m并存，不能择其较吻合测距者。',
'B063':'人员经过时段只是候选解释，非文件损坏或已知故障标签。',
'B065':'0.707m来自坐标差推导，非独立卷尺。',
'B069':'人体进入有过渡，不能整包统一NLOS标签。',
'B070':'人体重复没有明显测距变化是有效反例，不强标故障成功。'}
HIST={
'043014':('setup_only','静态20秒接口核对','几何/安装与完整动作验收未给出'),
'060852':('stopped_acquisition_fault','Car2原始2015帧nodes为空；中止','采集链恢复证据；不能当正常重复'),
'065640':('historical_static','A点yaw270静态','实际天线位置/角度不确定度'),
'072418':('pilot_not_formal','20cm短L；缺Car1基础与Car2 UWB话题','不是完整双车回放输入'),
'063303':('recovered_separate_condition','连接恢复后的静态，卷尺1.83m；独立于故障首录','恢复前后条件差异，参考定义'),
'054116':('historical_static','C点静态；原笔记1.82cm单位未澄清','单位/距离定义；不能擅改为1.82m'),
'051322':('historical_controlled_action','T02静态人工遮挡：约0–40清、40–80墙N10、80–160清、160–200 peer、200后清','电子时标与实际影响未验收，动作不等于故障真值'),
'055701':('historical_static','返回A点静态，卷尺2.125m','回位差/参考不确定度'),
'072322':('pilot_not_formal','短L试录','该尝试完成程度未有独立验收'),
'071759':('pilot_not_formal','短L试录','该尝试完成程度未有独立验收'),
'050058':('historical_static','AB静态，卷尺2.08m；重复start事件不是两次实验','参考点/距离类型/不确定度'),
'064946':('historical_static','A点yaw000，卷尺2.11m','角度/安装和距离参考不确定度'),
'065307':('historical_static','A点yaw180，卷尺2.12m','旋转后杆臂位置变化/参考不确定度'),
'184047':('aborted_attempt_not_formal_T10','两次ABORTED，底盘未就绪；正式T10为184755 retry','保留失败执行；不能替换正式T10')}
PROHIBIT='不得作为连续轨迹真值/绝对误差保护界；不得以小残差/收敛/文件可读认证健康；不得把重复或同包窗口当独立随机试验'
def build(out):
 out.mkdir(exist_ok=False);s=Sources();cat=s.json('datasets/field_raw/catalog.json');flat=s.csv('datasets/field_raw/catalog.csv');m=s.json(DOC+'manifest.json')
 assert len(cat)==len(flat)==76 and {r['record_id']:r['sha256'] for r in cat}=={r['record_id']:r['sha256'] for r in flat}
 sources=[SEP,CONF,DOC+'geometry.json',DOC+'results/BAG_QC_REPORT.md',DOC+'video_reference_20261027/MISSING_EVIDENCE.md',DOC+'EXPERIMENTS.md',DOC+'RESULT_CONTRACT.md',DOC+'video_reference_20261026/README.md',DOC+'sandbox_20261026_takeover/README.md',DOC+'two_car_imu_fgo_20261028/STAGE_C_REPORT.md',DOC+'t10_reliability_bridge_20261027/REPORT.md',DOC+'imu_odom_audit_20261027/REPORT.md',DOC+'single_car_imu_fgo_eval_20261027/REPORT.md']
 for p in sources:s.read(p)
 for r in cat:
  for p in r['linked_support_files']:s.read('datasets/field_raw/'+p)
 for pr,files in {'pr71':['research_roadmap_20261028/README.md'], 'pr72':['cooperative_influence_probe_20261028/'+f for f in ['REPORT.md','METHODS.md','FROZEN_CONFIG.json','HANDOFF.md']]}.items():
  for f in files:s.read(DOC+f,REFS[pr])
 for pr,folder,files in [('pr73','c_scope',['C_SCOPE_ONE_PAGE.md','LAB_PRECHECK_20261030.md']),('pr74','b_method',['B_DECISION.md','B_ANALYSIS.md']),('pr75','a_evidence',['A_FACTS.md','ANALYSIS.md'])]:
  for f in files:s.read('docs/research/cooperative_followup_20261029/'+folder+'/'+f,REFS[pr])
 result=[]
 def row(**kw):
  base=dict(record_id='',inventory='',file='',date='',sha256='',data_kind='',record_integrity_evidence='',experiment_completion='',available_topics_actions='',reference_grade='',reference_detail='',development_holdout='',documented_exposure='',allowed_use='',prohibited_use=PROHIBIT,minimum_missing='',evidence_sources='',metadata_verified_this_round=True,bag_sha_recomputed_this_round=False,message_decoded_this_round=False,video_read_this_round=False,source_original_status='',source_original_limits='',review_scope='固定索引/原备注/历史报告核对；非本轮原始数据验收');base.update(kw);return base
 for r in cat:
  rid=r['record_id'];sep=rid in SEPT;detail=r['reference_status'];extra=SEPT.get(rid,EXTRA.get(rid,''));limits='；'.join(r['limitations'])
  # Explicit source-reviewed membership: negated words such as "没有独立卷尺" never grant grade B.
  b_ids={19,24,27,28,32,33,*range(37,51),52,54,55,*range(57,63),64,65,67,68,69,70}
  grade='S_模拟参考未核实' if r['data_kind']!='real' else ('B_candidate_人工离散参考未作保护界验收' if int(rid[1:]) in b_ids else 'C_or_unknown_无合格绝对参考')
  if rid in ['B029','B053','B056','B063','B066']:grade='C_推算或条件共享参考；非独立新量测'
  if sep and rid not in ['B001','B010','B011','B012','B018']:grade='B_candidate_人工距离非房间连续参考'
  integrity='历史归档记录：'+r['this_run_verification']+'；旧索引录制状态：'+r['recording_status']
  if r['previously_decoded_message_count'] is not None:integrity+='；历史解码条数='+str(r['previously_decoded_message_count'])
  if sep:integrity+='；另查9月27日报告（逐条补充仅按该报告，不把索引未审阅当损坏）'
  evidence=['datasets/field_raw/catalog.json#'+rid,'datasets/field_raw/catalog.csv#'+rid]+['datasets/field_raw/'+p for p in r['linked_support_files']]+r['evidence']
  if sep:evidence.append(SEP)
  if rid in EXTRA or r['date']=='20261018':evidence.append(CONF)
  action=r['experiment_description']+'；补充：'+(extra or '无新增完成判断')
  if sep:action+='；'+('仅单链UWB，无四墙定位证据' if rid in [f'B{i:03}' for i in range(2,10)] else '话题依原报告/原备注；不从文件名补造')
  allowed='；'.join(r['recommended_use'])
  if sep:allowed+='；可按上述独立报告补充做相应单链/接口/人工距离诊断，仍非新验收'
  result.append(row(record_id=rid,inventory='historical_catalog',file=r['filename'],date=r['date'],sha256=r['sha256'],data_kind='real' if r['data_kind']=='real' else 'simulated',record_integrity_evidence=integrity,experiment_completion=r['experiment_status']+'；'+(extra or '沿原索引，不新增成功判断'),available_topics_actions=action,reference_grade=grade,reference_detail=detail+'；'+extra,development_holdout='历史已暴露开发/接口；非未见验证',documented_exposure='索引/历史报告/备注已公开；未逐包追溯所有算法使用',allowed_use=allowed,minimum_missing=('模拟参数与实际真值话题身份' if r['data_kind']!='real' else '按拟使用口径恢复该包参考定义/安装/时间来源；'+('已有缺项明确关闭时只降级用途，不要求补造旧真值' if rid in ['B023','B030','B031','B036','B060','B063'] else '当前无连续合格参考；不妨碍已列诊断用途')),evidence_sources=' | '.join(evidence),source_original_status=r['recording_status']+' / '+r['experiment_status'],source_original_limits=limits))
 for r in m['formal_bags']:
  rid=r['id'];held=rid in ['T09','T11','T13','T15'];occ=rid in ['T14','T15'];reference=r['manual_reference']
  exposure='既有结构解码、视频解码/标记提取/候选时空处理已暴露；'
  exposure+=('受查交接未发现本包定位误差调参，但不能称完全未见' if held else '既有开发输入诊断；T08/T10有IMU输入审计；本轮不重复计算')
  if rid=='T09':exposure+='；手工终点曾作T10静止Car2初值候选，非未暴露参考'
  if rid=='T10':exposure+='；已有条件性reliability bridge回放，不等于当前F0空间/时钟验收'
  missing='天线实际XYZ/固定停点时段、横距或斜距、测量不确定度、全局初值/安装及时间映射来源'
  if occ:missing+='；遮挡起止/材质/对象/影响仍未知；包与视频已存在且解码，非欠录'
  evidence=[DOC+'manifest.json#'+rid,DOC+'results/BAG_QC_REPORT.md',DOC+'EXPERIMENTS.md',DOC+'video_reference_20261027/MISSING_EVIDENCE.md',DOC+'video_reference_20261026/README.md',DOC+'sandbox_20261026_takeover/README.md']
  if rid in ['T08','T10']:evidence.extend([DOC+'two_car_imu_fgo_20261028/STAGE_C_REPORT.md',DOC+'imu_odom_audit_20261027/REPORT.md'])
  if rid in ['T09','T10']:evidence.append(DOC+'t10_reliability_bridge_20261027/REPORT.md')
  result.append(row(record_id=rid,inventory='new_manifest_formal',file=Path(r['relative_path']).name,date='20261025',sha256=r['sha256'],data_kind='real',record_integrity_evidence='既有逐包SHA及全部schema解码PASS；'+str(r['expected_messages'])+'消息；媒体manifest已验收存在/解码；本轮仅元数据复核',experiment_completion='formal_completed；动作描述不是精度验收',available_topics_actions=r['condition']+'；'+','.join(r['topic_message_counts']),reference_grade='B_candidate_人工离散点未验收；C_轨迹诊断',reference_detail=str(reference),development_holdout='protected_whole_bag_holdout' if held else 'development',documented_exposure=exposure,allowed_use='既有结构身份核对；未来方法/参数冻结后另登记整包留出评价' if held else '输入/状态/条件性开发诊断；固定停点仅在参考条件明确后使用',prohibited_use=PROHIBIT+('；禁止本轮读取测量/误差或选择参数；不得称从未见过媒体/参考' if held else '；不得无批准坐标时钟而声称全局精度'),minimum_missing=missing,evidence_sources=' | '.join(evidence),source_original_status=str(r['acceptance_status']),source_original_limits='manifest.global_limits；参考uncertainty/距离类型等未知原样保留'))
 for i,r in enumerate(m['historical_and_fault_bags'],1):
  filename=Path(r['relative_path']).name;stamp=filename.rsplit('_',1)[-1].split('.')[0];status,action,missing=HIST[stamp]
  result.append(row(record_id='N_H%02d'%i,inventory='new_manifest_historical',file=filename,date='20261025' if stamp=='184047' else '20261024',sha256=r['sha256'],data_kind='real',record_integrity_evidence='manifest归档/成员身份与EXPERIMENTS历史内容记录；不套用8正式包311144消息完整schema验收，也不把采集故障当字节损坏',experiment_completion=status,available_topics_actions=action+'；具体话题覆盖见EXPERIMENTS，未列出不推定完整',reference_grade='C_诊断；人工量测如有仅B_candidate',reference_detail=action,development_holdout='historical_development_not_formal_repeat',documented_exposure='历史EXPERIMENTS/manifest已公开；本轮只读索引',allowed_use='采集/安装/静态或中止原因开发诊断；保留原条件，不冒充正式重复',minimum_missing=missing,evidence_sources=DOC+'manifest.json#'+r['relative_path']+' | '+DOC+'EXPERIMENTS.md',source_original_status=r['category'],source_original_limits='不是8个正式实验；参考/完成情况按具体行，不补造'))
 assert len(result)==98 and len({r['file'] for r in result})==98
 csvwrite(out/'DATA_USE_MATRIX.csv',result);dump(out/'SOURCE_INDEX.json',s.items)
 dump(out/'inventory_check.json',dict(rows=len(result),historical_catalog=76,new_manifest=22,formal=8,historical_new=14,real=sum(r['data_kind']=='real' for r in result),simulated=sum(r['data_kind']!='real' for r in result),held=[r['record_id'] for r in result if r['development_holdout']=='protected_whole_bag_holdout'],all_hashes_well_formed=all(re.fullmatch('[0-9a-f]{64}',r['sha256']) is not None for r in result),raw_bags_opened=0,videos_opened=0,source_original_verification_not_inherited_as_this_round=True,source_sha256={p.name:sha(p) for p in Path(__file__).parent.glob('*.py')}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);build(p.parse_args().output)

"""Fast existing-record audit; no bag, video, estimator, or held-out errors loaded."""
import csv,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];DOC=ROOT/'docs/research/reference_resolution_audit_20261029'
paths={
 'sept_notes':'datasets/field_raw/20260927/notes/live_field/TWO_CAR_PA0_PB1_static_LOS_camera_clear_facing_GT1p85m_20260927_063345_ground_truth.txt',
 'sept_report':'docs/field_tests/20260927_FIELD_TEST_SUMMARY.md',
 'repeat_stats':'docs/field_tests/20261010_11/source_notes/multipoint_link_diagnostics.txt',
 'repeat1_notes':'datasets/field_raw/20261011/notes/live_field/MOBILE_P1_h1p00_clear_R1_20261011_020429_survey.txt',
 'repeat2_notes':'datasets/field_raw/20261011/notes/live_field/MOBILE_P1_h1p00_clear_R2_20261011_020505_survey.txt',
 'forward1':'docs/field_tests/20261010_11/source_notes/CAR2_static_calibration_key_forward_check.txt',
 'forward2':'datasets/field_raw/20261011/metadata/live_field/CAR2_WALL_UWB_ODOM_IMU_key_forward_repeat_20261011_051810_independent_check.txt',
 'p1':'datasets/field_raw/20261017/notes/live_field/CAR2_P1_REINSTALL_STATIC_20261017_045257_notes.txt',
 'p4':'datasets/field_raw/20261017/notes/live_field/CAR2_P4_REINSTALL_STATIC_20261017_053806_notes.txt',
 'static_report':'docs/research/static_evidence_to_method_20261029/DECISION.md',
 'static_stats':'docs/research/static_evidence_to_method_20261029/COMPACT_RESULTS.csv',
 'geometry':'docs/field_tests/20261024_25/video_reference_20261027/T10_geometry_summary.json',
 'verify':'docs/field_tests/20261024_25/video_reference_20261027/verification.json',
 'operator':'docs/field_tests/20261024_25/t10_closure_20261027/operator_evidence.json',
 'reference_decision':'docs/field_tests/20261024_25/t10_closure_20261027/reference_decision.json',
 'missing':'docs/field_tests/20261024_25/video_reference_20261027/MISSING_EVIDENCE.md',
 'precheck':'docs/research/cooperative_followup_20261029/c_scope/LAB_PRECHECK_20261030.md',
 'prior_criteria':'docs/research/cooperation_cost_criteria_20261029/TOLERANCE_SOURCES.json',
 'simulation_identity':'docs/research/history_recovery_minimal_20261029/RUN_INDEX.json'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(name,value): (DOC/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def table(name,rows):
 with (DOC/name).open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def text(key):return (ROOT/paths[key]).read_text()
def obj(key):return json.loads(text(key))
def main():
 assert 'measurement_uncertainty_m: approximately 0.01' in text('sept_notes')
 s=text('repeat_stats');parts={}
 for k in ['P1_R1','P1_R2']:
  block=s.split(k+'  xyz=')[1].split('\n\n')[0]
  parts[k]={m[0]:dict(valid=int(m[1]),frames=int(m[2]),median=float(m[3]),std=float(m[4])) for m in re.findall(r'(node_\d+): usable=(\d+)/(\d+) median=([0-9.]+) m geometry=.*? std=([0-9.]+) m',block)}
 assert set(parts['P1_R1'])==set(parts['P1_R2'])=={'node_10','node_2','node_3','node_8'}
 rep=[]
 for node in parts['P1_R1']:
  a,b=parts['P1_R1'][node],parts['P1_R2'][node]
  rep.append(dict(pair='20261011_P1_R1_R2',quantity='raw_wall_median',link=node,replicates=2,r1_m=a['median'],r2_m=b['median'],difference_m=round(b['median']-a['median'],6),r1_std_m=a['std'],r2_std_m=b['std'],r1_valid=a['valid'],r2_valid=b['valid'],source_precision_m=.001,reference_uncertainty_m=None,repeatability_std_usable_for_XY=None,conclusion='one paired range difference, not repeatability of localization error',source_path=paths['repeat_stats']))
 assert [r['difference_m'] for r in rep]==[.005,.007,0.,.014]
 g=obj('geometry');v=obj('verify');d=obj('reference_decision');o=obj('operator')
 assert g['uncertainty_model'] is None and g['actual_independent_position_error_m'] is None and g['approved_scope']=='not_accepted'
 assert v['accepted_metric_reference_rows']==0
 assert all(x['spatial_uncertainty_m'] is None and x['temporal_uncertainty_ns'] is None for x in d['per_vehicle'].values())
 assert d['time']['independent_time_bound_s'] is None and o['T10_initialization']['endpoint_uncertainty_m'] is None
 ev=[]
 def add(id,quantity,measured,replication,u,status,limitation,source):
  ev.append(dict(id=id,quantity=quantity,existing_reference=measured,repetition_record=replication,reported_uncertainty_m=u,coverage_or_bound_type=None,accepted_paired_XY_resolution_m=None,status=status,why_not_XY_effect_resolution=limitation,source_path='; '.join(paths[x] for x in source)))
 add('S01','20260927双车静态车间直距','卷尺1.85m','一段静态；帧不是独立重复',.01,'REPORTED_APPROXIMATE_SCALAR_UNCERTAINTY','未给k/覆盖概率/硬界；不是逐车XY，不能跨日期安装使用',['sept_notes'])
 add('S02','20260927单链距离与重复','卷尺1.50/2.00/3.00m','1.50m两次可用率13.60%/99.90%；NLOS两次过渡/预站位不同',.01,'SCALAR_REFERENCE_AND_HETEROGENEOUS_REPEATS','不能池化为同分布方法重复；旧报告约值，不是本轮XY标定',['sept_report'])
 add('S03','20261011同名义XYZ静态重复','(2,2,1)m人工参考','R1/R2各一次；四链差0–14mm',None,'ONE_RANGE_REPEAT_PAIR','没有逐次实际XYZ读数误差、重新摆位记录与定位方法重复误差',['repeat_stats','repeat1_notes','repeat2_notes'])
 add('S04','20261011前进距离检查','卷尺1.020/1.010m','两次路径距离不同；修正后差+83/-1mm',None,'ENDPOINT_DISTANCE_DIAGNOSTIC','不是相同真实轨迹重复；-1mm残差不证明1mm参考能力',['forward1','forward2'])
 add('S05','20261017 P1/P4人工天线XYZ','P1(2,2,.20)，P4更正(3,3,.20)m','两个不同位置，P1用于拟合修正',None,'STATIC_REFERENCE_WITH_UNQUANTIFIED_ERROR','无重复尺量/几何不确定度；P1不能独立验证自身拟合效果',['p1','p4'])
 add('S06','20261018 A/B/Brepeat/C','车间卷尺2.93m','操作不同，首录过渡与重复弱效并存',None,'OPERATION_SEQUENCE_NOT_IID_REPLICATES','只有车间距没有两车各自XY；不能由MAD估参考误差',['static_report','static_stats'])
 add('S07','20261024 T01/T03/T04','各自直接间距约2.08/2.11/2.12m','朝向/回位不同，缺实际逐车XYZ',None,'CHANGED_POSE_AND_ORIENTATION','回到A不等于完全同位置；不能当同条件定位误差重复',['static_report'])
 add('S08','T02操作前后窗口','操作时间线与量测变化','同一次录制多个相关窗口',None,'WITHIN_RUN_DIAGNOSTIC','窗口和50Hz消息不是独立试验；无实际XY参考',['static_report'])
 add('S09','T10及P/Q视频空间参考','Q未参与拟合，但实际坐标/误差缺失','1164个候选读回、0个accepted metric reference',None,'NOT_ACCEPTED','候选计算一致、像素/模型灵敏度不等于独立参考误差界',['geometry','verify','missing'])
 add('S10','T10视频时序','拟合候选残差约0.1803s','无同期独立事件误差/offset/drift界',None,'NO_INDEPENDENT_TIME_BOUND','拟合残差不能充当时钟界，不能换算有效动态位置界',['reference_decision','operator'])
 add('S11','T10人工停点','Car1终点(1.48,2.97)m、末距1.52m','无误差量化及同次停车窗绑定',None,'CHECKPOINT_NOT_ACCEPTED','静态不强求毫秒同步，但需未挪动停车窗和尺量误差记录',['reference_decision','operator'])
 add('S12','本轮合成方法比较','生成器真值可作条件性数值评价','仅已暴露seed101配对；方法不是独立重复',None,'CONDITIONAL_SIMULATION_ONLY','可复查计算差异，但不能提供实测分辨能力/泛化重复性',['simulation_identity'])
 table('REFERENCE_CAPABILITY.csv',ev);table('REPEATABILITY_READBACK.csv',rep)
 frozen=dict(status='PARTIAL_FREEZE_EVIDENCE_RULES_ONLY',reason='No verified paired XY reference uncertainty or comparable localization-error repetitions found in reviewed records; measurement capability alone cannot choose acceptable harm.',reported_historical_scalar_uncertainty=dict(value_m=.01,scope='20260927 tape range only',kind='approximately; coverage factor and confidence unspecified',approved_for_current_XY=False),accepted_paired_XY_resolution_m=None,accepted_real_yaw_resolution_rad=None,min_meaningful_XY_improvement_m=None,allowed_companion_XY_degradation_m=None,allowed_nominal_XY_degradation_m=None,allowed_yaw_degradation_rad=None,recovery_deadline_s=None,development_XY_budget_m=dict(value=.04,scope='existing exposed descriptive budget only; not acceptance'),fixed_rules=['Never substitute range MAD/std or fit residual for reference uncertainty','Do not pool changed operation/pose/date as identical independent repeats','Keep measurement uncertainty and practical acceptable harm distinct','Use exact same time indices/reference for paired method comparison','Keep null when uncertainty source or coverage is unknown','No new acquisition or estimator run in this audit'],conditional_deterministic_rule=dict(premise='independently verified per-time Euclidean antenna-reference error <= epsilon_t, same n timestamps, no alignment/fitted truth',R='sqrt(mean(epsilon_t**2))',bound='abs((RMSE_A_ref-RMSE_B_ref)-(RMSE_A_true-RMSE_B_true)) <= 2*R',approval='not instantiated; approximate 0.01m tape statement is not this premise; 95% intervals are not hard bounds'),next_minimum='Recover existing same-session actual XYZ/checkpoint repeated readings, instrument/type of bound and parked-window identity; if absent narrow field accuracy claims, do not auto re-record.')
 dump('FROZEN_TOLERANCES.json',frozen)
 for r in ev:assert r['accepted_paired_XY_resolution_m'] is None
 dump('CHECKS.json',dict(status='PASS',evidence_rows=len(ev),paired_range_rows=len(rep),reference_status_nulls_checked=True,originals_modified=False,bag_video_reads=0,estimator_runs=0,limitations='Only existing record semantics and arithmetic verified; no new ground truth or accepted uncertainty'))
 dump('RUN_MANIFEST.json',dict(base_commit='519113f38d636844285e01b56a193ca26ef2bfb4',source_sha256={p:sha(ROOT/p) for p in paths.values()},analysis_sha256=sha(Path(__file__)),command='PYTHONDONTWRITEBYTECODE=1 /home/ubuntu22/uwb-single-car-quality-fgo-v1-artifacts/venv/bin/python tools/reference_resolution_audit_20261029/audit.py',scope='read-only compact sources and notes; no held-out errors or original recordings',rows=12))
 print('PASS: 12 evidence groups, 4 range-repeat differences, no approved XY tolerance invented')
if __name__=='__main__':main()

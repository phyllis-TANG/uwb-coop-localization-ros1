"""Post-experiment reporting only; never changes estimator/configuration."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--results', type=Path, required=True)
args = parser.parse_args()
ROOT = Path(__file__).resolve().parents[3]
RESULTS = args.results.resolve()
DOC = ROOT/'docs/field_tests/20261024_25/reliability_stress'
CFG = json.loads((ROOT/'tools/field_20261024_25/reliability_stress/frozen_config.json').read_text())
METHODS = CFG['methods']
LABELS = {'normal':'正常', 'peer_bias':'单向持续偏差', 'common_peer_bias':'双向共模偏差',
          'spikes':'短时尖峰', 'oneway_missing':'单向缺测', 'async_delay':'异步/延迟/重复',
          'wall_reduced':'源车单墙', 'geometry_degenerate':'源车薄几何', 'bias_weak_wall':'偏差＋单墙',
          'slow_ramp':'缓变偏差＋单墙', 'small_bias':'门限内小偏差', 'coherent_fault':'墙与peer自洽故障'}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    runs = {name:json.loads((RESULTS/name/'run.json').read_text()) for name in ['development','validation','development_readback','validation_readback']}
    assert all(r['status']=='DONE' for r in runs.values())
    summary = json.loads((RESULTS/'validation/summary.json').read_text())
    aggregates = {(r['scenario'],r['method_id'],r['role'],r['phase']):r for r in summary['aggregates']}
    scores = json.loads((RESULTS/'validation/metrics.json').read_text())
    audit = json.loads((RESULTS/'validation/audit.json').read_text())
    verification = json.loads((RESULTS/'validation_readback/verification.json').read_text())
    shutil.copyfile(RESULTS/'validation/summary.json',DOC/'validation_summary.json')
    shutil.copyfile(RESULTS/'validation_readback/verification.json',DOC/'validation_readback.json')
    shutil.copyfile(RESULTS/'development_readback/verification.json',DOC/'development_readback.json')
    columns=['trial_id','scenario','seed','source_car','method_id','vehicle_id','role','phase','rmse_m','p95_m','p99_m','max_m',
             'error_failure_fraction','any_error_failure','solver_failure_fraction','excess_rmse_m','shift_from_independent_max_m','recovery_s']
    with (DOC/'per_seed_fault.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader()
        for r in scores:
            if r['phase']=='fault':writer.writerow({k:(round(r[k],9) if isinstance(r[k],float) else r[k]) for k in columns})
    logs='专项测试（冻结源码对应 24 项）\n'+(RESULTS/'reliability_tests_frozen.log').read_text()
    logs+='\nPR45未修改适配器回归（13 项）\n'+(RESULTS/'pr45_adapter_tests.log').read_text()
    (DOC/'TESTS.log').write_text(logs)
    versions={'schema_version':1,'scope':'synthetic_only','baseline_commit':CFG['base_commit'],
              'preregistration_local_commit':subprocess.check_output(['git','rev-parse','4f8eaf8'],cwd=ROOT,text=True).strip(),'source_freeze_commit':'62f1a1368596c6729365a8f55f9926c05ae113f2','report_generator_sha256':sha(Path(__file__)),
              'branch':'analysis/reliability-stress-20261026-baf181','work_start_utc':'2026-10-26T05:56:50Z',
              'runs':{name:{k:r[k] for k in ['status','code_commit','worktree_dirty','elapsed_s','created_at_utc','finished_at_utc','source_sha256','config_sha256','command_argv','environment']}|{'run_json_sha256':sha(RESULTS/name/'run.json')} for name,r in runs.items()},
              'compact_outputs_sha256':{p.name:sha(p) for p in sorted(DOC.iterdir()) if p.is_file() and p.name in ['validation_summary.json','validation_readback.json','development_readback.json','per_seed_fault.csv','TESTS.log']},
              'archive_policy':'full contract run.json, generated inputs/truth, estimates, diagnostics, per-seed metrics, snapshots and logs are outside Git; archive SHA registered separately',
              'limitations':['no field localization accuracy evaluated','no novelty established','unadjusted seed-block bootstrap CIs','equal fixed solve count is not a real-time performance claim']}
    (DOC/'source_versions.json').write_text(json.dumps(versions,ensure_ascii=False,indent=2)+'\n')
    lines=['# 双车 UWB 可靠性与压力测试交接', '',
           '合成验证已完成。错误 peer 测距会把另一辆墙观测正常的车拖偏；基于创新残差的门控和传播位移上限能抑制这种传播。完整候选包含独立影子解，但其额外价值必须由消融判断，不能把整个改善归因于影子隔离，也不主张已形成算法创新。实包定位精度评价仍为 **BLOCKED**。', '',
           '## 实际版本与边界', '',
           '- 起点：`'+CFG['base_commit']+'`（PR45），抓取时 main 相同。独立分支 `analysis/reliability-stress-20261026-baf181`。',
           '- 正式验证源码：`62f1a1368596c6729365a8f55f9926c05ae113f2`，干净工作树；开发数值源码 `9ff2ba52fa4a721268079a6693032882d501cc46`。数值算法和配置在验证前冻结，验证后未调整。',
           '- 普通 git push 缺凭据；通过 GitHub 接口发布同树提交。发布前逐字核对 Git tree SHA，保留本地预注册/实现检查点分支与 bundle。远端源树与本地冻结树完全相同。',
           '- 仅本目录和 `tools/field_20261024_25/reliability_stress/` 新增内容。PR45原件、公共geometry/manifest、视频和另一基线端文件均未修改。无ROS、串口、车辆、Release写入或自动合并。',
           '- 使用独立Python 3.12.14 venv；NumPy 2.4.1、SciPy 1.17.0；单线程BLAS。没有下载现场bag/视频，也未计算T09/T11/T13/T15定位误差。', '',
           '## 设计与验收', '',
           '先提交[预注册](PREREGISTRATION.md)，再实际执行24项专项测试、PR45适配器13项测试、4组小规模正确性检查、72组开发实验、480组验证实验。验证包含20个独立随机种子块，每块12场景×两种源车镜像；不是480个独立现场实验。每轨迹48s、5Hz、241个tick，故障窗[12,30)s，随后恢复。验证使用不同轨迹、更大噪声和故障幅值。', '',
           '所有方法共用轨迹、噪声、初值、观测准入和计算预算。每tick固定16次4×4线性系统求解（含所有方法共用的独立影子路径）；保留完整车间协方差。该预算匹配不是墙钟等时，也未证明计算效率最优。标准Huber只作用于peer标准化残差；其余墙和Odom项一致。', '',
           '采样与到达时间分开；只消费已到达信息。用已到达Odom搬运采样时刻几何，超龄/坏身份/重复/bridge分别拒绝；双向有向记录保留，但每200ms采样窗最多用一个物理因子，晚到反向不会重复加入。真实时钟未验收时接口拒绝，不把接收时间当采样时间。', '',
           '独立回读没有导入估计器、生成器或原评价器，重新读取输入/估计/真值，核对输出SHA、因果peer、相关窗唯一性、求解预算和误差。验证检查：'+str(verification['checked'])+'。健康判定时最大相对独立解位移 '+f"{verification['max_healthy_shift_m']:.12f}"+'m，弱几何时 '+f"{verification['max_weak_shift_m']:.12f}"+'m，符合预注册0.06/0.35m界（浮点容差1e-10）。这是输出相对独立解的位移约束，不是绝对定位精度保证。', '',
           '## 对照与消融：故障窗RMSE', '',
           '单位m；表格为逐运行RMSE的均值，先对两个源车镜像配对；不是把所有帧当独立样本。normal行使用同一[12,30)s对照窗。source是注入来源，other是另一辆；common_peer_bias两向测距都有错，coherent_fault两车墙观测都被污染，此时other不能称为健康车。', '']
    for role,title in [('other','另一辆车（other）'),('source','注入来源车（source）')]:
        lines+=['### '+title,'','| 场景 | 独立 | 固定peer | Huber | 候选firewall | 去隔离消融 |','|---|---:|---:|---:|---:|---:|']
        for scenario in CFG['scenarios']:
            vals=[aggregates[scenario,m,role,'fault']['mean_rmse_m'] for m in METHODS]
            lines+=['| '+LABELS[scenario]+' | '+' | '.join(f'{v:.4f}' for v in vals)+' |']
        lines+=['']
    lines+=['## 尾部、失败和恢复','','完整五方法P95/P99/max、误差超0.5m比例、超限运行数及求解失败均在[完整聚合](validation_summary.json)和[逐种子表](per_seed_fault.csv)。下表对照候选与Huber，恢复为故障撤除后连续2s不高于独立解误差+0.03m的最早时刻；该指标衡量附加传播消退，不等于独立解已经准确。未恢复右删失，不补零。','','| 场景/角色 | 候选P95 | Huber P95 | 候选超0.5m比例 | 候选超限运行/40 | 候选恢复中位s/删失 | Huber恢复中位s/删失 |','|---|---:|---:|---:|---:|---|---|']
    for scenario in CFG['scenarios']:
        for role in ['source','other']:
            r=aggregates[scenario,'firewall',role,'fault'];h=aggregates[scenario,'huber',role,'fault']
            def rec(x):return '不适用' if scenario=='normal' else f"{x['median_recovery_s'] if x['median_recovery_s'] is not None else 'null'} / {x['recovery_censored_runs']}"
            lines+=['| '+LABELS[scenario]+'/'+role+f" | {r['mean_p95_m']:.4f} | {h['mean_p95_m']:.4f} | {r['mean_error_failure_fraction']:.3%} | {r['runs_with_error_failure']}/40 | {rec(r)} | {rec(h)} |"]
    lines+=['','## 配对不确定性与机制判断','','负值代表完整候选更优；95%区间以20个种子块bootstrap 4000次，镜像先在种子内平均。未作多重比较校正，不把单个场景显著性泛化。','','| 场景/角色 | 候选−Huber RMSE [95%CI] | 候选−去隔离 RMSE [95%CI] |','|---|---|---|']
    by={(r['scenario'],r['role'],r['comparison']):r for r in summary['paired']}
    for scenario in CFG['scenarios']:
        for role in ['source','other']:
            cells=[]
            for other in ['huber','no_firewall']:
                p=by[scenario,role,'firewall_minus_'+other];lo,hi=p['seed_bootstrap_ci95_m']
                cells+=[f"{p['mean_delta_rmse_m']:+.4f} [{lo:+.4f}, {hi:+.4f}]"]
            lines+=['| '+LABELS[scenario]+'/'+role+' | '+' | '.join(cells)+' |']
    lines += ['', '### 验证结果对应的判断', '',
        '- H1得到支持：单向持续偏差时，另一辆车RMSE由独立的0.0838m变为固定peer的0.1964m；Huber为0.0928m，完整候选0.0824m。但去隔离消融为0.0818m，所以这项保护不能归因于影子隔离。',
        '- H2的位移界得到支持：全部231360次检查满足预注册上限。门控＋限幅组合在持续大偏差上优于Huber；没有进一步消融二者，不能分别估计各自贡献。',
        '- H3仅有局部支持：偏差＋单墙的source RMSE，完整候选0.1611m、去隔离0.2362m（19/20种子块改善）；缓变偏差＋单墙为0.2341m与0.5497m（20/20改善）。这是弱车自身的抗累积收益；主关注的other在这些场景中未稳定优于消融，不能宣称额外的健康车保护收益。',
        '- 正常/小偏差/尖峰/异步条件下，完整候选通常没有超过Huber，故不是统一最优策略。正常全时段相对Huber的代价见下文；墙减少但peer正确时，source候选0.1791m，高于独立0.1386m；薄几何时0.2116m，高于Huber0.1631m，损失了有益协同。',
        '- 墙与peer自洽故障完全未被解决：候选与其他方法均约0.75m。健康判别只表示当前墙几何足够，不等于墙测距真实无偏。该失败按预注册场景完整保留。', '',
        '## 正常代价、失效条件及固定失败样例', '']
    for role in ['source','other']:
        vals={m:aggregates['normal',m,role,'all']['mean_rmse_m'] for m in METHODS}
        lines += [f"正常全时段 {role} RMSE（m）："+', '.join(f'{m}={v:.4f}' for m,v in vals.items())+f"。候选相对独立解 {vals['firewall']-vals['independent']:+.4f}m，相对Huber {vals['firewall']-vals['huber']:+.4f}m。"]
    lines+=['', '固定展示验证种子1001、source=car1，不按成功程度挑例子；所有其它种子已保留。', '',
            '| 场景/角色 | 独立RMSE | 候选RMSE | 去隔离RMSE | 候选P95 | 候选max |', '|---|---:|---:|---:|---:|---:|']
    for scenario in ['common_peer_bias','slow_ramp','coherent_fault']:
        for role in ['source','other']:
            def score(m):return next(r for r in scores if (r['seed'],r['source_car'],r['scenario'],r['role'],r['phase'],r['method_id'])==(1001,'car1',scenario,role,'fault',m))
            f=score('firewall')
            vals=[score('independent')['rmse_m'],f['rmse_m'],score('no_firewall')['rmse_m'],f['p95_m'],f['max_m']]
            lines+=['| '+LABELS[scenario]+'/'+role+' | '+' | '.join(f'{v:.4f}' for v in vals)+' |']
    lines += ['', '已知失效：墙与peer自洽/墙也错误时，影子解本身偏移；绝对误差可以很大而创新仍小。缓变或小偏差可能在门限内，限幅会损失有益协同信息。两车都弱、错误时钟、错误外参/高度、长相关噪声、未建模yaw不确定性不在本实验保证范围内。门控重开另见每个trial的audit.json，区分从未隔离、重开和右删失。', '',
              '## 真实执行、失败与复现', '',
              '已解决的执行失败：第一次启动因PR45目录保护拒绝workspace下的结果目录，尚未数值计算；随后一次smoke完成4组计算但汇总NumPy int64不能JSON序列化，修复类型转换后在新目录成功重跑。失败记录和旧运行保留，不覆写。普通git push因无凭据失败一次，改用GitHub接口发布。没有同一失败无限重试，没有新增6小时预算。', '',
              '开发运行耗时 '+f"{runs['development']['elapsed_s']:.2f}"+'s，验证 '+f"{runs['validation']['elapsed_s']:.2f}"+'s，验证独立回读 '+f"{runs['validation_readback']['elapsed_s']:.2f}"+'s。实际逐命令、环境、源码/配置及run.json SHA见[source_versions.json](source_versions.json)；每阶段完整run.json登记生成输入、种子、输出SHA和源码快照。', '',
              '本次独立checkout `/workspace/scratch/baf181dcbfd0/reliability-stress-20261026-baf181`；venv `/workspace/scratch/baf181dcbfd0/reliability-venv-baf181`；大结果 `/tmp/uwb-reliability-20261026-baf181/`。这些是实际运行位置，跨机器复现用新的自定目录；归档不依赖这些绝对路径。完整归档名称与SHA在 `ARTIFACTS.json`，包含数值输入/输出/诊断、source snapshot、日志和本地预注册git bundle，不含现场bag/视频、venv或他人缓存。', '',
              '在源码冻结提交运行，变量指向自己新建的Git外路径（若PR45目录保护拒绝路径，选择真正独立路径，不能改guard）：', '',
              '```bash', 'python3 -m venv "$VENV"', 'PYTHON="$VENV/bin/python"', '"$PYTHON" -m pip install -r tools/field_20261024_25/reliability_stress/requirements.txt',
              '"$PYTHON" -m unittest discover -s tools/field_20261024_25/reliability_stress -p "test_*.py" -v',
              '"$PYTHON" -m unittest discover -s tools/field_20261024_25 -p "test_comparison_adapter.py" -v',
              'OPENBLAS_NUM_THREADS=1 "$PYTHON" tools/field_20261024_25/reliability_stress/run.py --split development --output "$RESULTS/development"',
              'OPENBLAS_NUM_THREADS=1 "$PYTHON" tools/field_20261024_25/reliability_stress/run.py --split validation --freeze-commit 62f1a1368596c6729365a8f55f9926c05ae113f2 --output "$RESULTS/validation"',
              '"$PYTHON" tools/field_20261024_25/reliability_stress/verify_outputs.py --input "$RESULTS/validation" --output "$RESULTS/validation_readback"', '```', '',
              '验证命令要求HEAD恰为冻结提交且工作树干净；后续纯报告提交应在自己的新checkout检出该源码版本再复现，不切换他人的分支。种子输入及estimate.csv为确定性数值结果；运行时刻、耗时、run_id和诊断时间不同会改变整个归档SHA，不承诺重新打包逐字相同。', '',
              '## 给基线端的交接', '',
              '最小集成是独立影子状态、因果有向peer准入、创新/恢复状态和每车传播位移监控；无需改标准化导出或视觉工具。接口、未验收时钟guard及外参门槛见[INTERFACE.md](INTERFACE.md)。实包初始化、时钟、刚性外参和独立参考未验收，故实包精度结论保持BLOCKED。留出四包不参与参数选择；下一步应先由协调端审阅合成机制和消融结论，再决定是否接入开发包基线。']
    (DOC/'README.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'reports_created':len(list(DOC.iterdir())),'verification':verification['checked']},ensure_ascii=False))


if __name__ == '__main__':
    started = time.monotonic()
    out = RESULTS/'reporting'
    out.mkdir(exist_ok=False)
    run = {'schema_version': 1, 'role': 'synthetic_post_experiment_reporting', 'status': 'IN_PROGRESS',
           'created_at_utc': datetime.now(timezone.utc).isoformat(),
           'code_commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
           'worktree_dirty': bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()),
           'source_sha256': {str(Path(__file__).resolve().relative_to(ROOT)):sha(Path(__file__))},
           'config_sha256': {'frozen_config.json':sha(ROOT/'tools/field_20261024_25/reliability_stress/frozen_config.json')},
           'command_argv': [sys.executable]+sys.argv, 'environment': {'python': sys.version},
           'inputs': [{'asset_id': 'validation_summary', 'relative_path': 'validation/summary.json',
                       'sha256':sha(RESULTS/'validation/summary.json')}],
           'input_data_root': '..', 'random_seeds': CFG['validation_seeds'],
           'outputs': [], 'blocked_reasons': [],
           'limitations': ['report-only; no numerical estimator or frozen configuration edits',
                           'reporting worktree includes new compact reports; numeric source remains frozen']}
    try:
        main()
        (out/'compact').mkdir()
        for p in sorted(DOC.iterdir()):
            if p.is_file(): shutil.copyfile(p,out/'compact'/p.name)
        shutil.copyfile(Path(__file__),out/'report.py')
        run['outputs']=[{'relative_path':str(p.relative_to(out)),'sha256':sha(p)}
                        for p in sorted(out.rglob('*')) if p.is_file()]
        run['status']='DONE'
    except Exception as exc:
        run['status']='FAILED'
        run['error']=str(exc)
        raise
    finally:
        run['elapsed_s']=time.monotonic()-started
        run['finished_at_utc']=datetime.now(timezone.utc).isoformat()
        (out/'run.json').write_text(json.dumps(run,ensure_ascii=False,indent=2)+'\n')

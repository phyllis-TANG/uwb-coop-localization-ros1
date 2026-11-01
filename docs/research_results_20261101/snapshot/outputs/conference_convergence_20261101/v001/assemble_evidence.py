from pathlib import Path
import json,hashlib
ROOT=Path('I:/UWB/project');HERE=Path(__file__).resolve().parent
D=ROOT/'outputs/dynamic_development_20261101/v001'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
data=read(D/'STOP_COMPARISON.json')
for path,digest in data['source_hashes'].items():
    assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest,path
lines=['A1/B1停车稳定窗逐车结果表（2026-11-01）',
       '条件开发结果；单位cm；M2独立，M3全协同，W025固定peer代价权重0.25。',
       '误差使用每车/每窗三方法共同有效时刻。N为共同有效/预定时刻；各方法自身有效数另列。',
       'START不含用于初始化的前5秒，后续warmup仍在分母；不声称移动全程精度。',
       '参考误差敏感性采用工程假设：每轴2cm对应平面球半径sqrt(2)*2cm，不是认证误差界。',
       '', '组 | 停点 | 车辆/角色 | N | M2 RMSE | M3 RMSE | W025 RMSE | M3配对方向 | W025配对方向 | 自身有效M2/M3/W025']
names={'START':'起点','B':'B','C':'C','RETURN':'返回'}
directions={'improve':'误差降低','harm':'误差增加','unresolved':'参考敏感性下未分辨'}
for r in data['rows']:
    m=r['methods'];p=r['paired'];own=r['own_valid_frames']
    lines.append(f"{r['case']} | {names[r['phase']]} | {r['car']}/{'移动' if r['role']=='moving' else '固定'} | {r['common_valid_frames']}/{r['scheduled_frames']} | "+' | '.join(f"{m[k]['rmse_m']*100:.2f}" for k in ('M2','M3','M3W025'))+f" | {directions[p['M3-M2']['direction']]} | {directions[p['M3W025-M2']['direction']]} | "+'/'.join(str(own[k]) for k in ('M2','M3','M3W025')))
lines+=['','全段发布与有效覆盖（包括运动、测量人员在场等非参考段，仅用于可用性统计）',
        '组 | 方法 | 发布数 | 求解接受 | Car1有效 | Car2有效 | 状态计数']
for case in ('A1','B1'):
    for method in ('M2','M3','M3W025'):
        s=read(D/case/method/'summary.json')
        lines.append(f"{case} | {method} | {s['frames']} | {s['accepted']} | {s['valid']['car1']} | {s['valid']['car2']} | {s['statuses']}")
lines+=['','异常处置：B1_B_W025_Car1约284.77cm保留在表内。用户决定停止继续追查物理原因，登记为持续测距偏移、原因未确定。',
        '事后删链诊断不纳入正式方法排名，不用诊断结果替换原W025结果。求解成功/满秩不等于定位可靠。',
        '16个逐车停车条目共享轨迹/历史，不是16次独立试验；正负方向数不能当成功率。',
        '来源：outputs/dynamic_development_20261101/v001/STOP_COMPARISON.json；中位数/P95/配对平方差区间见该JSON。',
        '本表由已保存结果自动生成；所有关联轨迹、事件及测点来源SHA再次核对通过；没有重跑估计器。']
(HERE/'A1_B1逐车结果表.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('\n'.join(lines))

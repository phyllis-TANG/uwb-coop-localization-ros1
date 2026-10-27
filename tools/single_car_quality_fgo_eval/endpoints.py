"""Frozen stopping-window antenna diagnostics, strictly offline evaluation."""
import argparse
import csv
import json
import math
from pathlib import Path
import statistics
from evidence import begin,finish,require,sha,write


def truthflag(value):
    if value in (True,'True','true','1',1):return True
    if value in (False,'False','false','0',0):return False
    raise ValueError('missing/unknown output validity flag')


def endpoint(rows,case):
    lo,hi=case['evaluation_window_s'];selected=[r for r in rows if lo<=float(r['state_time_s'])<=hi]
    finite=[r for r in selected if all(math.isfinite(float(r[k])) for k in ('antenna_x_m','antenna_y_m'))]
    valid=[r for r in finite if truthflag(r['estimate_valid'])]
    def describe(seq):
        if not seq:return dict(count=0,median_xy_m=None,distance_to_manual_endpoint_m=None,radial_spread_about_component_median_m=None)
        x=statistics.median(float(r['antenna_x_m']) for r in seq);y=statistics.median(float(r['antenna_y_m']) for r in seq)
        radial=[math.hypot(float(r['antenna_x_m'])-x,float(r['antenna_y_m'])-y) for r in seq]
        return dict(count=len(seq),median_xy_m=[x,y],distance_to_manual_endpoint_m=math.hypot(x-case['end_antenna_xyz_m'][0],y-case['end_antenna_xyz_m'][1]),
          radial_spread_about_component_median_m=dict(median=statistics.median(radial),rms=math.sqrt(statistics.mean(v*v for v in radial)),maximum=max(radial)),
          axis_span_m=[max(float(r[k]) for r in seq)-min(float(r[k]) for r in seq) for k in ('antenna_x_m','antenna_y_m')])
    return dict(case_id=case['id'],frozen_window_s=[lo,hi],manual_endpoint_xy_m=case['end_antenna_xyz_m'][:2],manual_reference_uncertainty_m=None,scheduled_window_outputs=len(selected),finite_outputs=len(finite),valid_outputs=len(valid),
      all_finite=describe(finite),estimate_valid_only=describe(valid),selected_state_times_s=[float(r['state_time_s']) for r in selected],
      scatter_definition='componentwise antenna XY median; radial distances about this median; RMS is within-window scatter, NOT trajectory/reference RMSE',
      reference_status='uncertainty unknown; historical geometry/odom-origin conditional; development stop diagnostic only')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--reused',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();v=begin(a.output,'frozen_PR59_stop_diagnostics_no_estimator')
    try:
        reference=json.loads((a.reused/'evaluation_only.json').read_text());results=[];flat=[]
        for case in sorted(reference['cases'],key=lambda x:x['id']):
            for arm in ('F0','F1','F2','F3'):
                path=a.reused/'F0_F3'/(case['id']+'_'+arm)/'published.csv'
                with path.open() as f:rows=list(csv.DictReader(f))
                result=endpoint(rows,case);result.update(arm=arm,quality_comparison_arm={'F0':'Q0','F3':'Q1'}.get(arm),publication_sha256=sha(path));results.append(result)
                stats=result['all_finite'];spread=stats['radial_spread_about_component_median_m'];flat.append(dict(case_id=case['id'],arm=arm,window_start_s=result['frozen_window_s'][0],window_end_s=result['frozen_window_s'][1],outputs=result['scheduled_window_outputs'],finite_outputs=result['finite_outputs'],estimate_valid_outputs=result['valid_outputs'],antenna_median_x_m=stats['median_xy_m'][0] if stats['median_xy_m'] else None,antenna_median_y_m=stats['median_xy_m'][1] if stats['median_xy_m'] else None,manual_x_m=result['manual_endpoint_xy_m'][0],manual_y_m=result['manual_endpoint_xy_m'][1],distance_to_manual_endpoint_m=stats['distance_to_manual_endpoint_m'],radial_scatter_median_m=spread['median'] if spread else None,radial_scatter_rms_m=spread['rms'] if spread else None,radial_scatter_max_m=spread['maximum'] if spread else None))
        write(a.output/'diagnostics.json',dict(status='DONE',reference_protocol_sha256=reference['protocol_sha256'],rows=results,quality_rule_uses_manual_endpoint=False,full_trajectory_RMSE_or_accepted_accuracy=False))
        with (a.output/'diagnostics.csv').open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
        md=['# 冻结停止窗末端开发诊断','', '人工参考不确定度未知，历史几何/odom原点仍有条件假设。本表不是全程RMSE或已验收精度；终点/停止窗不进入质量规则、阈值或参数选择。散布RMS是相对窗口自身XY中位数的散布。','', '| 包 | 臂 | 冻结窗口s | 发布/有限/有效 | 天线XY中位数m | 对人工末点平面距离差m | 散布中位/RMS/最大m |','|---|---|---|---|---|---:|---|']
        for x in flat:md.append(f"| {x['case_id']} | {x['arm']} | [{x['window_start_s']},{x['window_end_s']}] | {x['outputs']}/{x['finite_outputs']}/{x['estimate_valid_outputs']} | ({x['antenna_median_x_m']:.6f},{x['antenna_median_y_m']:.6f}) | {x['distance_to_manual_endpoint_m']:.6f} | {x['radial_scatter_median_m']:.6f}/{x['radial_scatter_rms_m']:.6f}/{x['radial_scatter_max_m']:.6f} |")
        (a.output/'TABLE.md').write_text('\n'.join(md)+'\n');v['inputs']=[dict(path=str(a.reused/'reuse_manifest.json'),sha256=sha(a.reused/'reuse_manifest.json')),dict(path=str(a.reused/'evaluation_only.json'),sha256=sha(a.reused/'evaluation_only.json'))];finish(a.output,v);return 0
    except Exception as e:finish(a.output,v,e);raise


if __name__=='__main__':raise SystemExit(main())

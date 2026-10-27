"""All-publication response/coverage report; no field truth or accuracy score."""
import argparse
from collections import Counter
import csv
import json
import math
from pathlib import Path
import numpy as np
from meta import LEGACY,finish,save,sha,start
from verify_fgo import loadlines,require


def stats(values):
    v=np.asarray(values,float)
    return {'n':len(v),'minimum':float(v.min()),'median':float(np.median(v)),'p95':float(np.percentile(v,95)),'maximum':float(v.max())} if len(v) else {'n':0}


def summarize(rows,base,common,stop):
    selected=[r for r in rows if r['state_epoch_ns'] in common];index={r['state_epoch_ns']:r for r in base}
    def difference(seq):
        return {'publications':len(seq),'base_shift_vs_F0_m':stats([np.linalg.norm(np.asarray(r['pose'][:2])-index[r['state_epoch_ns']]['pose'][:2]) for r in seq]),'absolute_wrapped_yaw_difference_vs_F0_deg':stats([abs(math.degrees(math.atan2(math.sin(r['pose'][2]-index[r['state_epoch_ns']]['pose'][2]),math.cos(r['pose'][2]-index[r['state_epoch_ns']]['pose'][2])))) for r in seq]),'these_are_response_differences_not_accuracy_errors':True}
    n=len(base);failed=[r for r in rows if 'solver_failed' in r['status'] or 'solver_error' in r['status']];bias=[r['bias_rad_s'] for r in rows if r.get('bias_rad_s') is not None]
    first_accepted=next((i for i,r in enumerate(rows) if r['accepted_graph']),None)
    stopped=[r for r in rows if stop[0]<=r['state_time_s']<=stop[1]]
    xy=np.array([r['antenna_xy_m'] for r in stopped]);spread=stats(np.linalg.norm(xy-xy.mean(axis=0),axis=1)) if len(xy) else {'n':0}
    result={'scheduled_publications':n,'published':len(rows),'finite_pose_count':sum(r['pose'] is not None and bool(np.isfinite(r['pose']).all()) for r in rows),'valid_count':sum(bool(r['estimate_valid']) for r in rows),
        'valid_fraction_of_all_scheduled':sum(bool(r['estimate_valid']) for r in rows)/n,'accepted_graph_count':sum(bool(r['accepted_graph']) for r in rows),'warmup_count':sum('warmup' in r['status'] for r in rows),
        'solver_failure_count':len(failed),'solver_failure_fraction_of_all_scheduled':len(failed)/n,'missing_angular_count':sum(r.get('angular_valid') is False for r in rows),'odom_yaw_fallback_count':sum(bool(r['odom_yaw_fallback']) for r in rows),
        'status_counts':dict(Counter(r['status'] for r in rows)),'all_publications':difference(rows),'common_estimate_valid_publications':difference(selected),
        'bias_rad_s':dict(stats(bias),first=bias[0],last=bias[-1],max_abs=float(np.max(np.abs(bias))),max_step=float(np.max(np.abs(np.diff(bias)))) if len(bias)>1 else 0.) if bias else None,
        'bias_interpretation':'F3 estimated model residual, not calibrated truth; F1/F2 fixed zero by design; F0 absent',
        'update_wall_s':stats([r['update_wall_s'] for r in rows]),'solve_wall_s_total':sum(r['solve_wall_s'] for r in rows),'marginal_wall_s_total':sum(r['marginal_wall_s'] for r in rows),
        'virtual_publication_delay_s':stats([r['estimated_worker_finish_s']-r['state_time_s'] for r in rows]),'virtual_queue_s':stats([r['estimated_worker_queue_s'] for r in rows]),
        'maximum_position_jump_between_publications_m':float(np.max(np.linalg.norm(np.diff(np.asarray([r['pose'][:2] for r in rows]),axis=0),axis=1))),
        'first_accepted_position_correction_m':rows[first_accepted]['position_correction_m'] if first_accepted is not None else None,
        'fixed_historical_stop_window_s':stop,'stop_window_antenna_spread_about_own_mean_m':spread,'stop_spread_is_not_accuracy_or_independent_stationarity_confirmation':True,
        'max_solve_keyframes':max(r['graph_states'] for r in rows),'max_solve_scalar_variables':max(r['scalar_variables'] for r in rows)}
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--matrix',type=Path,required=True);p.add_argument('--readback',type=Path,required=True);p.add_argument('--prefix',type=Path,required=True);p.add_argument('--negative',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run=start(a.output,'B_FGO_all_and_common_response_report')
    try:
        for path in (a.readback,a.prefix,a.negative):require(json.loads((path/'verification.json').read_text())['status']=='PASS','independent verification must pass')
        protocol=json.loads(LEGACY.read_text());cases={c['id']:c for c in protocol['cases']};reports=[];csvrows=[];allrows={}
        for case in ('004023','005135'):
            by={arm:loadlines(a.matrix/(case+'_'+arm)/'updates.jsonl.gz') for arm in ('F0','F1','F2','F3')};grid={r['state_epoch_ns'] for r in by['F0']};common=set(grid)
            for rows in by.values():
                require({r['state_epoch_ns'] for r in rows}==grid,'same complete publication grid')
                common&={r['state_epoch_ns'] for r in rows if r['estimate_valid']}
            stop=cases[case]['evaluation_window_s'];modes={};base={r['state_epoch_ns']:r for r in by['F0']}
            for arm,rows in by.items():
                modes[arm]=summarize(rows,by['F0'],common,stop);allrows[case,arm]=rows
                for r in rows:
                    csvrows.append(dict(case_id=case,arm=arm,state_epoch_ns=r['state_epoch_ns'],availability_cutoff_epoch_ns=r['availability_cutoff_epoch_ns'],state_time_s=r['state_time_s'],status=r['status'],estimate_valid=r['estimate_valid'],accepted_graph=r['accepted_graph'],common_estimate_valid=r['state_epoch_ns'] in common,angular_valid=r['angular_valid'],odom_yaw_fallback=r['odom_yaw_fallback'],prediction_yaw_source=r['prediction_yaw_source'],base_x_m=r['pose'][0],base_y_m=r['pose'][1],yaw_rad=r['pose'][2],bias_rad_s=r['bias_rad_s'],shift_vs_F0_m=float(np.linalg.norm(np.asarray(r['pose'][:2])-base[r['state_epoch_ns']]['pose'][:2])),update_wall_s=r['update_wall_s'],graph_states=r['graph_states'],scalar_variables=r['scalar_variables']))
            reports.append(dict(case_id=case,common_estimate_valid_count=len(common),common_estimate_valid_epoch_ns=sorted(common),modes=modes))
        with (a.output/'publication_diagnostics.csv').open('x',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(csvrows[0]));w.writeheader();w.writerows(csvrows)
        import matplotlib;matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,axes=plt.subplots(2,3,figsize=(13,7),layout='constrained')
        for i,case in enumerate(('004023','005135')):
            for arm in ('F0','F1','F2','F3'):
                rows=allrows[case,arm];t=[r['state_time_s'] for r in rows];b=allrows[case,'F0']
                axes[i,0].plot(t,[np.linalg.norm(np.asarray(r['pose'][:2])-q['pose'][:2]) for r,q in zip(rows,b)],label=arm)
                axes[i,1].plot(t,[math.degrees(math.atan2(math.sin(r['pose'][2]-q['pose'][2]),math.cos(r['pose'][2]-q['pose'][2]))) for r,q in zip(rows,b)],label=arm)
                if arm=='F3':axes[i,2].plot(t,[r['bias_rad_s'] for r in rows],label='F3 estimated residual')
            for ax in axes[i]:ax.set_xlabel('recorded centered state time (s)');ax.grid(alpha=.25);ax.legend(fontsize=8)
            axes[i,0].set_ylabel(case+' base shift vs F0 (m)');axes[i,1].set_ylabel('wrapped yaw difference (deg)');axes[i,2].set_ylabel('bias (rad/s)')
        fig.suptitle('Conditional historical response; differences are not field accuracy');fig.savefig(a.output/'response_and_bias.png',dpi=130);plt.close(fig)
        save(a.output/'summary.json',dict(status='DONE',cases=reports,nominal_runs=8,verification_prefix_controls=8,field_accuracy_evaluated=False,strict_physical_branch='BLOCKED',physical_clock_error_bound_ns=None,
            missing_information=['verified historical gyro/body axis/sign','historical sampling/header/receipt clock relation and physical error bounds','physical odom-origin correspondence for inherited center lever'],
            no_truth_endpoint_video_or_quaternion_used_for_tuning=True))
        run['inputs']=[{'path':str(x),'sha256':sha(x)} for x in (a.matrix/'matrix.json',a.readback/'verification.json',a.prefix/'verification.json',a.negative/'verification.json')];finish(a.output,run,'DONE');return 0
    except Exception as e:finish(a.output,run,'FAILED',e);raise


if __name__=='__main__':raise SystemExit(main())

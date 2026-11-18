#!/usr/bin/env python3
"""Recalculate cross-recording evidence from archived, matched estimates.

No estimator fitting, ROS, serial access, or raw-data modification. Historical
batch estimates and dedicated fixed-lag estimates retain separate identities.
Run --collect-sources once in the original checkout; subsequent runs are portable.
"""
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime, timezone, timedelta
import argparse, csv, hashlib, json, math, shutil
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parent
SRC, OUT, FIG = [ROOT / x for x in ('sources', 'results', 'figures')]
REPO = ROOT.parents[2]
TZ = timezone(timedelta(hours=8))
BLUE, RED, ORANGE = '#2166AC', '#B2182B', '#E08214'
plt.rcParams.update({'font.family':'STIXGeneral', 'mathtext.fontset':'stix',
 'font.size':8, 'axes.titlesize':9, 'axes.labelsize':8,
 'xtick.labelsize':7, 'ytick.labelsize':7, 'legend.fontsize':7,
 'axes.linewidth':.65, 'pdf.fonttype':42, 'ps.fonttype':42, 'savefig.dpi':260})

def read(p): return json.loads(p.read_text(encoding='utf-8'))
def writej(p, x): p.write_text(json.dumps(x, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
def writecsv(p, rows):
    if not rows: return
    with p.open('w', newline='', encoding='utf-8-sig') as f:
        w=csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
def csvrows(p):
    with p.open(encoding='utf-8-sig') as f: return list(csv.DictReader(f))
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def collect():
    SRC.mkdir(exist_ok=True)
    draft = REPO/'docs/research/paper_draft_v1_20261103'
    audit = REPO/'docs/research/paper_audit_20261103'
    for name in ('static_pair_rows.json','static_plot_rows.json','dynamic_all_32_stop_rows.json'):
        shutil.copyfile(draft/'data'/name, SRC/name)
    shutil.copyfile(audit/'bag_register_116.csv', SRC/'bag_register_116.csv')
    pr95=REPO.parent/'pr95_readonly/docs/research/paper_evidence_completion_20261103/static/runs'
    runs=sorted({r['run_id'] for r in read(SRC/'static_pair_rows.json')})
    epochs, meta, provenance = [], [], []
    for run in runs:
        traj, summary={},{}
        for profile in ('raw','historical'):
            p=pr95/run/profile
            traj[profile]=read(p/'trajectory.json'); summary[profile]=read(p/'summary.json')
            for name in ('trajectory.json','summary.json'):
                provenance.append({'run':run,'profile':profile,'path':str((p/name).relative_to(REPO.parent)),
                                   'sha256':digest(p/name)})
        assert summary['raw']['phase_windows_s']==summary['historical']['phase_windows_s']
        indexes={p:{m:{r['second']:r for r in traj[p][m]} for m in ('I','J','W025')} for p in traj}
        first=traj['raw']['I'][0]
        origin_ns=first['cutoff_ns']-first['second']*10**9
        name_stamp=run
        meta.append({'run_id':run,'placement':'A' if run.startswith('G1') else 'B',
          'receipt_origin_ns':origin_ns,
          'receipt_origin_hk':datetime.fromtimestamp(origin_ns/1e9,TZ).isoformat(),
          'saved_trajectory_span_s':traj['raw']['I'][-1]['second']-first['second'],
          'first_saved_second':first['second'],'last_saved_second':traj['raw']['I'][-1]['second'],
          'phase_windows_s':summary['raw']['phase_windows_s'],
          'reference':summary['raw']['reference'],
          'freeze_sha256':summary['raw']['freeze_sha256']})
        for phase,(lo,hi) in summary['raw']['phase_windows_s'].items():
            sets=[]
            for p in indexes:
                for m in indexes[p]:
                    sets.append({s for s,r in indexes[p][m].items() if lo<=s<hi and r['accepted']})
            assert all(s==sets[0] for s in sets), (run,phase,'unmatched valid masks')
            for s in sorted(set.intersection(*sets)):
                assert len({indexes[p][m][s]['cutoff_ns'] for p in indexes for m in indexes[p]})==1
                for p in indexes:
                    for m in indexes[p]:
                        r=indexes[p][m][s]
                        for car,i in [('car1',0),('car2',3)]:
                            ref=summary[p]['reference'][car]
                            epochs.append({'run_id':run,'profile':p,'phase':phase,'car':car,'method':m,
                             'second':s,'cutoff_ns':r['cutoff_ns'],'x_m':r['pose'][i],
                             'y_m':r['pose'][i+1],'reference_x_m':ref[0],'reference_y_m':ref[1]})
    writecsv(SRC/'E3_matched_epochs.csv',epochs)
    writej(SRC/'E3_recording_metadata.json',sorted(meta,key=lambda x:x['receipt_origin_ns']))
    writej(SRC/'E3_trajectory_provenance.json',provenance)

def inventory():
    rows=csvrows(SRC/'bag_register_116.csv'); out=[]
    e2ids={'B057','B059','B064'}
    static_xy={'B056','B062','B065','B066'}
    e3={r['run_id']:r for r in read(SRC/'E3_recording_metadata.json')}
    for r in rows:
        x=dict(r); rid=r['record_id']; name=r['filename']
        group='other_reference_or_interface'; status='context_or_sensor_characterization'
        action='保留原台账用途；按参考和配置逐包筛选'; metrics=''; priority='context'
        if r['data_kind']!='real':
            group='legacy_simulation';status='simulation_not_field_acquisition'
            action='保留仿真身份，不计入实地采集时长或独立重复';metrics='synthetic diagnostics';priority='context'
        elif rid in e2ids:
            group='E2_historical_two_robot';status='archived_trajectory_remeasured'
            action='已用原共同末五状态重算MSE/D/C；batch身份保留；精确固定窗重放需原始接收事件'
            metrics='endpoint-window MSE,D,C; no placement T';priority='P1'
        elif rid in static_xy:
            group='historical_two_robot_static_xy';status='reference_candidate_no_current_matched_trajectory'
            action='恢复原始包并运行raw/corrected × I/J/Reduced；B062为校准来源，B056共享前包终点'
            metrics='potential static D,C; T requires comparable placement groups';priority='P2'
        elif rid in {'B058','B060','B061','B063'}:
            group='historical_two_robot_motion';status='endpoint_candidate_needs_replay_and_window_check'
            action='保留偏向、线缆或人员过程；依据各包参考和停止支持重放，不按误差筛选'
            metrics='potential stop-window D,C';priority='P2'
        elif rid in {'B067','B068','B069','B070'}:
            group='historical_scalar_distance';status='scalar_reference_no_robot_xy_reference'
            action='用于车间测距残差、遮挡与重复性；补齐XY前不算定位C/T'
            metrics='range residuals, availability';priority='P3'
        elif rid in e3:
            group='E3_confirmation';status='matched_epoch_analysis_complete'
            action='原窗口和逐记录身份保留；正常窗全纳入';metrics='D,C; placement-group T';priority='P1'
        elif rid in {'A1','B1','A2','B2_PREFIX','B2_CONTINUATION'}:
            group='E4_motion_stops';status='raw_profile_available_corrected_missing'
            action='PR95已补齐32条停点对照；扩展C需补跑校正条件；分段初始化不另称独立试验'
            metrics='D now; C after corrected replay; no matched A/B T';priority='P2'
        elif rid.startswith('T') and rid[1:].isdigit():
            group='Oct24_25_two_robot_candidates';status='development_reference_and_replay_check'
            action='核实天线坐标、停点窗口、安装及时钟；原holdout身份保留'
            metrics='potential D,C at supported stops';priority='P2'
        elif rid.startswith('N_H'):
            group='Oct24_25_pilots';status='pilot_reference_and_motion_annotation_check'
            action='按原备注核对静态/朝向/试录身份；有参考的窗口可扩展量测分析'
            metrics='range/orientation; potential D,C after reference and replay checks';priority='P3'
        elif rid in {'P00_NORMAL','G1_R1_W1','G1_R1_W1_INTERRUPTED'}:
            group='E3_development_or_interruption';status='development_not_confirmation'
            action='保留开发和中断身份；不得增补为确认重复';metrics='development diagnostics';priority='context'
        elif 'TWO_CAR' in name:
            group='earlier_two_robot_interface';status='sensor_or_interface_evidence'
            action='有标量间距可作测距分析；无完整房间XY/基站输入时不计算定位C/T'
            metrics='range residuals, direction, availability';priority='P3'
        elif name.startswith('MOBILE_') or '_P1' in name or '_P23_' in name or '_P4_' in name or '_A_static_' in name or '_REINSTALL_STATIC_' in name:
            group='single_robot_static_calibration';status='calibration_or_transfer_evidence'
            action='用于跨位置测距校准迁移；校准来源与测试位置分开'
            metrics='per-link residuals, calibration transfer; no cooperative C,T';priority='P3'
        elif name.startswith('CAR2_'):
            group='single_robot_motion_or_pilot';status='single_robot_evidence'
            action='E1五条主记录保留；其他试录按原身份使用，不能形成双车C/T'
            metrics='single-robot endpoint or motion diagnostics';priority='context'
        elif name.startswith('PA0_') or name.startswith('EXP'):
            group='single_link_range_characterization';status='scalar_range_evidence'
            action='按标量参考、LOS/NLOS及重复身份分析测距';metrics='range residuals, availability';priority='context'
        x.update(analysis_group=group,current_status=status,eligible_metrics=metrics,
                 next_action=action,priority=priority,
                 verified_saved_trajectory_span_s=e3[rid]['saved_trajectory_span_s'] if rid in e3 else '',
                 duration_kind='saved trajectory span; not raw bag duration' if rid in e3 else 'not verified')
        out.append(x)
    writecsv(OUT/'recording_eligibility_116.csv',out)
    return dict(Counter(x['analysis_group'] for x in out))

def decompose():
    epochs=csvrows(SRC/'E3_matched_epochs.csv'); groups=defaultdict(list)
    for r in epochs:groups[tuple(r[k] for k in ('run_id','profile','phase','car','method'))].append(r)
    saved={tuple(r[k] for k in ('run_id','profile','phase','car','method')):r for r in read(SRC/'static_plot_rows.json')}
    detail=[]; maxerr=0
    for key,rs in groups.items():
        xy=np.array([[float(r['x_m']),float(r['y_m'])] for r in rs]);ref=np.array([float(rs[0]['reference_x_m']),float(rs[0]['reference_y_m'])])
        err=xy-ref; mse=float(np.mean(np.sum(err**2,axis=1)))
        offset=float(np.sum(np.mean(err,axis=0)**2)); spread=float(np.mean(np.sum((xy-xy.mean(axis=0))**2,axis=1)))
        maxerr=max(maxerr,abs(mse-offset-spread),abs(mse-saved[key]['mse_m2']))
        assert len(rs)==saved[key]['n_common'] and abs(mse-saved[key]['mse_m2'])<2e-13
        detail.append(dict(zip(('run_id','profile','phase','car','method'),key),n=len(rs),
          mse_m2=mse,mean_offset_sq_m2=offset,within_window_spread_m2=spread,
          mean_error_x_m=float(err[:,0].mean()),mean_error_y_m=float(err[:,1].mean())))
    assert len(detail)==240
    writecsv(OUT/'E3_error_decomposition_240.csv',detail)
    idx={tuple(r[k] for k in ('run_id','profile','phase','car','method')):r for r in detail}
    paired=[]
    for r in read(SRC/'static_pair_rows.json'):
        key=tuple(r[k] for k in ('run_id','profile','phase','car'))
        arm,ind=idx[key+(r['arm'],)],idx[key+('I',)]
        d=arm['mse_m2']-ind['mse_m2'];assert abs(d-r['D_m2'])<2e-13
        paired.append({k:r[k] for k in ('run_id','profile','phase','car','arm')}|
           {'D_m2':d,'D_offset_m2':arm['mean_offset_sq_m2']-ind['mean_offset_sq_m2'],
            'D_spread_m2':arm['within_window_spread_m2']-ind['within_window_spread_m2']})
    ix={tuple(r[k] for k in ('run_id','profile','phase','car','arm')):r for r in paired}
    calibration=[]
    for r in paired:
        if r['profile']!='raw':continue
        k=(r['run_id'],'historical',r['phase'],r['car'],r['arm']);c=ix[k]
        calibration.append({k:r[k] for k in ('run_id','phase','car','arm')}|
          {'placement':'A' if r['run_id'].startswith('G1') else 'B',
           'D_raw_m2':r['D_m2'],'D_corrected_m2':c['D_m2'],
           'C_m2':c['D_m2']-r['D_m2'],
           'C_offset_m2':c['D_offset_m2']-r['D_offset_m2'],
           'C_spread_m2':c['D_spread_m2']-r['D_spread_m2']})
    writecsv(OUT/'E3_C_decomposition_80.csv',calibration)
    summaries=[];loo_rows=[]
    for phase in ('normal','human','recovery'):
        selected=[r for r in calibration if r['phase']==phase]
        if not selected:continue
        for car in ('car1','car2'):
            for arm in ('J','W025'):
                rr=[r for r in selected if r['car']==car and r['arm']==arm]
                def contrast(field,skip=None):
                    return np.mean([r[field] for r in rr if r['placement']=='B' and r['run_id']!=skip])-np.mean([r[field] for r in rr if r['placement']=='A' and r['run_id']!=skip])
                vals=[float(contrast('C_m2',r['run_id'])) for r in rr]
                full=float(contrast('C_m2'))
                for r,v in zip(rr,vals):
                    loo_rows.append({'phase':phase,'car':car,'arm':arm,'omitted_run_id':r['run_id'],
                     'T_all_m2':full,'T_leave_one_out_m2':v,'sign_preserved':bool(np.sign(v)==np.sign(full))})
                summaries.append({'phase':phase,'car':car,'arm':arm,'n_A':sum(r['placement']=='A' for r in rr),
                  'n_B':sum(r['placement']=='B' for r in rr),'T_m2':full,
                  'T_offset_m2':float(contrast('C_offset_m2')),'T_spread_m2':float(contrast('C_spread_m2')),
                  'LOO_min_m2':min(vals),'LOO_max_m2':max(vals),
                  'LOO_sign_preserved':all(np.sign(x)==np.sign(full) for x in vals)})
    writecsv(OUT/'E3_T_leave_one_out.csv',summaries)
    writecsv(OUT/'E3_leave_one_out_all_80.csv',loo_rows)
    return detail,calibration,summaries,maxerr

def historical():
    protocol=read(SRC/'E2_protocol.json');summary=read(SRC/'E2_summary.json')
    rows=csvrows(SRC/'E2_trajectories.csv');index=defaultdict(dict)
    for r in rows:index[(r['case'],r['configuration'],r['method'],r['car'])][float(r['elapsed_s'])]=r
    result=[];mseidx={};max_endpoint_error=0
    for c in protocol['cases']:
        case=c['id']; saved=next(x for x in summary['cases'] if x['case']==case)
        for config in ('raw_walls','car2_p1_only','per_car_walls'):
            for car in ('car1','car2'):
                times=[float(x) for x in saved['configurations'][config]['independent']['endpoint_window_s']]
                assert times==saved['configurations'][config]['joint']['endpoint_window_s']
                ref=np.array(c['evaluation_only']['end_antenna_xyz_m'][car][:2])
                for method in ('independent','joint'):
                    rr=[index[(case,config,method,car)][s] for s in times]
                    xy=np.array([[float(r['antenna_x_m']),float(r['antenna_y_m'])] for r in rr])
                    err=xy-ref;mse=float(np.mean(np.sum(err**2,axis=1)))
                    endpoint=float(np.linalg.norm(np.median(xy,axis=0)-ref))
                    original=saved['configurations'][config][method]['endpoint_difference_m'][car]
                    max_endpoint_error=max(max_endpoint_error,abs(endpoint-original));assert abs(endpoint-original)<2e-12
                    row={'case':case,'paper_identity':f'E2-{protocol["cases"].index(c)+1}',
                     'date':'2026-10-18','configuration':config,'car':car,'method':method,
                     'window_start_s':min(times),'window_end_s':max(times),'n_common':len(times),
                     'mse_m2':mse,'rmse_cm':math.sqrt(mse)*100,'median_endpoint_difference_cm':endpoint*100,
                     'mean_offset_sq_m2':float(np.sum(err.mean(axis=0)**2)),
                     'spread_m2':float(np.mean(np.sum((xy-xy.mean(axis=0))**2,axis=1))),
                     'estimator':'historical_full_recording_batch'}
                    result.append(row);mseidx[(case,config,car,method)]=row
    contrasts=[]
    for c in protocol['cases']:
        for car in ('car1','car2'):
            def d(config):return mseidx[(c['id'],config,car,'joint')]['mse_m2']-mseidx[(c['id'],config,car,'independent')]['mse_m2']
            for corrected in ('car2_p1_only','per_car_walls'):
                contrasts.append({'case':c['id'],'car':car,'corrected_profile':corrected,
                  'D_raw_m2':d('raw_walls'),'D_corrected_m2':d(corrected),'C_m2':d(corrected)-d('raw_walls'),
                  'cooperative_order_reversal':d('raw_walls')*d(corrected)<0,
                  'independent_absolute_improves':mseidx[(c['id'],corrected,car,'independent')]['mse_m2']<mseidx[(c['id'],'raw_walls',car,'independent')]['mse_m2'],
                  'joint_absolute_improves':mseidx[(c['id'],corrected,car,'joint')]['mse_m2']<mseidx[(c['id'],'raw_walls',car,'joint')]['mse_m2']})
    writecsv(OUT/'E2_common_stop_MSE_36.csv',result);writecsv(OUT/'E2_calibration_contrasts_12.csv',contrasts)
    return contrasts,max_endpoint_error

def tidy(ax):
    ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',color='#ddd',lw=.45);ax.set_axisbelow(True)
def save(fig,name):
    for ext in ('pdf','png'):fig.savefig(FIG/f'{name}.{ext}',bbox_inches='tight',pad_inches=.04)
    plt.close(fig)

def figures(detail,calibration,hist):
    meta=read(SRC/'E3_recording_metadata.json');origin=meta[0]['receipt_origin_ns'];lookup={r['run_id']:r for r in meta}
    fig,axes=plt.subplots(2,1,figsize=(3.5,3.15),sharex=True,layout='constrained')
    boundary=((meta[3]['receipt_origin_ns']+meta[4]['receipt_origin_ns'])/2-origin)/6e10
    for i,car in enumerate(('car1','car2')):
        ax=axes[i];tidy(ax);ax.axhline(0,color='black',lw=.65)
        ax.axvspan(boundary,64,color='#f2f2f2',zorder=0)
        for arm,color,marker in [('J',RED,'o'),('W025',ORANGE,'^')]:
            rr=[r for r in calibration if r['car']==car and r['arm']==arm and r['phase']=='normal']
            xs=[(lookup[r['run_id']]['receipt_origin_ns']-origin)/6e10 for r in rr]
            ax.scatter(xs,[r['C_m2'] for r in rr],c=color,marker=marker,s=18,lw=.5,zorder=3)
        ax.set_ylabel('$C_i$ (m$^2$)');ax.set_title(f'({chr(97+i)}) Robot {i+1}',loc='left')
        ax.margins(y=.24)
        ax.text(.18,.94,'A ($n=4$)',transform=ax.transAxes,va='top',ha='center',fontsize=7)
        ax.text(.70,.94,'B ($n=6$)',transform=ax.transAxes,va='top',ha='center',fontsize=7)
        ax.set_xlim(-2,64)
    axes[-1].set_xlabel('Elapsed acquisition time (min)')
    fig.legend(handles=[Line2D([],[],color=c,marker=m,linestyle='none',label=l,markersize=4)
      for c,m,l in [(RED,'o','Cooperative'),(ORANGE,'^','Reduced ($\\lambda=0.25$)')]],
      loc='outside upper center',ncol=2,frameon=False)
    save(fig,'E3_calibration_change_chronology')
    fig,axes=plt.subplots(2,2,figsize=(7.0,3.7),sharey='row',layout='constrained')
    for i,car in enumerate(('car1','car2')):
        for j,geo in enumerate(('G1','G2')):
            ax=axes[i,j];tidy(ax)
            arr=[r for r in detail if r['phase']=='normal' and r['car']==car and r['run_id'].startswith(geo)]
            b=[];v=[]
            for profile in ('raw','historical'):
                for method in ('I','J','W025'):
                    rr=[r for r in arr if r['profile']==profile and r['method']==method]
                    b.append(np.mean([r['mean_offset_sq_m2'] for r in rr]));v.append(np.mean([r['within_window_spread_m2'] for r in rr]))
            xs=np.array([0,1,2,4,5,6])
            ax.scatter(xs-.10,b,s=19,marker='s',color=BLUE,label='Squared mean offset',zorder=3)
            ax.scatter(xs+.10,v,s=19,marker='o',color=ORANGE,label='Within-window spread',zorder=3)
            ax.set_yscale('log');ax.set_ylim(1e-7,1.)
            ax.axvline(3.,color='#bbb',lw=.5)
            ax.set_xticks(xs,['I','C','R','I','C','R']);ax.set_xlabel('Raw                         Corrected')
            ax.set_title(f'({chr(97+2*i+j)}) Robot {i+1}, placement {chr(65+j)}')
            if j==0:ax.set_ylabel('MSE component (m$^2$, log scale)')
    h,l=axes[0,0].get_legend_handles_labels();fig.legend(h,l,loc='outside upper center',ncol=2,frameon=False)
    save(fig,'E3_mean_offset_and_spread')
    fig,axes=plt.subplots(1,2,figsize=(7.,2.25),layout='constrained')
    for i,car in enumerate(('car1','car2')):
        ax=axes[i];tidy(ax);ax.axhline(0,color='black',lw=.65)
        for j,case in enumerate(('015334','033248','050447')):
            for off,profile,color,marker in [(-.13,'car2_p1_only',RED,'o'),(.13,'per_car_walls',ORANGE,'^')]:
                r=next(r for r in hist if r['case']==case and r['car']==car and r['corrected_profile']==profile)
                ax.scatter(j+off,r['C_m2'],color=color,marker=marker,s=25)
        ax.set_xticks([0,1,2],['E2-1','E2-2','E2-3']);ax.set_title(f'({chr(97+i)}) Robot {i+1}')
        ax.set_ylabel('$C_i$ (m$^2$)');ax.set_xlim(-.45,2.45)
    fig.legend(handles=[Line2D([],[],color=c,marker=m,linestyle='none',label=l,markersize=4)
     for c,m,l in [(RED,'o','Robot 2 calibrated'),(ORANGE,'^','Both robots calibrated')]],
     loc='outside upper center',ncol=2,frameon=False)
    save(fig,'E2_historical_calibration_change')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--collect-sources',action='store_true');args=ap.parse_args()
    for p in (SRC,OUT,FIG):p.mkdir(exist_ok=True)
    if args.collect_sources:collect()
    counts=inventory();detail,calibration,loo,maxerr=decompose();hist,eperr=historical()
    figures(detail,calibration,hist)
    meta=read(SRC/'E3_recording_metadata.json')
    summary={'date_hong_kong':'2026-11-04','inventory_rows':116,'inventory_group_counts':counts,
     'E3_recordings':len(meta),'E3_normal_paired_seconds':150,'E3_all_phase_paired_seconds':375,
     'E3_saved_trajectory_span_sum_s':sum(r['saved_trajectory_span_s'] for r in meta),
     'E3_acquisition_span_s':(max(r['receipt_origin_ns']+(r['last_saved_second'])*10**9 for r in meta)-min(r['receipt_origin_ns']+r['first_saved_second']*10**9 for r in meta))/1e9,
     'E3_raw_bag_hours':'not yet verified','E3_normal_T': [r for r in loo if r['phase']=='normal'],
     'E3_normal_max_spread_fraction':max(r['within_window_spread_m2']/r['mse_m2'] for r in detail if r['phase']=='normal'),
     'E2_contrasts':hist,'max_E3_MSE_identity_and_saved_value_error':maxerr,
     'max_E2_archived_endpoint_reproduction_error_m':eperr,
     'estimators_refitted':False,'historical_metrics_pooled_with_E3':False,
     'interpretation':'Chronology describes observed records. Placement and acquisition order are confounded. T remains a between-placement contrast.'}
    writej(OUT/'SUMMARY.json',summary)
    manifest={'sources':{str(p.relative_to(ROOT)):digest(p) for p in sorted(SRC.rglob('*')) if p.is_file()},
              'script_sha256':digest(Path(__file__))}
    writej(OUT/'SOURCE_MANIFEST.json',manifest)
    print(json.dumps({'inventory':counts,'E3_normal_T':summary['E3_normal_T'],
      'E2_C':hist,'verification_max_error':maxerr,'E2_endpoint_error':eperr},ensure_ascii=False,indent=2))

if __name__=='__main__':main()

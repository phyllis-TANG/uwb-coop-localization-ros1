"""Independent native quality arithmetic from frozen SPEC, not A qpolicy.

Audit state is a plain dictionary. No production online code is imported.
"""
import math
import numpy as np
from .common import require


def initial():return dict(mode='normal',gain=1.,warn=0,severe=0,clear=0,recover=0)


def step(previous,score,unknown_reason,p):
    s=dict(previous);before=s['mode']
    if unknown_reason is not None or score is None or not math.isfinite(score):
        for name in ('warn','severe','clear','recover'):s[name]=0
        return s,dict(state='unknown',policy_mode_held=s['mode'],reason=unknown_reason or 'NONFINITE_SCORE',information_multiplier=s['gain'],score=None,monitorable=False,transition=False)
    s['warn']=s['warn']+1 if score>=p['warn_score'] else 0;s['severe']=s['severe']+1 if score>=p['disable_score'] else 0;s['clear']=s['clear']+1 if score<=p['clear_score'] else 0
    mode=s['mode'];reason='CONSISTENT_FIXED_SHADOW'
    if mode=='normal':
        if s['severe']>=p['disable_count']:s.update(mode='disabled',gain=0.);reason='PERSISTENT_SEVERE_INCONSISTENCY'
        elif s['warn']>=p['warn_count']:s.update(mode='downweighted',gain=p['lowered_information']);reason='PERSISTENT_INCONSISTENCY'
        elif s['warn']:reason='PENDING_CONFIRMATION_BASE_WEIGHT'
    elif mode in ('downweighted','disabled'):
        if s['severe']>=p['disable_count']:s.update(mode='disabled',gain=0.);reason='PERSISTENT_SEVERE_INCONSISTENCY'
        elif s['clear']>=p['clear_count']:s.update(mode='recovering',gain=p['recovery_information'],recover=0);reason='CLEAR_PERSISTENCE_START_RECOVERY'
        else:reason='HYSTERESIS_HOLD_ATTENUATION'
    else:
        if score>=p['disable_score']:s.update(mode='disabled',gain=0.,recover=0);reason='RECOVERY_RELAPSE_SEVERE'
        elif score>=p['warn_score']:s.update(mode='downweighted',gain=p['lowered_information'],recover=0);reason='RECOVERY_RELAPSE'
        elif score<=p['clear_score']:
            s['recover']+=1;reason='RECOVERY_TRIAL'
            if s['recover']>=p['recover_count']:s.update(mode='normal',gain=1.);reason='RECOVERED_AFTER_HYSTERESIS'
        else:s['recover']=0;reason='RECOVERY_HOLD_NOT_CLEAR'
    answer=dict(state=s['mode'],policy_mode_held=s['mode'],reason=reason,information_multiplier=s['gain'],score=float(score),monitorable=True,transition=s['mode']!=before,persistence={k:s[k] for k in ('warn','severe','clear','recover')})
    return s,answer


def antenna_xyz(pose,model):
    x,y,yaw=pose[:3];lx,ly=model['base_to_antenna_body_xy_m'];return np.array([x+math.cos(yaw)*lx-math.sin(yaw)*ly,y+math.sin(yaw)*lx+math.cos(yaw)*ly,model['antenna_height_m']])


def score_gate(ledger,shadow,base,p,has_odom=True):
    """Native priority of unknown gates and independent 3D slant/XY geometry."""
    value=ledger['raw_aggregate_m'];target=ledger['target'];geometry=None;prediction=None;signed=None;score=None
    if value is None:reason='NO_CURRENT_AGGREGATED_LINK'
    elif not has_odom:reason='NO_ODOM_BRACKET'
    elif shadow is None:reason='SHADOW_NOT_AVAILABLE_AT_SAME_CUTOFF'
    elif not shadow['row']['accepted_graph']:reason='SHADOW_SOLVE_NOT_ACCEPTED'
    elif not shadow['row'].get('numerical_full_rank',False):reason='SHADOW_NUMERICAL_RANK_INSUFFICIENT'
    elif base['arm']=='F3' and not shadow['row']['angular_valid']:reason='SHADOW_ANGULAR_GAP'
    else:
        snap=shadow['row']['objective_snapshot'];others=sorted(k for k in snap['observations'][-1] if k!=target)
        if len(others)<p['min_other_links']:reason='INSUFFICIENT_OTHER_WALL_LINKS'
        else:
            point=antenna_xyz(shadow['row']['pose'],base['model']);delta=np.array([point-np.asarray(base['model']['anchors_xyz_m'][k]) for k in others]);dist=np.linalg.norm(delta,axis=1)
            if np.any(dist<1e-10):reason='DEGENERATE_SHADOW_GEOMETRY'
            else:
                singular=np.linalg.svd(delta[:,:2]/dist[:,None],compute_uv=False);ratio=float(singular[-1]/singular[0]) if singular[0]>0 else 0.;geometry=dict(other_links=others,singular_values=singular.tolist(),ratio=ratio)
                if ratio<p['min_xy_singular_ratio']:reason='WEAK_SHADOW_XY_GEOMETRY'
                else:
                    prediction=float(np.linalg.norm(point-base['model']['anchors_xyz_m'][target]));signed=value-base['model']['range_bias_m'][target]-prediction;score=abs(signed)/p['score_scale_m'];reason=None
    return score,reason,geometry,signed,prediction


def check_policy(actual,expected):
    require({k:x for k,x in actual.items() if k!='score'}=={k:x for k,x in expected.items() if k!='score'},'native state/persistence/unknown/hysteresis differs')
    score=expected['score'];require(actual['score'] is None if score is None else actual['score'] is not None and abs(actual['score']-score)<1e-10,'policy score differs')
    return True

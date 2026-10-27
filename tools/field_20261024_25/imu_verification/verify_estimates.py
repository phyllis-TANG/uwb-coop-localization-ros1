"""Read future A estimate CSV provenance against events; no A code imported."""
import csv
import json
import math
from pathlib import Path
from causal_usage import covariance_check


def check_estimate_rows(rows,lookup,origin):
    checked=0;modes={}
    for e in rows:
        mode=e['motion_mode'];car=e['vehicle_id'];publish=int(e['publish_receive_epoch_ns'])
        if car not in ('car1','car2') or mode not in ('legacy_odom_pose','body_odom_rate','body_imu_fixed_bias','body_imu_bias'):
            raise ValueError('output car/mode identity')
        if abs(float(e['canonical_time_s'])-(publish-origin)/1e9)>1e-12:raise ValueError('canonical publication arithmetic')
        for stem,kind in [('last_velocity','odom'),('last_imu','imu')]:
            record=e.get(stem+'_record_index','')
            if record=='':continue
            key=(kind,int(record))
            if key not in lookup:raise ValueError('output references missing input')
            r=lookup[key]
            if r['vehicle_id']!=car or r['receive_epoch_ns']>publish:raise ValueError('future or cross-car output provenance')
            for target,original in [('_header_epoch_ns','header_epoch_ns'),('_receive_epoch_ns','receive_epoch_ns')]:
                if int(e[stem+target])!=r[original]:raise ValueError('output source ns changed')
        if mode=='legacy_odom_pose':
            if any(e.get(k,'')!='' for k in ('gyro_bias_rad_s','gyro_bias_variance','last_imu_record_index')) or e['imu_mode_status']!='legacy_not_used':
                raise ValueError('legacy posterior misrepresented as augmented state')
        elif e.get('gyro_bias_variance','')!='':
            b,var=float(e['gyro_bias_rad_s']),float(e['gyro_bias_variance'])
            if not math.isfinite(b) or not math.isfinite(var) or var<0:raise ValueError('invalid residual bias state/variance')
        if e.get('pose_covariance','')!='':covariance_check(json.loads(e['pose_covariance']),3)
        if str(e['valid'])=='1' and not all(math.isfinite(float(e[k])) for k in ('x_m','y_m','yaw_rad')):raise ValueError('valid pose nonfinite')
        checked+=1;modes[mode]=modes.get(mode,0)+1
    return {'rows_checked':checked,'motion_modes':modes,'scope':'identity/time/numeric output audit only; propagation ledger and frozen-legacy comparison are additional checks'}

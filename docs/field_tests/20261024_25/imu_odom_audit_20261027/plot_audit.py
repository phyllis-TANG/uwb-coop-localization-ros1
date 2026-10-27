"""Post-audit signal visualization only; no tuning, calibration or estimator."""
import csv,gzip,math
from pathlib import Path
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

rows={}
with gzip.open(Path(sys.argv[1])/'pair_observations.csv.gz','rt') as f:
    for row in csv.DictReader(f):rows.setdefault((row['experiment'],row['vehicle']),[]).append(row)
fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
for col,key in enumerate((('T08','car2'),('T10','car2'))):
    r=rows[key];ns=np.array([int(x['odom_header_ns']) for x in r],dtype=np.int64);seconds=(ns-ns[0])/1e9
    axes[0,col].plot(seconds[::4],[float(x['odom_rate_z']) for x in r][::4],label='Odom angular z',lw=1.4)
    axes[0,col].plot(seconds[::4],[float(x['gyro_z']) for x in r][::4],label='IMU gyro z',lw=.8,alpha=.7)
    axes[0,col].set(title=' / '.join(key),xlabel='Own source-header relative time (s)',ylabel='Angular rate (rad/s)')
for col,key in enumerate((('T08','car1'),('T10','car2'))):
    r=rows[key];ns=np.array([int(x['odom_header_ns']) for x in r],dtype=np.int64);seconds=(ns-ns[0])/1e9
    gyro=np.array([float(x['gyro_z']) for x in r]);dt=np.diff(np.array([int(x['imu_header_ns']) for x in r],dtype=np.int64))/1e9
    integrals=np.r_[0,np.cumsum(np.where((dt>0)&(dt<=.1),.5*(gyro[1:]+gyro[:-1])*dt,0))]
    odom=np.unwrap([float(x['odom_yaw']) for x in r]);odom-=odom[0]
    axes[1,col].plot(seconds,np.degrees(odom),label='Odom yaw change (not truth)')
    axes[1,col].plot(seconds,np.degrees(integrals),label='Uncorrected gyro integral (paired samples)')
    axes[1,col].set(title=' / '.join(key)+' | nominally stationary vehicle',xlabel='Own source-header relative time (s)',ylabel='Signal angle change (deg)')
for ax in axes.flat:ax.grid(alpha=.25);ax.legend(fontsize=8)
fig.suptitle('IMU / Odom readiness audit | no accepted bias calibration or localization accuracy evaluation')
fig.savefig(Path(sys.argv[2]),dpi=140)

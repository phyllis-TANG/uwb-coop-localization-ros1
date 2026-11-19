"""Offline synthetic calibration only. The exported model contains no evaluation states."""
import csv
import json
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/two_car_fixed_lag_fgo_v1'))
import simulate as sim

OUT=ROOT/'docs/research/midterm_dual_robot_contract_a/calibration_v1'
CARS=('car1','car2')
TEMPLATE=json.loads(sim.CONFIG.read_text())['models']


def distance(xy):
    heights=[TEMPLATE[c]['antenna_height_m'] for c in CARS]
    xyz=np.column_stack((xy,heights))
    anchors=TEMPLATE['car1']['anchors_xyz_m']
    a=np.array([anchors[k] for k in sorted(anchors)])
    return np.r_[np.linalg.norm(xyz[:,None]-a,axis=2).ravel(),np.linalg.norm(xyz[1]-xyz[0])]


def capture(seed,times,train):
    cfg,events,_,_=sim.make_case(seed,'nominal')
    frames={(e['vehicle_id'],e['header_epoch_ns']):e for e in events if e['kind']=='uwb'}
    rng=np.random.default_rng(np.random.SeedSequence([seed,397]))
    for t in times:
        raw=[frames[c,sim.EPOCH_NS+t*10**9] for c in CARS]
        ranges=[e['value'][k] for e in raw for k in sorted(TEMPLATE['car1']['anchors_xyz_m'])]
        ranges.append(raw[0]['value']['node_0'])
        if train:
            xy=np.array([cfg['models'][c]['start_antenna_xyz_m'][:2] for c in CARS])
        else:
            # Isolated instrument simulator. Only noisy reference readings leave this block.
            xy=np.array([sim.antenna_xyz(sim.true_pose(t,c,TEMPLATE[c]),TEMPLATE[c])[:2] for c in CARS])
            xy+=rng.normal(0,.08,(2,2))
        yield dict(seed=seed,t=t,xy=xy.tolist(),ranges=ranges,
                   heading=[cfg['models'][c]['initial_heading_deg'] for c in CARS] if train else None)


def residual(row):
    return row['ranges']-distance(row['xy'])


def write_csv(name,rows):
    with (OUT/name).open('w') as f:
        w=csv.DictWriter(f,rows[0],lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


def main():
    train=[r for seed in range(700001,700033) for r in capture(seed,[1],True)]
    valid=[r for seed in range(800001,800033) for r in capture(seed,[12,27,48],False)]
    joint=np.array([np.r_[np.ravel(r['xy']),residual(r)] for r in train])
    mean=joint.mean(axis=0)
    cov=np.cov(joint.T)/len(train)
    cov+=np.diag(np.r_[np.maximum(0,.08**2/32-np.diag(cov)[:4]),np.zeros(9)])
    heading=np.deg2rad([r['heading'] for r in train])
    angle=np.angle(np.exp(1j*heading).mean(axis=0))
    angle_se=np.maximum(2/np.sqrt(32),np.rad2deg(np.angle(np.exp(1j*(heading-angle)))).std(axis=0,ddof=1)/np.sqrt(32))
    good=np.ones(9,dtype=bool)
    table=[]
    for t in (12,27,48):
        a=np.array([residual(r) for r in valid if r['t']==t])
        shift=a.mean(axis=0)-mean[4:]
        upper=np.abs(shift)+1.96*np.sqrt(np.diag(cov)[4:]+a.var(axis=0,ddof=1)/len(a))
        good &= upper<=.05
        for i in range(9):
            table.append(dict(t=t,link=i,correction_m=mean[4+i],validation_offset_m=shift[i],screen_upper_m=upper[i],passes=bool(upper[i]<=.05)))
    model=dict(mean=mean.tolist(),covariance=cov.tolist(),stable=good.tolist(),
               mean_heading_deg=np.rad2deg(angle).tolist(),heading_se_deg=angle_se.tolist())
    (OUT/'calibration.json').write_text(json.dumps(model,indent=2)+'\n')
    (OUT/'survey_readings.json').write_text(json.dumps(dict(train=train,validation=valid),indent=1)+'\n')
    write_csv('link_validation.csv',table)
    print('stable links',good,'survey',mean[:4],np.sqrt(np.diag(cov)[:4]))

if __name__=='__main__':
    main()

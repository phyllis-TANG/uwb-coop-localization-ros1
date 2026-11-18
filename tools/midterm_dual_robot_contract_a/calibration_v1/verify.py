"""Independent checks from synthetic instrument readings and archived vehicle epochs."""
import csv
import gzip
import json
import math
from bisect import bisect_right
import numpy as np
from calibrate import OUT,TEMPLATE,CARS
from development import blob,EVAL,FREEZE

def residual(r):
    xyz=[[*p,TEMPLATE[c]['antenna_height_m']] for p,c in zip(r['xy'],CARS)]
    a=TEMPLATE['car1']['anchors_xyz_m']
    prediction=[math.dist(p,a[k]) for p in xyz for k in sorted(a)]+[math.dist(*xyz)]
    return np.subtract(r['ranges'],prediction)

def main():
    data=json.loads((OUT/'survey_readings.json').read_text())
    model=json.loads((OUT/'calibration.json').read_text())
    train,valid=data['train'],data['validation']
    assert len(train)==32 and len(valid)==96
    assert not {r['seed'] for r in train}&{r['seed'] for r in valid}
    samples=np.array([list(np.ravel(r['xy']))+list(residual(r)) for r in train])
    avg=samples.mean(axis=0)
    covariance=(samples-avg).T@(samples-avg)/(32*31)
    for i in range(4):
        covariance[i,i]=max(.08**2/32,covariance[i,i])
    np.testing.assert_allclose(model['mean'],avg,atol=1e-14)
    np.testing.assert_allclose(model['covariance'],covariance,atol=1e-14)
    good=np.ones(9,dtype=bool)
    for t in (12,27,48):
        a=np.asarray([residual(r) for r in valid if r['t']==t])
        good&=(abs(a.mean(axis=0)-avg[4:])+1.96*np.sqrt(a.var(axis=0,ddof=1)/32+covariance.diagonal()[4:])<=.05)
    np.testing.assert_array_equal(good,model['stable'])
    table=list(csv.DictReader((OUT/'clock.csv').open()))
    assert len(table)==len({(r['scene'],r['arm'],r['car']) for r in table})==16
    for scene in ('nominal','wall'):
        truth=json.loads(gzip.decompress(blob(EVAL,'docs/research/ground_continuous_b/runs/101_'+scene+'/truth.json.gz')))
        for arm in ('baseline','survey','survey_links'):
            ep=json.loads(gzip.decompress((OUT/f'{scene}_{arm}.json.gz').read_bytes()))
            assert [e['t'] for e in ep]==list(range(1,64))
            if arm=='baseline':
                old=json.loads(gzip.decompress(blob(FREEZE,'docs/research/midterm_dual_robot_contract_a/round2/dev/101_'+scene+'/epochs.json.gz')))
                for a,b in zip(ep,old):
                    assert a['action']==b['action']
                    np.testing.assert_allclose(a['bias'],b['bias'],rtol=0,atol=1e-12)
                    for c,d in zip(a['cars'],b['cars']):
                        np.testing.assert_allclose(c['xy'],d['xy'],rtol=0,atol=1e-12)
                        if a['action']=='ACCEPT':
                            np.testing.assert_allclose(c['hcpl']['history'],d['hcpl']['history'],rtol=0,atol=1e-12)
            if arm=='survey_links':
                for e in ep:
                    np.testing.assert_allclose(np.array(e['bias'])[good],avg[4:][good],atol=1e-14)
                    np.testing.assert_allclose(np.array(e['covariance_diag'])[4:][good],covariance.diagonal()[4:][good],atol=1e-14)
            ready=[e['ready'] for e in ep]
            for car in (1,2):
                available=exposed=later=fault=0
                recovery=None
                for i,pair in enumerate(truth):
                    now=i/20
                    j=bisect_right(ready,now)-1
                    if j<0 or ep[j]['expiry']<now: continue
                    c=ep[j]['cars'][car-1]
                    pl=c['hcpl']['history']
                    if pl is None or pl>.10: continue
                    available+=1
                    later+=ep[j]['t']>=2
                    unsafe=math.dist(c['xy'],pair[car-1])>.10
                    exposed+=unsafe
                    fault+=unsafe and 24<=now<38
                    if now>=38 and recovery is None: recovery=now
                row=next(r for r in table if (r['scene'],r['arm'],r['car'])==(scene,arm,str(car)))
                assert [available/20,exposed/20,later/20]==[float(row[k]) for k in ('available_s','exposed_s','later_available_s')]
                if scene=='wall':
                    assert fault/20==float(row['fault_exposed_s'])
                    assert ('' if recovery is None else str(recovery))==row['first_available_after_clear_s']
    print('PASS: survey joint covariance, 9 link screens, 2 baseline regressions, fixed means/variances, 12 per-car HCPL clock scores.')

if __name__=='__main__':
    main()

"""Find interior joint points, then construct rational enclosures for their evidence."""
import csv
import gzip
import hashlib
import json
import math
from fractions import Fraction as F
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT/'docs/research/ground_b_round3'

S = 10**12
VAR = F(1,625)
BOUND = F(3,5)


def root(q):
    i=math.isqrt(q.numerator*S*S//q.denominator)
    return F(i,S),F(i+(i*i*q.denominator!=q.numerator*S*S),S)


def dist2(p,s):
    return sum((F(x)-F(y))**2 for x,y in zip(p,s,strict=True))


def square_bounds(lo,hi):
    return max(lo,-hi,0)**2,max(abs(lo),abs(hi))**2


def candidates(row):
    obs=row['obs']
    cert=row['region']
    centers=[[tuple((l+u)/2e6 for l,u in box) for box,_ in cells] for cells in cert['cells']]
    xyz=[ [(*xy,obs['heights'][c]) for xy in group] for c,group in enumerate(centers)]
    loss=[[sum((math.dist(p,a)-y)**2 for a,y in zip(obs['anchors'],obs['ranges'][4*c:4*c+4]))
           for p in group] for c,group in enumerate(xyz)]
    for i,js in cert['joint']:
        for j in js:
            gap=max(0,abs(obs['ranges'][8]-math.dist(xyz[0][i],xyz[1][j]))-.6)
            if loss[0][i]+loss[1][j]+gap**2<.04159:
                yield centers[0][i],centers[1][j]


def evidence(xy,obs):
    points=[[F(str(v)) for v in p] for p in xy]
    xyz=[[*p,F(h)] for p,h in zip(points,obs['heights'])]
    pairs=[(p,a) for p in xyz for a in obs['anchors']]+[tuple(xyz)]
    # Residual convention: measurement minus slant minus peer-only bias.
    raw=[]
    for (p,a),y in zip(pairs,obs['ranges']):
        lo,hi=root(dist2(p,a))
        raw.append((F(y)-hi,F(y)-lo))
    sq=[square_bounds(*r) for r in raw[:8]]
    margin_lo=26*VAR-sum(hi for _,hi in sq)
    margin_hi=26*VAR-sum(lo for lo,_ in sq)
    width_lo=root(margin_lo)[0]
    width_hi=root(margin_hi)[1]
    lo,hi=raw[-1]
    inner=(max(-BOUND,hi-width_lo),min(BOUND,lo+width_lo))
    outer=(max(-BOUND,lo-width_hi),min(BOUND,hi+width_hi))
    assert inner[0]<inner[1]
    bias=sum(inner)/2
    residuals=raw[:8]+[(lo-bias,hi-bias)]
    stat=sum(square_bounds(*r)[1] for r in residuals)/VAR
    upper=F(math.floor(stat*10**9)+1,10**9)
    assert upper<26
    return dict(xy_m=[list(map(str,p)) for p in points],bias_m=str(bias),
                feasible_bias_inner_m=list(map(str,inner)),feasible_bias_outer_m=list(map(str,outer)),
                residual_intervals_m=[list(map(str,r)) for r in residuals],weighted_stat_strict_upper=str(upper))


def main():
    witnesses=[]
    table=[]
    with (ROOT/'docs/research/ground_b_round2/evaluation/resolution.csv').open() as f:
        radii={(r['scene'],int(r['car']),r['resolution_m']):r['radius_m'] for r in csv.DictReader(f)}
    for scene in ('nominal','peer_step','wall'):
        path=ROOT/f'docs/research/ground_continuous_b/runs/101_{scene}/records.json.gz'
        with gzip.open(path,'rt') as f:
            row=next(r for r in json.load(f) if r['t']==30)
        valid=list(candidates(row))
        for c in range(2):
            record=dict(scene=scene,car=c+1,any_center_lower_m='',G1_lower_m='',outer_05_m=radii[scene,c+1,'0.05'],
                        outer_025_m=radii[scene,c+1,'0.025'],pair_distance_lower_m='',status='EMPTY')
            if scene=='wall':
                assert not row['region']['joint']
            else:
                p=max(valid,key=lambda z:math.dist(z[c],row['xy'][c]))
                s=max(valid,key=lambda z:math.dist(z[c],p[c]))
                proof=[evidence(z,row['obs']) for z in (p,s)]
                proj=[list(map(F,w['xy_m'][c])) for w in proof]
                separation=root(dist2(*proj))[0]
                g1=max(root(dist2(x,row['xy'][c]))[0] for x in proj)
                # Publish lower bounds rounded DOWN to whole micrometres.
                def lower(x):
                    return f'{(x*10**6).__floor__()/10**6:.6f}'
                record.update(any_center_lower_m=lower(separation/2),G1_lower_m=lower(g1),
                              pair_distance_lower_m=lower(separation),status='PROVED' if separation>F(1,5) else 'UNRESOLVED')
                witnesses.append(dict(scene=scene,seed=101,state_s=30,car=c+1,
                    records_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),witnesses=proof))
            table.append(record)
    with (DOC/'witness_residuals.csv').open('w') as f:
        writer=csv.writer(f,lineterminator='\n')
        writer.writerow(['scene','target_car','witness','link','residual_lower_m','residual_upper_m','bias_m','weighted_stat_strict_upper'])
        for e in witnesses:
            path=ROOT/f"docs/research/ground_continuous_b/runs/101_{e['scene']}/records.json.gz"
            with gzip.open(path,'rt') as stream:
                obs=next(r['obs'] for r in json.load(stream) if r['t']==30)
            links=[f'car{c}:{key}' for c in (1,2) for key in obs['anchor_order']]+['car1:peer']
            for n,w in enumerate(e['witnesses'],1):
                for link,(lo,hi) in zip(links,w['residual_intervals_m'],strict=True):
                    writer.writerow([e['scene'],e['car'],n,link,lo,hi,w['bias_m'],w['weighted_stat_strict_upper']])
    (DOC/'witnesses.json').write_text(json.dumps(witnesses,indent=2)+'\n')
    with (DOC/'radius_bounds.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=table[0],lineterminator='\n')
        w.writeheader()
        w.writerows(table)

if __name__=='__main__':
    main()

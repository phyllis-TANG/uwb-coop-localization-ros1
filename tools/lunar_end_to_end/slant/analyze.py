"""Zero-search readback of frozen certificates, projection unions and original noise event."""
import argparse,csv,gzip,hashlib,importlib.util,json
from fractions import Fraction as F
from freeze_inputs import DOC,write
from solver import distance,point

def union_area(rectangles):
    rects={tuple(F(x) for ab in r['box'] for x in ab) for r in rectangles}
    cuts=sorted({x for a,b,_,_ in rects for x in (a,b)})
    total=F(0)
    for left,right in zip(cuts,cuts[1:]):
        last=None
        for lo,hi in sorted((c,d) for a,b,c,d in rects if a<=left and right<=b):
            bottom=lo if last is None else max(lo,last)
            total+=(right-left)*max(0,hi-bottom)
            last=hi if last is None else max(last,hi)
    return total

def raw_event(m,e,n):
    p,s=[[point(v) for v in xyz[:2]] for xyz in e['xyz']]
    hs=list(map(F,m['heights']))
    ds=[distance(car,[point(x),point(y)],h-F(z)) for car,h in zip((p,s),hs) for x,y,z in m['anchors']]
    l,u=distance(p,s,hs[0]-hs[1]);bias=F(e['injected_bias']);ds.append((l+bias,u+bias))
    lo=hi=0
    for (l,u),y,v in zip(ds[:n],m['ranges'],m['variance']):
        y=F(y);lo+=max(0,l-y,y-u)**2/F(v);hi+=max(abs(l-y),abs(u-y))**2/F(v)
    return lo,hi

def main(src):
    lock=json.loads((DOC/'A_LOCK.json').read_text())
    for name,h in lock['files'].items():assert hashlib.sha256((src/name).read_bytes()).hexdigest()==h
    spec=importlib.util.spec_from_file_location('contract',src/'tools/midterm_dual_robot_contract_a/height_v1/checker.py');A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)
    rows=list(csv.DictReader((DOC/'LEDGER.csv').open()));assert len(rows)==24
    pairs=[];out=[]
    for row in rows:
        key=row['case'];method=row['method'];path=DOC/'results'/f'{key}_{method}';raw=(path/'certificate.json.gz').read_bytes();receipt=json.loads((path/'receipt.json').read_text())
        assert hashlib.sha256(raw).hexdigest()==receipt['certificate_sha256']
        c=json.loads(gzip.decompress(raw));x=json.loads((path/'input.json').read_text())
        assert A.check(x,c)['certificate_valid']
        unresolved=[n for n in c['nodes'] if n['kind'] in ('UNDECIDED','PENDING')]
        res=all(max(F(b)-F(a) for a,b in node['box'])<=F(1,20) for node in unresolved)
        assert res==(row['resolution_met']=='True')
        m=json.loads((DOC/'inputs'/f'{key}.json').read_text());e=json.loads((DOC/'evaluation'/f'{key}.json').read_text());lo,hi=raw_event(m,e,len(x['observations']))
        q=F(c['threshold_certificate']['tau'])
        assert (hi<=q or lo>q) and (hi<=q)==(row['original_event']=='True')
        vals=[union_area(c['projections'][car]['rectangles']) for car in 'ps']
        out.append(dict(case=key,method=method,event_lower=str(lo),event_upper=str(hi),p_union_m2=str(vals[0]),s_union_m2=str(vals[1]),pending=len(c['queue']),passed=True))
    for p,n in zip(out[::2],out[1::2]):
        assert p['case']==n['case']
        for car in 'ps':
            a=F(p[car+'_union_m2']);b=F(n[car+'_union_m2'])
            pairs.append(dict(case=p['case'],car=car,P4_union_m2=float(a),N4_union_m2=float(b),delta_m2=float(a-b),relative_percent=float(100*(a-b)/b)))
    for name,records in [('READBACK',out),('AREA_CHANGE',pairs)]:
        with (DOC/(name+'.csv')).open('w') as f:
            w=csv.DictWriter(f,fieldnames=list(records[0]),lineterminator='\n');w.writeheader();w.writerows(records)
if __name__=='__main__':
    from pathlib import Path
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);main(p.parse_args().source)

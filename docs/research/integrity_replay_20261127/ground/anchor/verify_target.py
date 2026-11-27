"""Refine only boxes that could change the 20 cm decision at the frozen centre."""
from fractions import Fraction as F
import csv
import json
from pathlib import Path
from check_anchor import BASE, Q, C, bounding_root, evaluate_bounds

def verify(a,robot,cap=500000):
    stack=[bounding_root(a)]
    tested=inside=rejected=0
    threshold=F(1,5)**2
    cost=evaluate_bounds(a)
    while stack and tested<cap:
        box=stack.pop(); tested+=1
        far=sum(max(abs(box[i][0]-C[i]),abs(box[i][1]-C[i]))**2 for i in (2*robot,2*robot+1))
        if far<=threshold:
            inside+=1
            continue
        lo,_=cost(box)
        if lo>Q:
            rejected+=1
            continue
        width=[b-a for a,b in box]
        axis=width.index(max(width))
        if width[axis]<=F(1,2000):
            return 'unresolved',tested,inside,rejected,len(stack)+1
        l,h=box[axis];mid=(l+h)/2
        stack.extend(box[:axis]+(interval,)+box[axis+1:] for interval in ((l,mid),(mid,h)))
    return ('certified_reported_centre' if not stack else 'unresolved'),tested,inside,rejected,len(stack)

def run():
    cases=json.loads((BASE/'certificates.json').read_text())
    rows=[]
    for cert in cases:
        a=F(cert['anchor_allowance']);j=cert['robot']-1
        if F(cert['checked_squared_lower_m2'])>F(1,25):
            result=('excluded_by_feasible_pair',0,0,0,0)
        else:
            result=verify(a,j)
        rows.append((float(a*100),j+1,*result))
    with (BASE/'target.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['anchor_offset_cm','robot','decision_at_20cm','visited','retained_inside_disk','rejected_by_cost','undecided']);w.writerows(rows)
    print(*rows,sep='\n')
if __name__=='__main__':run()

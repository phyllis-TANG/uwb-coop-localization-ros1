"""Development only: compare equal-height distances, boundary witnesses and a synthetic search."""
import json
from fractions import Fraction as F
from freeze_inputs import DOC,IDS,write
from solver import distance,evaluator,point,search
box=tuple(map(point,[0,0,3,4]))
assert distance(box[:2],box[2:],F(0))==(5,5)
m=dict(anchors=[[-1,0,0],[0,-1,0],[4,4,0],[3,5,0]],heights=[0,0],measurement_ids=IDS,ranges=[1,1,6,6,6,6,1,1,5],variance=['1/625']*9,bias=['-3/5','3/5'])
equal={}
for method in ('P4','N4'):
    l,u=evaluator(m,method)(box)
    # Independent planar oracle for the degenerate test point.
    from math import hypot
    oracle=sum((hypot(x-a,y-b)-v)**2*625 for (x,y),values in zip([(0,0),(3,4)],[m['ranges'][:4],m['ranges'][4:8]]) for (a,b,_),v in zip(m['anchors'],values))
    assert abs(float(l)-oracle)<1e-9 and abs(float(u)-oracle)<1e-9
    equal[method]=float(l)
witness={}
for w in json.loads((DOC.parent/'interface/counterexample.json').read_text()):
    case=dict(m,anchors=w['anchors'],heights=[w['p'][2],w['s'][2]],ranges=w['observation'])
    pos=tuple(map(point,w['p'][:2]+w['s'][:2]))
    l,u=evaluator(case,w['method'])(pos)
    assert u<w['threshold']
    flat=dict(case,heights=[0,0],anchors=[[x,y,0] for x,y,_ in case['anchors']])
    flat_lower=evaluator(flat,w['method'])(pos)[0]
    assert flat_lower>w['threshold']
    witness[w['method']]=[float(u),float(flat_lower)]
m.update(heights=[1,2],ranges=['1.4142','1.4142','5.7446','5.9161','6','6.1644','2.2361','2.2361','5.0990'])
r=search(m,'P4',[['-.1','.1'],['-.1','.1'],['2.9','3.1'],['3.9','4.1']])
assert r['counts'].get('UNDECIDED',0)>0 and not r['queue']
write(DOC/'DEVELOPMENT.json',dict(equal_height=equal,boundary_slant_upper_planar_lower=witness,synthetic_counts=r['counts'],formal_runs=0))

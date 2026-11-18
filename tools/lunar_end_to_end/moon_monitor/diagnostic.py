"""Off-contract anchor-only q=26 diagnostic, with exact cut/label replay."""
from collections import deque
from monitor import *
from evaluate_monitor import save_csv

def anchor26(m,root,E,A,x):
    from solver import evaluator
    bounds=evaluator(m,'N4')
    queue=deque([('',tuple(tuple(map(F,p)) for p in root))])
    nodes=[];start=perf_counter()
    while queue:
        if len(nodes)>=50000 or perf_counter()-start>=30:raise TimeoutError('diagnostic search budget')
        key,box=queue.popleft()
        lo,hi=bounds(box);widths=[b-a for a,b in box];axis=widths.index(max(widths))
        kind='OUTSIDE' if lo>26 else 'INSIDE' if hi<=26 else 'UNDECIDED' if max(widths)<=F(1,20) else 'SPLIT'
        if kind=='SPLIT':
            a,b=box[axis];mid=(a+b)/2
            for suffix,pair in [('0',(a,mid)),('1',(mid,b))]:
                queue.append((key+suffix,box[:axis]+(pair,)+box[axis+1:]))
        nodes.append(dict(id=key,box=[[str(a),str(b)] for a,b in box],kind=kind))
    ctx=A.Context(x,root);by={n['id']:n for n in nodes}
    assert ctx.box(by['']['box'])==ctx.box(root)
    seen=set();stack=['']
    while stack:
        key=stack.pop();seen.add(key);n=by[key];z=ctx.box(n['box']);kind=n['kind']
        if kind=='SPLIT':
            l,r=[ctx.box(by[key+s]['box']) for s in '01']
            diff=[i for i in range(4) if l[i]!=r[i]]
            assert len(diff)==1
            i=diff[0];assert l[i][0]==z[i][0]<l[i][1]==r[i][0]<r[i][1]==z[i][1]
            assert all(l[j]==r[j]==z[j] for j in range(4) if j!=i)
            stack.extend([key+'0',key+'1'])
        else:
            lo,hi=ctx.bounds_parsed(z,'no_peer')
            assert (kind=='OUTSIDE' and lo>26 or kind=='INSIDE' and hi<=26 or kind=='UNDECIDED' and max(b-a for a,b in z)<=F(1,20))
    assert seen==set(by)
    return nodes

def stats(nodes):
    from analyze import union_area
    out={}
    for label,leaves in [('inner',[n for n in nodes if n['kind']=='INSIDE']),('outer',[n for n in nodes if n['kind'] in ('INSIDE','UNDECIDED')])]:
        out[label+'_joint_m4']=float(sum(math.prod(F(b)-F(a) for a,b in n['box']) for n in leaves))
        for car,k in [('p',0),('s',2)]:
            out[label+'_'+car+'_m2']=float(union_area([dict(box=n['box'][k:k+2]) for n in leaves]))
    return out

def subset(left,right):
    # Same root and longest-axis midpoint rule. Compare the two tree partitions.
    l={n['id']:n for n in left};r={n['id']:n for n in right}
    def visit(a,b):
        u,v=l[a]['kind'],r[b]['kind']
        if u=='OUTSIDE' or v in ('INSIDE','UNDECIDED'):return True
        if u!='SPLIT' and v=='OUTSIDE':return False
        return all(visit(a+s if u=='SPLIT' else a,b+s if v=='SPLIT' else b) for s in '01')
    return visit('','')

def run():
    E,A,_=modules();result=[]
    for e in read(D/'events.json'):
        if not e['old']:continue
        key=e['case']
        m=read(CACHE/OLD/SLANT/'inputs'/(key+'.json'))
        payload=read(D/'certificates'/(key+'_N4.json.gz'))
        x=payload['original'];root=A.event_root(x)
        n24=payload['certificate']['nodes']
        n26=anchor26(m,root,E,A,x)
        dump(D/'diagnostic'/(key+'.json.gz'),dict(original=x,diagnostic_threshold=26,nodes=n26))
        p26=read(D/'certificates'/(key+'_P4.json.gz'))['certificate']['nodes']
        for label,nodes in [('N4(24)',n24),('N4(26)',n26),('P4(26)',p26)]:
            result.append(dict(case=key,method=label,outer_subset_of_N4_26=subset(nodes,n26),**stats(nodes)))
    save_csv('threshold_diagnostic.csv',result)

if __name__=='__main__':run()

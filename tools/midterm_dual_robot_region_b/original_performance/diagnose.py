"""Replay saved inputs, measure wall components, and count disjoint subtree unions."""
import copy,csv,gzip,tempfile
from time import perf_counter
from study import *
from common import canonical
from precontraction.formal import READY
from common import load_module

def diagnose(saved):
    candidate=checker()
    _,a=load_a(LOCK)
    times=[]
    for old in csv.DictReader((DOC/'checker_v2/COSTS.csv').open()):
        if old['method']!='P4' or old['group']!='main':continue
        unit=old['id']
        r=read(saved/(unit+'.result.json.gz'));tree=r['result'];case=r['case'];s=r['settings'];m=case['model']
        row=dict(id=unit,historical_wall=old['full_wall_seconds'])
        def timed(name,fn,*args):
            start=perf_counter()
            result=fn(*args)
            row[name]=perf_counter()-start
            return result
        ref=timed('B',b_fast.audit,m,'P4',s,tree)
        assert ref==timed('B_candidate',candidate.audit,m,'P4',s,tree)
        proj=timed('projection',b_fast.projections,m,tree)
        timed('projection_audit',b_fast.audit_projection,m,tree,proj)
        cert=timed('conversion',b_fast.make_certificate,case,'P4',s,tree,proj)
        assert cert==read(saved/(unit+'.certificate.json.gz'))
        verdict=timed('A',a.check,case['a_input'],cert)
        assert verdict==r['certificate_a']['validation']
        data=timed('serialization',canonical,cert)
        blob=timed('compression',gzip.compress,data,6)
        with tempfile.TemporaryFile(dir=D) as f:
            start=perf_counter();f.write(blob);f.flush();os.fsync(f.fileno());row['write_fsync']=perf_counter()-start
        times.append(row)
    # Corrupt the independent B tree in four different ways.
    for change in ('root','queue','leaf','counts'):
        broken=copy.deepcopy(tree)
        if change=='root':broken['nodes'][0]['box'][0]=['77','78']
        elif change=='queue':broken['queue'].append('invalid')
        elif change=='leaf':next(n for n in broken['nodes'] if n['status']=='OUTSIDE')['status']='INSIDE'
        else:broken['counts']={}
        for audit in (b_fast.audit,candidate.audit):
            try:audit(m,'P4',s,broken)
            except (AssertionError,ValueError):continue
            raise RuntimeError('accepted '+change)
    write(D/'diagnostics.json',times)
    contract=load_module('root_contract',ROOT/READY['entry'])
    prune=[]
    for case in dict.fromkeys(s['case'] for s in PLAN['jobs']):
        root=OLD/'runs/pilot'
        proof=read(root/(case+'_contracted')/'proof.json.gz')
        check=contract.check_composite(proof['original'],proof['certificate'])
        assert check['accepted']
        box=check['preprocessing']['contracted_domain']
        box=None if box is None else [[Fraction(x) for x in v] for v in box]
        nodes={n['path']:n for n in read(root/(case+'_original')/'tree.json.gz')['nodes']}
        selected=unique=0
        stack=[('',False)]
        while stack:
            path,covered=stack.pop();n=nodes[path]
            if not covered:
                covered=box is None or any(Fraction(b)<lo or Fraction(a)>hi for (a,b),(lo,hi) in zip(n['box'],box))
                selected+=int(covered)
            unique+=int(covered)
            if n['status']=='SPLIT':stack.extend([(path+'0',covered),(path+'1',covered)])
        prune.append(dict(case=case,subtrees=selected,unique=unique,total=len(nodes),fraction=unique/len(nodes),strict_empty=box is None))
    write(D/'pruning.json',prune)


if __name__=='__main__':diagnose(Path(sys.argv[1]))

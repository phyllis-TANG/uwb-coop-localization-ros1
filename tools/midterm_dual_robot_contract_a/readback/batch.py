"""Read certificates and the execution ledger from one immutable Git commit."""
import argparse
import csv
import gzip
import hashlib
import io
import json
import re
import subprocess
import sys
from collections import Counter
from fractions import Fraction as Q
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parents[1]
DOC = 'docs/research/midterm_dual_robot_contract_a'
B = 'docs/research/midterm_dual_robot_region_b/precontraction/LEDGER.csv'
PLAN = '1bd7b8aeca0a3748da3b97d2f8457a3705ff1078'
IMPL = 'd3dc0dc8a028de569fa84941cb09ab801c8e5ed8'


def blob(commit, path):
    return subprocess.check_output(['git', 'show', f'{commit}:{path}'], cwd=ROOT)


for name in ['precontract_v1/contract.py', 'checker_v2.py', 'core.py']:
    file = TOOLS / name
    if file.read_bytes() != blob(IMPL, file.relative_to(ROOT)):
        raise RuntimeError(f'checker version mismatch at {file}')
sys.path.insert(0, str(TOOLS / 'precontract_v1'))
import contract as C


def ledger(data):
    return list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))


def key(row):
    return tuple(row[k] for k in ('phase', 'case', 'arm'))


def budget(row, x, tree, pre):
    fields = ['preprocess_s','preprocessing_certificate_s','search_s','A_check_s',
              'B_check_s','conversion_s','projection_s','io_s','total_s','peak_rss_bytes']
    values = {k: Q(row[k]) for k in fields if row.get(k)}
    if any(v < 0 for v in values.values()):
        return 'FAIL'
    limits = dict(total_s=120, peak_rss_bytes=2**30, preprocess_s=4,
                  search_s=min(30,Q(x['budget']['max_seconds'])))
    if any(values[k] > limit for k,limit in limits.items() if k in values):
        return 'FAIL'
    if any(v > values['total_s'] for k,v in values.items()
           if 'total_s' in values and k not in ('total_s','peak_rss_bytes')):
        return 'FAIL'
    if tree and tree['cost']['processed_nodes'] > min(50000,x['budget']['max_nodes']):
        return 'FAIL'
    if pre and (Q(pre['cost']['preprocess_seconds']) > 4 or
                any(Q(d['elapsed_seconds']) > Q('1/2') for d in pre['directions'])):
        return 'FAIL'
    return 'PASS' if len(values)==len(fields) else 'UNKNOWN'


def check(row,x,cert):
    arm=row['arm']
    composite='preprocessing' in cert
    mode={'original':'4d','contracted':'4d','P4':'4d','J5':'5d','N4':'no_peer'}[arm]
    if (arm=='contracted' and not composite) or (composite and arm not in ('P4','contracted')):
        raise ValueError('certificate type disagrees with arm')
    if composite:
        result=C.check_composite(x,cert)
        tree=cert['search_certificate']
        domain=result['preprocessing']['contracted_domain']
    else:
        tree=cert
        C.V2.check(x,tree)
        domain=x['domains'][:4]
    if tree and tree['mode']!=mode:
        raise ValueError('wrong mode')
    nodes=tree['nodes'] if tree else []
    pending=tree['queue'] if tree else []
    # INSIDE leaves are analytically decided. Only unresolved leaves require tolerance.
    resolved=not pending and all(Q(b)-Q(a)<=Q('0.05') for n in nodes
              if n['kind']=='UNDECIDED' for a,b in n['box'])
    keep=[n for n in nodes if n['kind'] in ('INSIDE','PENDING','UNDECIDED')]
    probes={'queue_size':len(pending),'retained_leaves':len(keep)}
    case=row['case']
    if case in ('empty','empty_in_domain'):
        probes['strict_empty']=not keep
    if case=='forced_budget':
        probes['forced_stop_with_queue']=bool(pending)
    witnesses={'boundary':[['1','0','0','0']], 'domain_closed_contact':[['6','0','2','0']],
               'coincident_zero_distance':[['1']*4], 'collinear':[['0','1','0','-1'],['0','-1','0','1']],
               'collinear_b0_zero':[['-1','1','2','3/2'],['-1','-1','2','-3/2']]}
    for i,point in enumerate(witnesses.get(case,[])):
        probes[f'witness_{i}_retained']=any(all(Q(a)<=Q(v)<=Q(b) for (a,b),v in zip(n['box'],point)) for n in keep)
    return dict(inclusion='PASS',resolution='PASS' if resolved else 'FAIL',
                budget=budget(row,x,tree,cert.get('preprocessing')),checks=probes,
                mechanism='FAIL' if False in [v for v in probes.values() if type(v)==bool] else 'PASS'), domain, tree


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('sha')
    p.add_argument('ledger',help='CSV path in evidence commit, or fixtures')
    p.add_argument('output',type=Path)
    p.add_argument('--index',help='optional CSV in same commit mapping phase,case,arm to certificate_path')
    args=p.parse_args()
    if not re.fullmatch('[0-9a-f]{40}',args.sha):
        p.error('full commit SHA required')
    sample=args.ledger=='fixtures'
    if sample and args.sha!=IMPL:
        p.error('fixtures require published implementation SHA')
    if sample:
        rows=[dict(phase='sample',case=k,arm='contracted',status='FIXTURE') for k in ('normal','collinear','boundary','empty')]
    else:
        rows=ledger(blob(args.sha,args.ledger))
        if Counter(map(key,rows))!=Counter(map(key,ledger(blob(PLAN,B)))):
            raise ValueError('missing, duplicate or unplanned ledger identity')
    index={}
    if args.index:
        for entry in ledger(blob(args.sha,args.index)):
            if key(entry) in index or key(entry) not in set(map(key,rows)):
                raise ValueError('unexpected or duplicate certificate index key')
            index[key(entry)]=entry['certificate_path']
    inputs={x['case_id']:x for name in ('deterministic','random_conditional')
            for x in json.loads(blob(IMPL,f'{DOC}/inputs/{name}.json'))}
    args.output.mkdir(parents=True,exist_ok=True)
    folders={}
    if not sample:
        root=B.rsplit('/',1)[0]+'/runs/'
        paths=subprocess.check_output(['git','ls-tree','-r','--name-only',args.sha,root],cwd=ROOT,text=True)
        for path in paths.splitlines():
            if path.endswith('/job.json'):
                phase=path[len(root):].split('/')[0]
                if phase=='dev':
                    continue
                job=json.loads(blob(args.sha,path))
                identity=(phase,job['case']['id'],job['arm'] if phase=='pilot' else job['method'])
                if identity in folders or identity not in set(map(key,rows)):
                    raise ValueError('unexpected run '+str(identity))
                folders[identity]=(path.rsplit('/',1)[0],job)
    report=[]
    for row in rows:
        record=dict(zip(('phase','case','arm'),key(row)),status=row['status'],
                    inclusion='PENDING',resolution='PENDING',budget='PENDING')
        report.append(record)
        if row['status'].startswith('NOT_RUN') and not (row.get('certificate_path') or key(row) in index or key(row) in folders):
            continue
        base=f"{DOC}/precontract_v1/examples/{row['case']}"
        try:
            x=json.loads(blob(IMPL,base+'.input.json')) if sample else inputs[row['case']]
            folder,job=folders.get(key(row),(None,None))
            path=folder+'/proof.json.gz' if folder else base+'.composite.json' if sample else row.get('certificate_path') or index[key(row)]
            raw=blob(args.sha,path)
            record.update(path=path,sha256=hashlib.sha256(raw).hexdigest(),input_hash=x['input_hash'])
            cert=json.loads(gzip.decompress(raw) if path.endswith('.gz') else raw,object_pairs_hook=unique)
            if folder:
                def read(name):
                    data=blob(args.sha,folder+'/'+name)
                    return json.loads(gzip.decompress(data) if name.endswith('.gz') else data,object_pairs_hook=unique)
                if job['case']['a_input']!=x or cert['original']!=x:
                    raise ValueError('original input differs from frozen input')
                wrapped=cert
                cert=wrapped['certificate']
                expected=C.restricted_input(x,cert['preprocessing']) if 'preprocessing' in cert else x
                if wrapped['restricted']!=expected:
                    raise ValueError('wrong restricted input')
            verdict,domain,tree=check(row,x,cert)
            record.update(verdict)
            if folder:
                wall=read('wall.json')
                worker=read('worker.json')
                receipt=read('receipt.json')
                record.update(wall=wall,worker=worker,receipt=receipt)
                settings=job['settings']
                # Frozen B runner sets RLIMIT_AS in the worker before exec. This is
                # evidence of an enforced ceiling, not an observed RSS sample.
                runner='tools/midterm_dual_robot_region_b/precontraction/formal.py'
                hard_limit=(receipt['freeze']==job['freeze'] and
                            blob(job['freeze'],runner)==blob('fbbe5dabf9d6325e551a27e3fe655fb23d8a7543',runner) and
                            settings['memory_bytes']<=2**30 and receipt['status']=='COMPLETE')
                measured=dict(total_s=wall['seconds'],preprocess_s=worker.get('preprocessing',0),
                    preprocessing_certificate_s=worker.get('precheck_and_derive',0),
                    search_s=worker.get('search',0),A_check_s=worker['A_check'],
                    B_check_s=worker.get('B_check',0),conversion_s=worker.get('conversion',0),
                    projection_s=worker['projection']+worker['projection_audit'],
                    io_s=worker.get('checkpoint_io',0)+worker['evidence_io'])
                consistent=all(row.get(k) and float(row[k])==v for k,v in measured.items())
                record.update(ledger_matches_measurements=bool(consistent),
                              worker_memory_limit_verified=hard_limit)
                accounted=dict(row)
                if hard_limit:
                    accounted['peak_rss_bytes']=str(settings['memory_bytes'])
                record['budget']=budget(accounted,x,tree,cert.get('preprocessing')) if consistent else 'FAIL'
                if tree and tree['cost']['processed_nodes']>settings['max_boxes']:
                    record['budget']='FAIL'
                if tree:
                    rawtree=read('tree.json.gz')
                    if rawtree['queue']!=tree['queue'] or sorted((n['path'],n['status'],n['box']) for n in rawtree['nodes'])!=sorted((n['id'],n['kind'],n['box']) for n in tree['nodes']):
                        raise ValueError('archived tree differs from certified nodes or queue')
                    for car in ('p','s'):
                        boxes=[n['box'] for n in tree['projections'][car]['rectangles']]
                        def rectangles(items):
                            return {tuple(Q(v) for interval in box for v in interval) for box in items}
                        if rectangles(boxes)!=rectangles(wrapped['regions'][car]['rectangles']):
                            raise ValueError('archived projection differs from certified projection')
                if row['status'].startswith('NOT_RUN'):
                    record['ledger_discrepancy']='artifact present while ledger reports NOT_RUN'
                    record['budget']='UNKNOWN'
                if wall['seconds']>120 or worker.get('search',0)>30 or wall['status']!='COMPLETE':
                    record['budget']='FAIL'
            if row['arm']=='contracted' and row['case'] in ('normal','collinear','normal_b0_zero','collinear_b0_zero'):
                record['figure_data']=dict(original=x['domains'][:4],contracted=domain,
                                           projections={car:[json.loads(v) for v in sorted({json.dumps(n['box']) for n in tree['projections'][car]['rectangles']})] for car in ('p','s')})
        except Exception as exc:
            record.update(inclusion='REJECT',reason=str(exc))
    result=dict(evidence_commit=args.sha,ledger=args.ledger,checker=IMPL,rows=report)
    if not sample:
        sums={arm:sum(r['wall']['seconds'] for r in report if r['phase']=='pilot' and
                      r['arm']==arm and 'wall' in r) for arm in ('original','contracted')}
        result['pilot_wall_seconds']=sums
        if sum('wall' in r for r in report if r['phase']=='pilot')==14:
            decision=json.loads(blob(args.sha,B.rsplit('/',1)[0]+'/runs/pilot/decision.json'))
            if (decision['planned']!=14 or any(abs(sums[k]-decision['seconds'][k])>1e-10 for k in sums)
                or decision['expand']!=(sums['contracted']<sums['original'])):
                raise ValueError('published pilot aggregate differs from reconstructed totals')
    (args.output/'table.json').write_text(json.dumps(result,indent=2)+'\n')
    return any(r['inclusion']=='REJECT' or r.get('mechanism')=='FAIL' or r['budget']=='FAIL' for r in report)


def unique(pairs):
    result={}
    for k,v in pairs:
        if k in result:
            raise ValueError('duplicate certificate field '+k)
        result[k]=v
    return result


if __name__=='__main__':
    sys.exit(main())

"""Before input generation: audit exact seed tokens and literal Python ranges."""
from common import *
import ast,re,subprocess

def main():
    seeds=list(range(291118001,291118041));refs=sorted(set(subprocess.check_output(['git','for-each-ref','--format=%(objectname)'],cwd=ROOT,text=True).split()+[subprocess.check_output(['git','rev-parse','FETCH_HEAD'],cwd=ROOT,text=True).strip()]));blobs={};matches=[];ranges=[];checked=[]
    for sha in refs:
        for line in subprocess.check_output(['git','ls-tree','-rz',sha],cwd=ROOT).split(b'\0'):
            if not line:continue
            meta,p=line.split(b'\t',1);name=p.decode();parts=meta.split()
            if not name.endswith(('.md','.json','.jsonl','.csv','.txt','.log','.py','.sh','.yaml','.yml','.json.gz','.jsonl.gz','.csv.gz')):continue
            if name.startswith(('tools/midterm_noise_scale_a/','docs/research/midterm_noise_scale_a/')):continue
            blobs.setdefault(parts[2].decode(),name)
    pattern=re.compile(rb'(?<![\d.])(?:'+b'|'.join(str(s).encode() for s in seeds)+rb')(?!\d)')
    for oid,p in blobs.items():
        data=subprocess.check_output(['git','cat-file','blob',oid],cwd=ROOT)
        if data.startswith(b'\x1f\x8b'):data=gzip.decompress(data)
        hit=pattern.findall(data)
        if hit:matches.append(dict(path=p,oid=oid,matches=sorted(set(x.decode() for x in hit))))
        if p.endswith('.py'):
            try:tree=ast.parse(data.decode())
            except (SyntaxError,UnicodeError):tree=None
            if tree:
                for node in ast.walk(tree):
                    if isinstance(node,ast.Call) and ((isinstance(node.func,ast.Name) and node.func.id=='range') or (isinstance(node.func,ast.Attribute) and node.func.attr=='arange')):
                        try:r=range(*[ast.literal_eval(a) for a in node.args])
                        except (ValueError,TypeError):continue
                        overlap=[s for s in seeds if s in r]
                        if overlap:ranges.append(dict(path=p,seeds=overlap))
        checked.append(dict(path=p,git_blob=oid,sha256_uncompressed=hashlib.sha256(data).hexdigest(),bytes=len(data)))
    assert not matches and not ranges,(matches,ranges)
    save(DOC/'SEED_AUDIT.json',dict(seeds=seeds,refs=refs,unique_blobs=len(checked),literal_matches=matches,literal_range_overlaps=ranges,formal_inputs_generated=0,formal_optimizer_calls=0,scope='All local committed refs plus freshly fetched main; text and compressed evidence, excluding only this task. Cannot establish unrecorded external executions.',status='NO_REUSE_IN_AUDITED_RECORDS'))
    write_records(DOC/'SEED_AUDIT_FILES.jsonl.gz',checked);print('seed audit blobs',len(checked),'collisions',len(matches)+len(ranges))
if __name__=='__main__':main()

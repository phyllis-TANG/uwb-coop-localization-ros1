"""Verify portable source bytes; extract saved observations without RNG or optimization."""
from common import *
import collections,subprocess,platform

def main():
    manifest=read(OLD/'SHA256SUMS.json');verified={}
    for path,sha in manifest['files'].items():
        actual=hashlib.sha256((ROOT/path).read_bytes()).hexdigest();assert actual==sha,path;verified[path]=sha
    seen=set();selected=[];categories=collections.Counter()
    for path in sorted((OLD/'results').glob('EVIDENCE-*.jsonl.gz')):
        for z in records(path):
            if z['type']!='UNIT':continue
            r=z['value'];uid=r['item']['id'];assert uid not in seen;seen.add(uid)
            for m in SOURCE['methods']:categories[r['results'][m]['P1']['category']]+=1
            u=r['input'];assert digest(u['obs'])==u['input_sha256']
            if u['condition']['id'] in CFG['conditions'] and u['seed'] in CFG['seeds']:
                assert u['condition']['motion']=='static' and u['condition']['kind']=='peer' and u['condition']['bias_m']==.3
                selected.append(dict(id=uid,input=u,initials=initials(u['obs']['anchors'],u['obs']['start']),original={m:{s:r['results'][m][s] for s in ['P0','P1']} for m in CFG['methods']}))
    assert len(seen)==3600 and len(selected)==240
    assert categories=={'ACCEPTED':14335,'NOT_STATIONARY':65},categories
    selected.sort(key=lambda r:r['id']);write_records(DOC/'INPUTS.jsonl.gz',selected)
    save(DOC/'SOURCE_CHECKS.json',dict(source_sha=CFG['source_sha'],readonly_sha=CFG['readonly_sha'],verified_files=verified,source_units=len(seen),source_final_categories=dict(categories),selected_units=len(selected),original_configurations=720,new_planned=2880,observation_generation_calls=0,python=platform.python_version(),numpy=np.__version__,protocol_freeze_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()))
    print('verified',len(verified),'files; selected',len(selected),'saved units')
if __name__=='__main__':main()

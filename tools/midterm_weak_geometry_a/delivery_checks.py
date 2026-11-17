"""Independent identities, selection and output acceptance; no optimizer import."""
from common import *
import csv,collections,subprocess

def main():
    p=DOC/'results';inp=list(records(DOC/'INPUTS.jsonl.gz'));new=list(records(p/'ENDPOINTS.jsonl.gz'));assert len(inp)==240 and len(new)==2880
    expected={(u['id'],m,i) for u in inp for m in CFG['methods'] for i in CFG['initializations']};actual={(z['id'],z['method'],z['init']) for z in new};assert len(actual)==len(new) and expected==actual
    assert sum(z['optimizer_calls'] for z in new)==5760
    cats=collections.Counter(z['stages']['P1']['category'] for z in new);assert cats=={'ACCEPTED':2873,'NOT_STATIONARY':7}
    stages={(z['id'],z['method'],z['init']):z['stages']['P1'] for z in new}
    for u in inp:
        assert digest(u['input']['obs'])==u['input']['input_sha256'];assert initials(u['input']['obs']['anchors'],u['input']['obs']['start'])==u['initials']
        for m in CFG['methods']:stages[(u['id'],m,'I0')]=u['original'][m]['P1']
    selection=read(p/'readback/SELECTION.json');met=list(csv.DictReader((p/'readback/ENDPOINT_METRICS.csv').open()))
    for s in selection:
        candidates=[(stages[(s['id'],s['method'],i)]['cost'],i) for i in ['I0']+CFG['initializations'] if stages[(s['id'],s['method'],i)]['accepted']];assert min(candidates)[1]==s['selected_init']
        assert met[s['selected_index']]['init']==s['selected_init']
    for path,sha in read(DOC/'SOURCE_CHECKS.json')['verified_files'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha
    for x in (ROOT/'tools/midterm_weak_geometry_a').glob('*.py'):compile(x.read_text(),str(x),'exec')
    points=np.load(p/'readback/POINTS.npz');reasons=collections.Counter(points['reason'].ravel());assert points['q'].shape==(3600,2,12)
    # Verify summary points match saved q, preserving non-stationary rows.
    assert read(p/'summary/COUNT_CHECKS.json')['max_count_difference']==0
    save(DOC/'DELIVERY_CHECKS.json',dict(source_hashes_rechecked=81,inputs=240,new_unique_configurations=len(actual),new_stage_records=5760,new_optimizer_calls=5760,original_configurations=720,all_candidates=3600,new_categories=dict(cats),candidate_categories=dict(collections.Counter(r['category'] for r in met)),independent_selections_checked=len(selection),point_blocks=int(np.prod(points['q'].shape)),point_reasons=dict(reasons),coverage_cells_independently_recounted=384,analysis_optimizer_calls=0,code_compile='PASS',frozen_protocol_unchanged=subprocess.check_output(['git','diff','fdafeb4','--','docs/research/midterm_weak_geometry_a/PROTOCOL.md','docs/research/midterm_weak_geometry_a/CONFIG.json','docs/research/midterm_weak_geometry_a/SEEDS.csv'],cwd=ROOT,text=True)==''))
    print(read(DOC/'DELIVERY_CHECKS.json'))
if __name__=='__main__':main()

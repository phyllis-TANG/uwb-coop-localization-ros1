"""Scope-limited immutable Git record audit, no observation generation."""
import argparse,sys
from pathlib import Path
from io_utils import ROOT,DOC,read,save
sys.path.insert(0,str(ROOT/'tools/midterm_simulation_validation'))
import audit_seeds
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--pr-heads',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    c=read(DOC/'CONFIG.json');audit_seeds.load_config=lambda:c
    result=audit_seeds.audit(a.pr_heads);result['scope']=result['scope'].replace('all 101 GitHub','all listed GitHub');save(a.out,result)
    print({k:result[k] for k in ['status','unique_blobs','uncompressed_bytes','literal_matches','literal_range_overlaps','missing_commits','missing_blobs']})
    assert result['status']=='REGISTERED_UNEXPOSED_IN_AUDITED_RECORDS'

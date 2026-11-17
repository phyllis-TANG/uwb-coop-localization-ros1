"""Copy compact verifiable deliverables; full spectra/log intermediates stay outside Git."""
import argparse,gzip,hashlib,json,shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--artifacts',type=Path,required=True);p.add_argument('--destination',type=Path,required=True);a=p.parse_args();out=a.destination/'results';out.mkdir(exist_ok=False)
for source,names in [(a.artifacts/'run001',['RECOVERY.json','CHECKS.json','PROVENANCE.json','REFERENCE_INFORMATION.json','MARGINALS.npz','RUNS.csv','INFORMATION.csv']),(a.artifacts/'summary001',['COVERAGE.csv','BIAS_COVERAGE.csv','EMPIRICAL_MOMENTS.csv','ASSOCIATIONS.csv','NOT_STATIONARY.csv','PRIOR_COMPARISONS.csv','CASES.json','SUMMARY_CHECKS.json','RANK_SUMMARY.json','OVERVIEW.csv'])]:
 for name in names:
  data=(source/name).read_bytes()
  if name in ['RUNS.csv','INFORMATION.csv','COVERAGE.csv','BIAS_COVERAGE.csv','EMPIRICAL_MOMENTS.csv','ASSOCIATIONS.csv']:(out/(name+'.gz')).write_bytes(gzip.compress(data,mtime=0))
  else:(out/name).write_bytes(data)
for name in ['formula-checks.json','summary-checks.json','interface-checks.json']:shutil.copy2(a.artifacts/name,out/name)
shutil.copytree(a.artifacts/'summary001/figures002',a.destination/'figures')
# Reproducibility of external spectra: gzip header timestamps differ, hash uncompressed content too.
s=a.artifacts/'run001/SPECTRA.jsonl.gz';(out/'EXTERNAL_EVIDENCE.json').write_text(json.dumps(dict(spectra_compressed_sha256=hashlib.sha256(s.read_bytes()).hexdigest(),spectra_uncompressed_sha256=hashlib.sha256(gzip.decompress(s.read_bytes())).hexdigest(),regenerate='analyze.py --out NEW_EXTERNAL_DIRECTORY',reason='Full per-run singular spectra retained outside Git; per-run min/max/rank/condition and reference spectra delivered'),indent=2)+'\n')

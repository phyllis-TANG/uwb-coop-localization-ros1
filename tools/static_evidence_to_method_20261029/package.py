#!/usr/bin/env python3
"""Package existing statistics, preserving reuse vs supplementary provenance."""
import argparse,csv,json,hashlib
from pathlib import Path
from analyze import csvout,dump,sha,ROOT,SESSION

def package(stats,out):
 out.mkdir(exist_ok=False)
 with (stats/'COMPACT_RESULTS.csv').open() as f:rows=list(csv.DictReader(f))
 receipt=json.loads((stats/'RUN_MANIFEST.json').read_text())
 # These are original published population standard deviations, not new decoding.
 for window,sd in [('pre',.035),('wall_action',.281),('recovery1',.138),('peer_action',.033),('recovery2',.028)]:
  old=next(r for r in rows if (r['bag'],r['window'],r['car'],r['link'],r['origin'])==('T02',window,'car2','node_10','reused_numeric'))
  r={k:old[k] for k in ['bag','file','bag_sha256','window','start_s','end_s','clock','car','link','origin','source_path','source_version','result_path']}
  r.update(metric_kind='population_std_original_report_not_median_uncertainty',std_m_original_report=sd)
  rows.append(r)
 csvout(out/'COMPACT_RESULTS.csv',rows)
 with (stats/'CONTRASTS.csv').open() as f:contrasts=list(csv.DictReader(f))
 for r in contrasts:r['source_version']=sha(out/'COMPACT_RESULTS.csv')
 csvout(out/'CONTRASTS.csv',contrasts)
 for name in ['OLD_STATIC_EVIDENCE.csv','CHECKS.json']:(out/name).write_bytes((stats/name).read_bytes())
 receipt['supplement_run_receipt_path']=str(stats/'RUN_MANIFEST.json');receipt['supplement_run_receipt_sha256']=sha(stats/'RUN_MANIFEST.json')
 receipt['raw_statistics_outputs']=receipt.pop('outputs');receipt['external_cache_root']=str(stats)
 receipt['rows']=len(rows);receipt['reused_numeric_rows']=sum(r['origin']=='reused_numeric' for r in rows)
 receipt['packaging_code_sha256']=sha(Path(__file__))
 receipt['outputs']={p.name:sha(p) for p in out.iterdir() if p.is_file()}
 dump(out/'RUN_MANIFEST.json',receipt)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--stats',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();package(a.stats,a.output)

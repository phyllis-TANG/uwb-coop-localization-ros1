"""Reproduce the shared panel without requiring A's external historical RAW file."""
import argparse,json,subprocess
from pathlib import Path
from audit import ROOT,A_SHA,B_SHA,module,dump,panel,sha

def main():
    p=argparse.ArgumentParser();p.add_argument('--b-root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--large',type=Path,required=True);z=p.parse_args()
    for root,commit,paths in [(ROOT,A_SHA,['tools/midterm_simulation_s1b/analyze.py','docs/research/midterm_simulation_s1b/CONFIG.json']), (z.b_root,B_SHA,['tools/midterm_simulation_s2/prototype.py','tools/midterm_simulation_phase1/identifiability.py','docs/research/midterm_simulation_s2/CONFIG.json'])]:
        for path in paths:assert (root/path).read_bytes()==subprocess.check_output(['git','show',commit+':'+path],cwd=root),path
    a=module('panel_A',ROOT/'tools/midterm_simulation_s1b/analyze.py');b=module('panel_B',z.b_root/'tools/midterm_simulation_s2/prototype.py')
    cfg=json.loads((z.b_root/'docs/research/midterm_simulation_s2/CONFIG.json').read_text())
    z.out.mkdir(parents=True,exist_ok=False);z.large.mkdir(parents=True,exist_ok=False)
    dump(z.out/'SUMMARY.json',panel(a,b,cfg,z.out,z.large))
    expected=ROOT/'docs/research/midterm_numerical_audit/results/PANEL_INPUTS.jsonl'
    assert sha(z.out/'PANEL_INPUTS.jsonl')==sha(expected)
    print('PASS: identical panel input file SHA256',sha(expected))
if __name__=='__main__':main()

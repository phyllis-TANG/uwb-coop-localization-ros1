"""A-side acceptance: verify frozen content then run development-only fixtures."""
import argparse
import json
from pathlib import Path
from checks import run_checks
from core import load_config
from pipeline import exclusive,git,plan,provenance,verify_freeze,versions
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);args=p.parse_args()
    manifest=verify_freeze();c=load_config()
    provenance(c,'formal',git('rev-parse','HEAD'))  # preflight only, no run or generation
    # Enumerate seed identities only. No observation generation or formal solve.
    identities=plan(c,'formal')
    assert len(identities)==c['expected']['formal_paired_units']
    result=run_checks(args.out)
    receipt=dict(frozen_commit=git('rev-parse','HEAD'),manifest_verified=True,dependencies=versions(),planned_conditions=c['expected']['conditions'],planned_formal_methods=len(identities)*len(c['methods']),formal_observations_generated=0,formal_runs=0,checks_passed=result['passed'])
    exclusive(args.out/'ACCEPTANCE.json',receipt);print(json.dumps(receipt,ensure_ascii=False,indent=2))

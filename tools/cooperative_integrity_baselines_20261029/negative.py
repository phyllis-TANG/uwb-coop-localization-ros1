#!/usr/bin/env python3
"""Private in-memory semantic corruptions, original output bytes never rewritten."""
import argparse
import copy
import gzip
import json
from pathlib import Path
import numpy as np
from independent import verify,verify_input_prefix,noise_keys
from common import sha,write_json


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    source=a.run/'monitor.jsonl.gz';before=sha(source)
    with gzip.open(source,'rt') as f:rows=[json.loads(line) for line in f]
    config=json.loads((a.run/'config.json').read_text());results=[]
    def attempt(name,mutation):
        private=copy.deepcopy(rows[:3]);mutation(private)
        try:verify(private,config)
        except (AssertionError,ValueError,TypeError,np.linalg.LinAlgError):results.append(dict(name=name,status='REJECTED'));return
        raise AssertionError('Semantic corruption accepted: '+name)
    attempt('SS_SCORE',lambda r:r[2]['monitor']['ss']['peer'][0].__setitem__('statistic',100.))
    attempt('CROSS_CORRELATION_DROPPED',lambda r:r[2]['monitor']['ss']['peer'][0].__setitem__('cross_covariance',[[0.,0.],[0.,0.]]))
    attempt('B1_SCORE',lambda r:r[0]['monitor']['b1']['engineering_0.2m']['car1'].__setitem__('statistic',100.))
    attempt('STARTUP_AVAILABLE',lambda r:r[0]['monitor']['declarations']['B0'][0].__setitem__('available',True))
    attempt('FAILURE_ACCEPTED',lambda r:r[2].__setitem__('status','predict_only_solver_failed'))
    attempt('EXCLUDED_PRIOR_NOISE_REINTRODUCED',lambda r:r[2]['linear_evidence']['car1_absolute']['prior_b'][0].__setitem__(noise_keys().index('wall|car1|1|node_10'),1.))
    attempt('INITIAL_GUESS_HISTORY_CHANGED',lambda r:r[2]['linear_evidence']['peer']['snapshot']['states'][0].__setitem__(0,99.))
    # Input-prefix reader receives regenerated frozen data only; it imports no online code.
    from inputs import make
    _,events,_,_=make('nominal')
    private=copy.deepcopy(rows[:1]);dep=private[0]['peer_dependencies'][0]
    dep['identity']['receive_epoch_ns']=private[0]['availability_cutoff_epoch_ns']+1
    try:verify_input_prefix(private,events,config)
    except AssertionError:results.append(dict(name='FUTURE_RECEIVE_DEPENDENCY',status='REJECTED'))
    else:raise AssertionError('Future input accepted')
    assert sha(source)==before
    write_json(a.output,dict(status='PASS',negative_count=len(results),results=results,original_sha256_unchanged=before,
                            intervention_storage='private memory only; no raw input modification'))
    print(len(results),'semantic corruptions rejected')
if __name__=='__main__':main()

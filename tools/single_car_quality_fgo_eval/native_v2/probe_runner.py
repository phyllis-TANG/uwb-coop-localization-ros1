"""Control execution only: original A Pipeline plus read-only buffer observer.

This is an estimator launcher, NOT an independent reader. It does not implement
or change a policy/graph. The independent control reader imports no A module.
"""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
from .common import ROOT,begin,finish,lines,require,sha,write,write_lines


def plain(x):
    if isinstance(x,np.ndarray):return x.tolist()
    if isinstance(x,np.generic):return x.item()
    if isinstance(x,dict):return {k:plain(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [plain(v) for v in x]
    return x


def cache_record(front):
    out={k:plain(getattr(front,k)) for k in ('odom','ranges','latest_header','first','first_local','previous_pose','previous_local') if hasattr(front,k)}
    if hasattr(front,'angular'):out['angular_rows']=plain(front.angular.rows);out['angular_last_source']=front.angular.last_source
    out['graph_states']=plain(front.graph.states);out['graph_times']=plain(front.graph.times);out['graph_local']=plain(front.graph.local)
    out['graph_observations']=plain(front.graph.observations);out['prior']=dict(point=front.graph.prior.point.tolist(),matrix=front.graph.prior.matrix.tolist(),offset=front.graph.prior.offset.tolist())
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--events',type=Path,required=True);p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();v=begin(a.output,'B_control_original_A_pipeline_with_read_only_cache_observer')
    try:
        sys.path.insert(0,str(ROOT/'tools/single_car_quality_fgo'))
        from qfrontend import Pipeline
        from qio import sources
        config=json.loads(a.config.read_text());require(config['timing']['paced'] is False,'accelerated verification controls only, never performance timing');events=lines(a.events);lock=sources();graphs=[];ledger=[];pub=[];caches=[];holder={}
        def graph_sink(row):
            graphs.append(row);pipeline=holder['pipeline'];front=pipeline.main if row['role']=='main' else pipeline.shadows[row['role']]
            caches.append(dict(role=row['role'],state_epoch_ns=row['state_epoch_ns'],record_id=row['record_id'],observer_point='after graph result, before frontend prune',cache=cache_record(front)))
        pipeline=Pipeline(config,events[0]['receive_epoch_ns'],graph_sink=graph_sink,ledger_sink=ledger.append,publication_sink=pub.append);holder['pipeline']=pipeline
        for event in events:pipeline.ingest(event)
        pipeline.finish();require(sources()==lock,'A source unchanged')
        for name,values in [('graphs',graphs),('ledger',ledger),('publications',pub),('caches',caches)]:write_lines(a.output/(name+'.jsonl.gz'),plain(values))
        write(a.output/'summary.json',dict(status='DONE',source_sha256=lock,group=config['group'],original_A_pipeline_used=True,independent_reader=False,actual_available_time_not_measured=True,publications=len(pub),marginalizations={k:f.graph.marginalizations for k,f in dict(main=pipeline.main,**pipeline.shadows).items()},input_sha256=sha(a.events),config_sha256=sha(a.config)))
        v['estimator_runs']=1;v['inputs']=[dict(path=str(a.events),sha256=sha(a.events)),dict(path=str(a.config),sha256=sha(a.config))];finish(a.output,v);return 0
    except Exception as e:finish(a.output,v,e);raise


if __name__=='__main__':raise SystemExit(main())

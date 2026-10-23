#!/usr/bin/env python3
"""Adapter-specific identity, clock, causal dependency and isolation tests."""
import copy
import json
import math
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
import tempfile
from unittest.mock import patch
import numpy as np
from single_car_fixed_lag import FixedLagReplay,Objective,initial_prior
from single_car_integrity import IntegrityReplay
from two_car_independent_integrity import (ROOT,CARS,TAGS,PEERS,ANCHORS,adapt_message,
    bag_events,make_config,odom_bracket)

PARENT=json.loads((ROOT/'docs/field_tests/two_car_updated_comparison_20261022/protocol.json').read_text())
CAL=json.loads((ROOT/'docs/field_tests/two_car_updated_comparison_20261022/results/calibration.json').read_text())
TEMPLATE=json.loads((ROOT/'docs/field_tests/integrity_feasibility_v1_1_20261022/estimator_config.json').read_text())
ORIGIN=1700000000000000000


def config(car):return make_config(TEMPLATE,PARENT,CAL,PARENT['cases'][0],car)


def message(car,kind,header_ns,values=None):
    header=NS(stamp=NS(sec=header_ns//10**9,nanosec=header_ns%10**9),
              frame_id=car+('/odom_combined' if kind=='odom' else '/uwb_linktrack'))
    if kind=='uwb':
        return NS(header=header,tag_id=TAGS[car],ranges=[NS(anchor_id=k,range=v) for k,v in values.items()])
    return NS(header=header,child_frame_id='base_footprint',
        pose=NS(pose=NS(position=NS(x=0.,y=0.),orientation=NS(x=0.,y=0.,z=0.,w=1.))),
        twist=NS(twist=NS(linear=NS(x=0.,y=0.),angular=NS(z=0.))))


def fixture(car,end=26.,fault=0.,peer=1.):
    conf=config(car);model=conf['model'];xyz=model['start_antenna_xyz_m']
    base={k:float(np.linalg.norm(np.asarray(xyz)-ref))+model['range_bias_m'][k]
          for k,ref in model['anchors_xyz_m'].items()}
    out=[]
    for i in range(int(end*20)+1):
        t=i/20
        vals=dict(base);vals['node_10']+=.1*math.sin(t*.3)+fault
        vals[PEERS[car]]=peer
        for kind,offset in [('odom',0),('uwb',.001)]:
            ns=ORIGIN+round((t+offset)*1e9)
            msg=message(car,kind,ns+7*10**9,vals)
            out.append(('/'+car+('/odom' if kind=='odom' else '/uwb/ranges'),msg,ns))
    return out


def replay(raw,car,monitor=True):
    conf=config(car);rows=[]
    if monitor:
        obj=IntegrityReplay(conf,rows.append,dict(M1=1.,M2=.062191200771030145))
    else:
        obj=FixedLagReplay(conf['model'],conf['replay'],rows.append,lag_s=20.,max_nfev=50)
    for topic,msg,ns in raw:
        event,_=adapt_message(topic,msg,ns,ORIGIN,car);obj.ingest(event)
    obj.finish()
    return obj,rows


def stable(rows):
    return [(r['state_time_s'],r['pose'],r['status'],r.get('range_medians_m'),r['M1'],r['M2'],
        [(k,h['pose'],h.get('prior_matrix'),h.get('prior_offset'),h['prior_lineage_sha256'])
         for k,h in r['exclusion_hypotheses'].items()]) for r in rows]


class AdapterTests(unittest.TestCase):
    def test_topic_node_frame_identity_and_cross_car_isolation(self):
        for car in CARS:
            other=next(c for c in CARS if c!=car)
            for kind in ['odom','uwb']:
                topic='/'+car+('/odom' if kind=='odom' else '/uwb/ranges')
                msg=message(car,kind,ORIGIN,dict(node_10=3.,**{PEERS[car]:1.}))
                event,meta=adapt_message(topic,msg,ORIGIN,ORIGIN,car)
                self.assertEqual(event.kind,kind);self.assertEqual(meta['car'],car)
                self.assertEqual(adapt_message(topic,msg,ORIGIN,ORIGIN,other)[0].kind,'clock')
                msg.header.frame_id='wrong'
                with self.assertRaises(ValueError):adapt_message(topic,msg,ORIGIN,ORIGIN,car)
            msg=message(car,'uwb',ORIGIN,{'node_10':3.});msg.tag_id=TAGS[other]
            with self.assertRaises(ValueError):adapt_message('/'+car+'/uwb/ranges',msg,ORIGIN,ORIGIN,car)

    def test_reader_origin_is_first_all_topic_receipt_and_headers_are_lossless(self):
        rows=[(NS(topic='/unrelated',msgtype='x'),ORIGIN,None)]
        for car in CARS:
            topic='/'+car+'/odom';rows.append((NS(topic=topic,msgtype='x'),ORIGIN+1000000,message(car,'odom',ORIGIN+123456789)))
        class Reader:
            def __init__(self,paths):pass
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def messages(self):return iter(rows)
            def deserialize(self,raw,typ):return raw
        for car in CARS:
            diag={};trace=[]
            with patch('rosbags.highlevel.AnyReader',Reader):events=list(bag_events(Path('unused'),car,diag,trace.append))
            self.assertEqual(diag['origin_bag_receipt_ns'],ORIGIN)
            self.assertEqual(trace[0]['original_header_ns'],ORIGIN+123456789)
            event=next(e for e in events if e.kind=='odom')
            self.assertEqual(event.header_s,.001);self.assertEqual(event.received_s,.001)

    def test_future_mutation_and_truncation_preserve_past_publications(self):
        raw=fixture('car1',28.);_,full=replay(raw,'car1')
        changed=copy.deepcopy(raw)
        for topic,msg,ns in changed:
            if ns>ORIGIN+25*10**9 and topic.endswith('ranges'):
                for v in msg.ranges:
                    if v.anchor_id=='node_10':v.range+=.8
        _,future=replay(changed,'car1')
        truncated=[x for x in raw if x[2]<=ORIGIN+25*10**9]
        _,short=replay(truncated,'car1')
        past=lambda rows:[r for r in rows if r['availability_cutoff_s']<=25.]
        self.assertEqual(stable(past(full)),stable(past(future)))
        self.assertEqual(stable(past(full)),stable(short))
        self.assertNotEqual(full[-1]['pose'],future[-1]['pose'])

    def test_interpolation_never_uses_unarrived_right_endpoint(self):
        trace=[dict(kind='odom',association_time_s=t,bag_receipt_s=t,bag_receipt_ns=ORIGIN+int(t*1e9),
                    original_header_ns=ORIGIN+int((t+7)*1e9)) for t in [.5,1.5]]
        self.assertIsNone(odom_bracket(trace,1.,1.2))
        pair=odom_bracket(trace,1.,2.)
        self.assertEqual([r['association_time_s'] for r in pair],[.5,1.5])

    def test_each_car_bias_used_once_and_no_endpoint_fields(self):
        for car in CARS:
            model=config(car)['model'];point=initial_prior(model)
            raw={k:float(np.linalg.norm(np.asarray(model['start_antenna_xyz_m'])-xyz))+model['range_bias_m'][k]
                 for k,xyz in model['anchors_xyz_m'].items()}
            obj=Objective([1.],[[0,0,0]],[raw],model,point)
            np.testing.assert_allclose(obj.fun(point.point),0.,atol=1e-12)
            self.assertEqual(model['range_bias_m'],CAL['applied_biases_m'][car])
            self.assertNotIn('evaluation_only',config(car));self.assertNotIn('end_antenna_xyz_m',model)
        self.assertNotEqual(config('car1')['model']['range_bias_m'],config('car2')['model']['range_bias_m'])

    def test_peer_changes_cannot_change_independent_outputs(self):
        for car in CARS:
            raw=fixture(car,6.,peer=1.);altered=fixture(car,6.,peer=1000.)
            _,a=replay(raw,car);_,b=replay(altered,car)
            self.assertEqual(stable(a),stable(b))

    def test_exclusion_history_remains_independent_after_adapter_and_marginalization(self):
        a,ra=replay(fixture('car2',26.),'car2')
        b,rb=replay(fixture('car2',26.,fault=.6),'car2')
        ga,gb=a.hypotheses['node_10'],b.hypotheses['node_10']
        self.assertGreater(ga.marginalizations,0)
        for key in ['point','matrix','offset']:
            np.testing.assert_array_equal(getattr(ga.prior,key),getattr(gb.prior,key))
        self.assertEqual(a.lineage['node_10'],b.lineage['node_10'])
        self.assertNotEqual(ra[-1]['pose'],rb[-1]['pose'])

    def test_monitor_off_leaves_full_localization_identical_for_both_cars(self):
        for car in CARS:
            raw=fixture(car,26.)
            _,a=replay(raw,car);_,b=replay(raw,car,monitor=False)
            for keys in [('pose','status','range_medians_m','local_odom','prior_matrix','prior_offset')]:
                self.assertEqual([[r.get(k) for k in keys] for r in a],[[r.get(k) for k in keys] for r in b])

    def test_duplicate_or_nonpositive_ranges_and_repeated_receipts_are_explicit(self):
        msg=message('car1','uwb',ORIGIN,dict(node_10=3.,node_2=-1.))
        msg.ranges.append(NS(anchor_id='node_10',range=4.))
        event,meta=adapt_message('/car1/uwb/ranges',msg,ORIGIN,ORIGIN,'car1')
        self.assertNotIn('node_10',event.value);self.assertEqual(meta['duplicate_groups'],1)
        raw=fixture('car1',1.)
        with self.assertRaisesRegex(ValueError,'Nonincreasing'):replay([raw[0],raw[0]],'car1')

    def test_resume_refuses_unfinished_or_changed_output_without_starting_worker(self):
        from run_two_car_independent_integrity import run,write,hashes,sha,verify_record
        with tempfile.TemporaryDirectory(dir=ROOT/'.bridge_work') as name:
            out=Path(name)
            write(out/'source_lock.json',dict(repository_files={},experiment_files={}))
            write(out/'protocol.json',dict(budgets=dict(total_formal_wall_s=1800.)))
            records=[dict(id=str(i),status='planned') for i in range(6)]
            write(out/'run_inventory.json',records)
            with patch('run_two_car_independent_integrity.subprocess.run') as start:
                with self.assertRaisesRegex(ValueError,'Refusing'):run(out,True)
                start.assert_not_called()
                records[0]['status']='failed';write(out/'run_inventory.json',records)
                with self.assertRaisesRegex(ValueError,'Refusing'):run(out,False)
                start.assert_not_called()
            target=out/'runs'/'0'/'output';target.mkdir(parents=True)
            (target/'sample.json').write_text('{}')
            r=dict(id='0',status='completed',output_hashes=hashes(target),source_lock_sha256=sha(out/'source_lock.json'))
            verify_record(out,r)
            (target/'sample.json').write_text('{"changed":true}')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):verify_record(out,r)

    def test_alarm_intervals_use_state_axis_and_clip_actual_eof(self):
        from report_two_car_independent_integrity import spans,sumspan
        rows=[dict(state_time_s=float(t),alarm=t in [3,4,6]) for t in range(2,7)]
        events=spans(rows,6.25,lambda r:r['alarm'])
        self.assertEqual([(r['start_s'],r['end_s']) for r in events],[(3.,5.),(6.,6.25)])
        self.assertEqual(sumspan(events),2.25)


if __name__=='__main__':unittest.main()

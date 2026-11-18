import copy
import gzip
import json
import unittest
from collections import Counter

from trajectory import ROOT, replay, display, score
from verify import audit, rebuild, VERSIONS


class Readback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d=ROOT/'docs/research/ground_b_round1/runtime'
        cls.cfg=json.loads((d/'geometry.json').read_text())
        frames=[]
        for line in gzip.decompress((d/'events.jsonl.gz').read_bytes()).splitlines():
            e=json.loads(line)
            t,part=divmod(e['header_epoch_ns']-cls.cfg['epoch_ns'],10**9)
            if part:
                continue
            if e['vehicle_id']=='car1':
                if e['kind']=='odom' and t in (6,7,8):
                    continue
                if e['kind']=='uwb':
                    if t in (1,2,9):
                        e['value']['node_0']+=100
                    if t==3:
                        continue
                    if t in (4,5):
                        e['receive_epoch_ns']=e['header_epoch_ns']+10**9+(t==4)
            frames.append(e)
        raw=gzip.compress(b'\n'.join(json.dumps(e).encode() for e in sorted(frames,key=lambda e:e['receive_epoch_ns'])))
        ep=replay(raw,cls.cfg)
        # Simulate a slow worker; reconstruct FIFO after changing its service time.
        ep[10]['service']=3
        finish=0
        for e in ep:
            arrival=e['all_arrived']
            e['start']=max(finish,arrival if arrival is not None else e['t']+1)
            finish=e['start']+e['service']
            e['finish']=e['ready']=finish
        ticks=display(ep)
        truth=[[[0,0],[0,0]]]*1280
        summaries,events=score(ticks,truth)
        meta=dict(actions=dict(Counter(e['action'] for e in ep)),epochs=63,vehicle_ticks=2560,summary=summaries)
        cls.args=ep,ticks,events,meta,truth,[cls.cfg['models'][c]['start_antenna_xyz_m'][:2] for c in ('car1','car2')]

    def test_valid_sequence(self):
        ep,ticks,*_=self.args
        self.assertEqual([e['action'] for e in ep[:9]],['REJECT','REJECT','MISSING_RANGE','MISSING_RANGE','ACCEPT']+['MISSING_ODOM_OR_SURVEY_REFERENCE']*3+['REJECT'])
        self.assertEqual(ep[4]['all_arrived'],6)
        self.assertIsNone(ticks[2*241]['state_time'])
        audit(*self.args)

    def test_deleted(self):
        ep,ticks,_,meta,*tail=self.args
        with self.assertRaisesRegex(ValueError,'TTA'):
            audit(ep,ticks,[],meta,*tail)

    def test_duplicate(self):
        ep,ticks,events,meta,*tail=self.args
        with self.assertRaisesRegex(ValueError,'TTA'):
            audit(ep,ticks,events+[events[0]],meta,*tail)

    def test_alarm_time(self):
        ep,ticks,events,meta,*tail=self.args
        with self.assertRaisesRegex(ValueError,'TTA'):
            audit(ep,ticks,[dict(events[0],alarm=30)]+events[1:],meta,*tail)

    def test_exposed_duration(self):
        ep,ticks,events,meta,*tail=self.args
        meta=copy.deepcopy(meta)
        meta['summary'][0]['exceed_available_s']=80.
        with self.assertRaisesRegex(ValueError,'summary'):
            audit(ep,ticks,events,meta,*tail)

    def test_available_exposure_and_recovery(self):
        def row(x,label):
            return dict(xy=None if x is None else [x,0],status={v:label for v in VERSIONS})
        rows=[row(0,'AVAILABLE'),row(.11,'AVAILABLE'),row(None,'NO_DECISION'),
              row(.12,'ALARM'),row(.10,'AVAILABLE'),row(.11,'AVAILABLE'),row(.09,'AVAILABLE')]
        summary,events,intervals=rebuild(1,'history',rows,[[0,0]]*len(rows))
        self.assertEqual(summary['exceed_available_s'],.10)
        self.assertEqual(intervals,[(1,4,3),(5,6,None)])
        self.assertEqual([e['outcome'] for e in events],['timely_alarm']*3+['recovered_before_or_at_deadline']*3)

if __name__=='__main__':
    unittest.main()

"""Field adapter contracts use fixtures, without replacing raw bag timestamps."""
import copy
import json
import unittest
import numpy as np
from frontend import execute,JointReplay
from configuration import default_config
from test_contract import strip_times
from pinned import f0_front,f0_sim
from simulate import make_case


class FieldContracts(unittest.TestCase):
    def test_physical_order_receive_reversal_no_reordering_or_future(self):
        c,events,_,_=make_case(7,'nominal');events=[e for e in events if e['receive_epoch_ns']<=f0_sim.EPOCH_NS+4*10**9]
        changed=copy.deepcopy(events)
        # Place one other event in physical order with an earlier source receipt.
        at=100;e=copy.deepcopy(changed[at]);e.update(kind='other',vehicle_id=None,header_epoch_ns=None,value=None)
        e['receive_epoch_ns']=changed[at-1]['receive_epoch_ns']-1000;changed.insert(at,e)
        maximum=None
        for i,e in enumerate(changed):
            e['record_index']=i;maximum=e['receive_epoch_ns'] if maximum is None else max(maximum,e['receive_epoch_ns']);e['availability_epoch_ns']=maximum
        rows=[];r=execute(changed,c,'M3',rows.append)
        self.assertTrue(rows);self.assertEqual(r.last_index,len(changed)-1)
        for row in rows:
            for edge in (row.get('angular_intervals') or {}).values():
                for s in edge['segments']:
                    self.assertLessEqual(s['dependency']['availability_epoch_ns'],row['availability_cutoff_epoch_ns'])
                    self.assertLessEqual(s['dependency']['record_index'],row['availability_prefix_max_record_index'])

    def test_false_availability_and_undeclared_clock_blocked(self):
        c,e,_,_=make_case(7,'nominal');e[0]['availability_epoch_ns']=e[0]['receive_epoch_ns']+1
        with self.assertRaisesRegex(ValueError,'availability'):execute(e,c,'M0',lambda x:None)
        c['clock_policy']['car1']['imu']['kind']='identity_unverified'
        with self.assertRaises(ValueError):execute(e,c,'M3',lambda x:None)

    def test_field_cannot_default_to_synthetic_axis_clock(self):
        c,events,_,_=make_case(7,'nominal');c['scope']='field'
        with self.assertRaises(ValueError):execute(events,c,'M3',lambda x:None)


if __name__=='__main__':unittest.main(verbosity=2)

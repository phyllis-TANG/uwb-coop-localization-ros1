import unittest
from decisions import primary_names
from evaluate import evaluate


class ReadoutContracts(unittest.TestCase):
    def test_alarm_preceding_error_crossing_has_no_fictitious_delay(self):
        config={'models':{car:{'base_to_antenna_body_xy_m':[0.,0.],'antenna_height_m':.2} for car in ('car1','car2')}}
        rows=[];truth=[]
        for t in range(1,5):
            d=dict(computable=True,alarm=t>=2,available=t<2,reason='FIXTURE')
            m=dict(declarations={name:[d.copy(),d.copy()] for name in primary_names()},
                   subset_results={'peer':{'pose':[0.,0.,0.,1.,0.,0.]}},ss={},
                   b0={'engineering_q':0.,'state':'accepted'},graph_wall_s=0.,covariance_wall_s=0.,four_anchor_and_declaration_wall_s=0.)
            rows.append(dict(state_epoch_ns=t,state_time_s=float(t),availability_cutoff_epoch_ns=t+1,
                pose=[0.,0.,0.,1.,0.,0.],accepted_graph=True,status='graph',monitor=m,
                total_monitored_emit_wall_s=.2,monitor_available_time_virtual_s=t+.2))
            shift=1. if t>=3 else 0.
            truth.append(dict(state_epoch_ns=t,cars={car:dict(pose=[ci+shift,0.,0.],antenna_xyz_m=[ci+shift,0.,.2]) for ci,car in enumerate(('car1','car2'))}))
        result=evaluate('nominal',rows,truth,config)
        selected=next(r for r in result['episodes'] if r['profile']=='B0' and r['car']=='car2' and r['AL_m']==.1)
        self.assertEqual(selected['start_s'],3.)
        self.assertEqual(selected['first_alarm_s'],2.)
        self.assertEqual(selected['alarm_lead_state_s'],1.)
        self.assertEqual(selected['alarm_delay_virtual_s'],0.)
        self.assertEqual(selected['hmi_s'],0)

if __name__=='__main__':unittest.main()

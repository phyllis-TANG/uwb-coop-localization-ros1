import copy
import json
import unittest
from pathlib import Path
import checker as C

K=C.K
D=Path(__file__).resolve().parents[3]/'docs/research'
EX=D/'midterm_dual_robot_contract_a/height_v1'


def fixture():
    return K.seal(dict(schema_version=C.VERSION,source_commit=C.BASE,case_id='vertical-contact',
        frame='moon_map_z_up',units='m',source_times={'p':'5','s':'0'},heights={'p':'1','s':'1'},
        anchors={f'a{i}':['0']*3 for i in range(4)},measurement_ids=K.IDS,
        observations=[['0','0']]+[['1','1'] for _ in range(7)]+[['0','0']],
        variance=['1/26']*9,bias_domain=['-3/5','3/5'],arithmetic_policy=K.POLICY,
        domain_source='joint_event_26',budget={'max_nodes':1,'max_seconds':'30','position_resolution':'1/20'}))


def certificate(x,kind='PENDING',mode='4d'):
    root=C.event_root(x)
    m=9 if mode=='4d' else 8
    cert=dict(schema_version=C.VERSION,source_commit=C.BASE,input_hash=x['input_hash'],mode=mode,
        measurement_ids=K.IDS[:m],threshold_certificate=K.threshold(m))
    if root is None:
        return dict(cert,status='EVENT_ROOT_EMPTY')
    nodes=[{'id':'r','kind':kind,'box':root}]
    ctx=C.Context(x,root)
    return dict(cert,root='r',nodes=nodes,queue=['r'] if kind=='PENDING' else [],
        projections=ctx.projections(nodes),domain_contact=kind!='OUTSIDE',
        counts={k:int(k==kind) for k in ('SPLIT','INSIDE','OUTSIDE','UNDECIDED','PENDING')},
        cost={'processed_nodes':int(kind!='PENDING'),'search_seconds':'0','certificate_write_seconds':'0','peak_rss_bytes':'0','distance_evaluations':0},
        status={'PENDING':'BUDGET_OUTER','OUTSIDE':'EMPTY_IN_DECLARED_DOMAIN','INSIDE':'OUTER_CERTIFIED'}[kind],
        internal_semantics='forall_position_exists_bias_and_observation' if m==9 else 'forall_position_exists_observation',bias_recovery=[])


class Tests(unittest.TestCase):
    def setUp(self):
        self.x=fixture()
        self.root=C.event_root(self.x)
        self.ctx=C.Context(self.x,self.root)
        self.zero=[['0','0']]*4

    def test_vertical_distance(self):
        self.assertEqual(self.ctx.bounds(self.zero,'4d'),(26,26))

    def test_contact(self):
        self.assertEqual(self.root[:2],self.zero[:2])
        self.assertEqual(self.ctx.recovery(['0']*4)['inner'],['0','0'])

    def test_equal_heights(self):
        self.x['heights']={'p':'0','s':'0'}
        ctx=C.Context(self.x,self.root)
        for mode in ('4d','no_peer'):
            old=dict(anchor_map={k:v[:2] for k,v in self.x['anchors'].items()},domains=self.root+[self.x['bias_domain']],observation_intervals=self.x['observations'],noise_model={'variance':self.x['variance']})
            self.assertEqual(ctx.bounds(self.root,mode),K.bounds(old,self.root,mode))

    def test_different_vehicle_heights(self):
        self.x['heights']['s']='2'
        ctx=C.Context(self.x,self.root)
        self.assertEqual(ctx.peer_distance(ctx.box(self.zero)),(1,1))

    def test_empty(self):
        self.x['observations'][0]=['-5','-5']
        K.seal(self.x)
        self.assertEqual(C.check(self.x,certificate(self.x))['status'],'EVENT_ROOT_EMPTY')

    def test_budget(self):
        self.assertEqual(C.check(self.x,certificate(self.x))['status'],'BUDGET_OUTER')

    def test_one_node_cap_split(self):
        cert=certificate(self.x)
        root=cert['nodes'][0]
        root.update(kind='SPLIT',axis=2,cut='0',children=['l','r2'])
        for i,name in enumerate(root['children']):
            box=copy.deepcopy(root['box'])
            box[2][1-i]='0'
            cert['nodes'].append(dict(id=name,box=box,kind='PENDING'))
        cert.update(queue=['l','r2'],projections=self.ctx.projections(cert['nodes']))
        cert['counts'].update(SPLIT=1,PENDING=2)
        cert['cost']['processed_nodes']=1
        self.assertEqual(C.check(self.x,cert)['counts']['PENDING'],2)

    def test_N4_exclusion(self):
        cert=certificate(self.x,'OUTSIDE','no_peer')
        self.assertEqual(C.check(self.x,cert)['status'],'EMPTY_IN_DECLARED_DOMAIN')

    def test_closed_inside(self):
        self.x['heights']={'p':'0','s':'0'}
        self.x['observations']=[['0','0'] for _ in range(9)]
        self.x['observations'][0]=['-1','-1']
        self.x['variance'][0]='1/26'
        K.seal(self.x)
        ctx=C.Context(self.x,C.event_root(self.x))
        self.assertEqual(ctx.bounds(self.zero,'4d'),(26,26))
        self.assertEqual(ctx.recovery(['0']*4)['status'],'FEASIBLE_PROVED')

    def test_lost_queue(self):
        cert=certificate(self.x)
        cert['queue']=[]
        with self.assertRaisesRegex(ValueError,'QUEUE'): C.check(self.x,cert)

    def test_tampered_height(self):
        cert=certificate(self.x)
        self.x['heights']['p']='2'
        with self.assertRaisesRegex(ValueError,'INPUT_HASH'): C.check(self.x,cert)

    def test_swapped_car_ids(self):
        cert=certificate(self.x)
        cert['measurement_ids']=cert['measurement_ids'][4:8]+cert['measurement_ids'][:4]+cert['measurement_ids'][8:]
        with self.assertRaisesRegex(ValueError,'MEASUREMENT_IDENTITY'): C.check(self.x,cert)

    def test_rebound_hash(self):
        cert=certificate(self.x)
        self.x['case_id']='other'
        K.seal(self.x)
        with self.assertRaisesRegex(ValueError,'CERT_IDENTITY'): C.check(self.x,cert)

    def counter(self,index):
        ex=json.loads((D/'lunar_end_to_end/interface/counterexample.json').read_text(),parse_float=str)[index]
        x=self.x
        m=len(ex['observation'])
        x.update(heights={car:ex[car][2] for car in ('p','s')},anchors={f'a{i}':xyz for i,xyz in enumerate(ex['anchors'])},
            observations=[[v,v] for v in ex['observation']],measurement_ids=K.IDS[:m],variance=['1/625']*m,bias_domain=['0','0'])
        K.seal(x)
        root=C.event_root(x)
        ctx=C.Context(x,root)
        point=ex['p'][:2]+ex['s'][:2]
        self.assertTrue(all(a<=K.q(v)<=b for v,(a,b) in zip(point,map(K.iv,root))))
        box=[[v,v] for v in point]
        lo,hi=ctx.bounds(box,'4d' if m==9 else 'no_peer')
        want=K.q(ex['slant_metric_at_b0'])
        self.assertLess(max(abs(lo-want),abs(hi-want)),K.F('1e-9'))
        self.assertLess(hi,ex['threshold'])
        x['heights']={'p':'0','s':'0'}
        for xyz in x['anchors'].values(): xyz[2]='0'
        self.assertGreater(C.Context(x,root).bounds(box,'no_peer')[0],ex['threshold'])

    def test_PR137_N4(self): self.counter(0)
    def test_PR137_P4(self): self.counter(1)


if __name__=='__main__':
    unittest.main()

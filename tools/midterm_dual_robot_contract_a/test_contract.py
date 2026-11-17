import copy
import json
import tempfile
import unittest
from pathlib import Path
from core import *
from generate import make, GEOMETRIES
from check import archive_check, read_json

# These are hand-built proof fixtures, never locator/search outputs or measured costs.
def fixture(x,mode='4d',split=False):
    dim=5 if mode=='5d' else 4; box=copy.deepcopy(x['domains'][:dim])
    nodes=[{'id':'r','box':box,'kind':'PENDING'}]
    if split:
        a=copy.deepcopy(box); b=copy.deepcopy(box); a[0][1]='0'; b[0][0]='0'
        nodes=[{'id':'r','box':box,'kind':'SPLIT','axis':0,'cut':'0','children':['l','h']},
               {'id':'l','box':a,'kind':'PENDING'},{'id':'h','box':b,'kind':'PENDING'}]
    c={'schema_version':VERSION,'input_hash':x['input_hash'],'source_commit':BASE,'mode':mode,
       'measurement_ids':IDS[:8 if mode=='no_peer' else 9], 'threshold_certificate':threshold(8 if mode=='no_peer' else 9),
       'root':'r','nodes':nodes,'queue':[],'projections':{},'domain_contact':True,'counts':{},
       'status':'BUDGET_OUTER','internal_semantics':'forall_state_exists_observation' if mode=='5d' else ('forall_position_exists_bias_and_observation' if mode=='4d' else 'forall_position_exists_observation'),
       'bias_recovery':[],'cost':{'processed_nodes':0,'search_seconds':'120','certificate_write_seconds':'0','peak_rss_bytes':'0','distance_evaluations':0}}
    refresh(c); return c

def refresh(c):
    c['counts']={k:sum(n['kind']==k for n in c['nodes']) for k in ('SPLIT','OUTSIDE','INSIDE','UNDECIDED','PENDING')}
    c['queue']=[n['id'] for n in c['nodes'] if n['kind']=='PENDING']
    c['projections']=projections(c['nodes']); c['cost']['processed_nodes']=len(c['nodes'])-len(c['queue'])

class ContractTests(unittest.TestCase):
    def setUp(self): self.x=make('test')[0]; self.c=fixture(self.x,split=True)
    def reject(self,c=None,x=None):
        with self.assertRaises((Invalid,KeyError,TypeError,ValueError)): check(x or self.x,c or self.c)
    def test_01_all_modes_root(self):
        for mode in ('5d','4d','no_peer'): self.assertTrue(check(self.x,fixture(self.x,mode))['certificate_valid'])
    def test_02_partition(self): self.assertTrue(check(self.x,self.c)['certificate_valid'])
    def test_03_deleted_queue(self): self.c['queue']=[]; self.reject()
    def test_04_missing_branch(self): self.c['nodes'].pop(); self.reject()
    def test_05_wrong_threshold(self): self.c['threshold_certificate']['tau']='1'; self.reject()
    def test_06_duplicate_observation(self): self.c['measurement_ids'][1]=IDS[0]; self.reject()
    def test_07_false_outside(self):
        self.c['nodes'][1]['kind']='OUTSIDE'; self.c['nodes'][1]['lower']='999999'; refresh(self.c); self.reject()
    def test_08_noncovering_child(self): self.c['nodes'][1]['box'][0][1]='-1'; self.reject()
    def test_09_wrong_projection(self): self.c['projections']['s']['rectangles'].pop(); self.reject()
    def test_10_wrong_radius(self): self.c['projections']['p']['radius']='0'; self.reject()
    def test_11_wrong_recovery(self): self.c['bias_recovery']=[{'point':['0']*4,'result':{'outer':['0','0']}}]; self.reject()
    def test_12_root_cropped(self): self.c['nodes'][0]['box'][0][0]='-5'; self.reject()
    def test_13_duplicate_node(self): self.c['nodes'].append(copy.deepcopy(self.c['nodes'][1])); self.reject()
    def test_14_orphan(self):
        n=copy.deepcopy(self.c['nodes'][1]); n['id']='orphan'; self.c['nodes'].append(n); self.reject()
    def test_15_cycle(self): self.c['nodes'][0]['children'][0]='r'; self.reject()
    def test_16_false_inside(self): self.c['nodes'][1]['kind']='INSIDE'; refresh(self.c); self.reject()
    def test_17_false_empty(self): self.c['status']='EMPTY_IN_DECLARED_DOMAIN'; self.reject()
    def test_18_quantifier(self): self.c['internal_semantics']='forall_state_exists_observation'; self.reject()
    def test_19_cost_count(self): self.c['cost']['processed_nodes']=999999; self.reject()
    def test_20_negative_cost(self): self.c['cost']['search_seconds']='-1'; self.reject()
    def test_21_wrong_input_hash(self): self.c['input_hash']='f'*64; self.reject()
    def test_22_wrong_noise_dimension(self): self.x['noise_model']['dimension']=4; seal(self.x); self.reject()
    def test_23_nondiagonal_rejected(self): self.x['noise_model']['R']=[[1,1],[1,1]]; seal(self.x); self.reject()
    def test_24_wrong_bias_link(self): self.x['bias_incidence'][0]=1; seal(self.x); self.reject()
    def test_25_time_varying_rejected(self): self.x['noise_model']['bias_evolution']='time_varying'; seal(self.x); self.reject()
    def test_26_truth_leak_rejected(self): self.x['truth']=[0]*5; seal(self.x); self.reject()
    def test_27_nonpositive_variance(self): self.x['noise_model']['variance'][0]='0'; seal(self.x); self.reject()
    def test_28_threshold_certificates(self):
        for m in (8,9): self.assertLess(F(threshold_check(threshold(m),m)['tail_squared_upper']),F(1,400))
    def test_29_zero_distance(self):
        x=make('zero',truth=['1']*4)[0]; b=[['1','1']]*4; self.assertEqual(bounds(x,b,'4d')[0],0)
        self.assertEqual(distance([(F(1),F(1))]*2,[(F(1),F(1))]*2),(0,0))
    def test_30_closed_touch_and_degenerate_bias(self):
        x=make('touch',truth=['0','0','0','0'])[0]; x['domains'][4]=['3/5','3/5']; x['observation_intervals'][8]=['3/5','3/5']
        r=recovery(x,['0']*4); self.assertEqual(r['outer'],['3/5','3/5']); self.assertEqual(r['inner'],['3/5','3/5'])
        self.assertEqual(gap_bounds((F(1),F(2)),(F(2),F(3)))[0],0)
    def test_31_empty_certifiable(self):
        x=make('empty')[0]; x['observation_intervals'][0]=['100','100']; seal(x)
        c=fixture(x); c['nodes'][0]['kind']='OUTSIDE'; c['status']='EMPTY_IN_DECLARED_DOMAIN'; c['domain_contact']=False; refresh(c)
        self.assertTrue(check(x,c)['certificate_valid']); self.assertIsNone(c['projections']['p']['radius'])
    def test_32_truth_outside_domain(self):
        x=make('out',truth=['7','0','2','0'])[0]
        with self.assertRaises(Invalid): recovery(x,['7','0','2','0'])
        # Input remains meaningful; coverage premise fails, no true-state-driven domain expansion.
        validate(x)
    def test_33_unit_scaling_algebra(self):
        x=self.x; point=['-1','1','2','3/2']; a=bounds(x,[[v,v] for v in point],'4d')
        y=copy.deepcopy(x); scale=F(1000)
        y['anchor_map']={k:[str(F(t)*scale) for t in v] for k,v in y['anchor_map'].items()}
        for key in ('domains','observation_intervals'): y[key]=[[str(F(t)*scale) for t in v] for v in y[key]]
        y['noise_model']['variance']=[str(F(t)*scale**2) for t in y['noise_model']['variance']]
        b=bounds(y,[[str(F(v)*scale)]*2 for v in point],'4d')
        self.assertLessEqual(a[0],b[1]); self.assertLessEqual(b[0],a[1])
        self.assertEqual(F(3,25)**2/F(1,625),F(120)**2/F(1600))
    def test_34_coordinate_rigid_transform(self):
        a=[(F(1),F(1)),(F(2),F(2))]; b=[(F(4),F(4)),(F(6),F(6))]
        def transform(z): return [(3-z[1][1],3-z[1][0]),(z[0][0]+7,z[0][1]+7)]
        self.assertEqual(distance(a,b),distance(transform(a),transform(b)))
    def test_35_exchange_vehicle(self):
        x=self.x; p=['-1','1','2','3/2']; old=bounds(x,[[v,v] for v in p],'4d')
        y=copy.deepcopy(x); y['observation_intervals']=x['observation_intervals'][4:8]+x['observation_intervals'][:4]+x['observation_intervals'][8:]
        new=bounds(y,[[v,v] for v in p[2:]+p[:2]],'4d'); self.assertEqual(old,new)
    def test_36_collinear_mirror(self):
        x=make('mirror','collinear')[0]; a=['-1','1','2','3/2']; b=['-1','-1','2','-3/2']
        self.assertEqual(bounds(x,[[v,v] for v in a],'4d'),bounds(x,[[v,v] for v in b],'4d'))
    def test_37_reference_zero_model_aligned(self):
        # Fix s to s0 in same 9-row model; peer is a known reference row, retain s's four constant residuals.
        p=[(F(1),F(1)),(F(2),F(2))]; s=[(F(4),F(4)),(F(6),F(6))]
        self.assertEqual(distance(p,s),(F(5),F(5)))
        x=self.x; pos=['-1','1','2','3/2']; z=[[v,v] for v in pos]
        direct=F(0)
        for index,car in enumerate((pos[:2],pos[2:])):
            for k in range(4):
                d=distance([(F(v),F(v)) for v in car],[(F(v),F(v)) for v in x['anchor_map'][f'a{k}']])
                direct+=gap_bounds(d,iv(x['observation_intervals'][4*index+k]))[0]**2/F(1,625)
        self.assertEqual(direct,bounds(x,z,'no_peer')[0])
    def test_38_recovery_exact_interval_formula(self):
        x=make('recover',truth=['0','0','0','0'])[0]
        x['observation_intervals']=[['5','5']]*8+[['1/5','3/10']]
        r=recovery(x,['0']*4); self.assertEqual(r['status'],'FEASIBLE_PROVED')
        # S=0, d=0; exact halfwidth sqrt(26/625), nested rational inner/outer.
        rad=sqrt_bounds(F(26,625)); self.assertEqual(r['outer'],[str(max(F(-3,5),F(1,5)-rad[1])),str(min(F(3,5),F(3,10)+rad[1]))])
    def test_39_saved_bounds_ignored(self):
        self.c['nodes'][1]['lower']='-999'; self.c['nodes'][1]['upper']='0'; self.c['success']=True
        self.assertTrue(check(self.x,self.c)['certificate_valid'])
    def test_40_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.json'; p.write_text('{"a":1,"a":2}')
            with self.assertRaises(Invalid): read_json(p)
    def test_41_exact_rational_rejects_float(self):
        with self.assertRaises(Invalid): iv([0.0,'1'])
    def test_42_domain_contact_false(self): self.c['domain_contact']=False; self.reject()
    def test_43_wrong_count(self): self.c['counts']['PENDING']=0; self.reject()
    def test_44_invalid_split_cut(self): self.c['nodes'][0]['cut']='-6'; self.reject()
    def test_45_recovery_negative_remainder(self):
        x=self.x; x['observation_intervals'][0]=['100','100']; self.assertEqual(recovery(x,['0']*4)['status'],'EMPTY_PROVED')

    def test_46_zero_remainder_tangency(self):
        x=make('tangent',truth=['0']*4)[0]
        x['observation_intervals']=[['26/5','26/5'],['126/25','126/25']]+[['5','5']]*6+[['3/5','3/5']]
        self.assertEqual(bounds(x,[['0','0']]*4,'no_peer'),(26,26))
        self.assertEqual(recovery(x,['0']*4),{'outer':['3/5','3/5'],'inner':['3/5','3/5'],'status':'FEASIBLE_PROVED'})
    def test_47_quantifier_difference_is_real(self):
        x=make('quantifier',truth=['0']*4)[0]; box=[['0','0']]*4
        self.assertEqual(bounds(x,box,'4d'),(0,0))
        self.assertGreater(bounds(x,box+[x['domains'][4]],'5d')[1],26)
    def test_48_truth_noise_event_fixed(self):
        from generate import DIRECTION
        energy=sum(F(t)**2 for t in DIRECTION)
        self.assertEqual(energy,6); self.assertLess(energy,26)
    def test_49_profile_exact_scalar_elimination(self):
        # Rational 3-4-5 distance; residual t=7/10 and B=[-3/5,3/5].
        t=F(7,10); B=(F(-3,5),F(3,5)); best=min(max(t,B[0]),B[1])
        self.assertEqual((t-best)**2,F(1,100))
        self.assertEqual(gap(F(5),(F(57,10)-B[1],F(57,10)-B[0]))**2,(t-best)**2)
    def test_50_archive_missing_denominator(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/'deterministic.json').write_text(json.dumps([self.x])); (root/'c.json').write_text(json.dumps(self.c))
            files={'c.json':hashlib.sha256((root/'c.json').read_bytes()).hexdigest()}
            r={'schema_version':VERSION,'source_commit':'a'*40,'files':files,'archive_hash':digest(files),'stage':'deterministic','records':[]}
            (root/'RESULTS_READY.json').write_text(json.dumps(r))
            with self.assertRaisesRegex(Invalid,'DENOMINATOR_MISSING'): archive_check(root,root,'a'*40)
    def test_51_archive_hash_tamper(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/'c.json').write_text('{}')
            r={'schema_version':VERSION,'source_commit':'a'*40,'files':{'c.json':'0'*64},'archive_hash':'0'*64}
            (root/'RESULTS_READY.json').write_text(json.dumps(r))
            with self.assertRaisesRegex(Invalid,'ARCHIVE_HASH_MISMATCH'): archive_check(root,root,'a'*40)
    def test_52_archive_all_methods(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/'deterministic.json').write_text(json.dumps([self.x])); files={}; records=[]
            for mode in ('5d','4d','no_peer'):
                name=mode+'.json'; (root/name).write_text(json.dumps(fixture(self.x,mode)))
                files[name]=hashlib.sha256((root/name).read_bytes()).hexdigest()
                records.append({'case_id':self.x['case_id'],'mode':mode,'input_hash':self.x['input_hash'],'execution_status':'CERTIFICATE_AVAILABLE','certificate_file':name})
            r={'schema_version':VERSION,'source_commit':'a'*40,'files':files,'archive_hash':digest(files),'stage':'deterministic','records':records}
            (root/'RESULTS_READY.json').write_text(json.dumps(r))
            result=archive_check(root,root,'a'*40); self.assertEqual(result['certified'],3)
            records.append(records[0]); (root/'RESULTS_READY.json').write_text(json.dumps(r))
            with self.assertRaisesRegex(Invalid,'DENOMINATOR_DUPLICATE'): archive_check(root,root,'a'*40)
    def test_53_nonempty_full_internal_certificate(self):
        x=make('inside',truth=['0']*4)[0]; x['domains']=[['0','0']]*5; seal(x)
        for mode in ('4d','5d','no_peer'):
            c=fixture(x,mode); c['nodes'][0]['kind']='INSIDE'; c['status']='OUTER_CERTIFIED'; refresh(c)
            self.assertTrue(check(x,c)['certificate_valid'])

if __name__=='__main__': unittest.main(verbosity=2)

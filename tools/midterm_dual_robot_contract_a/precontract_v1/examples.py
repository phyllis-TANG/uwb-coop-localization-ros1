"""Hand-calculable fixtures only, not B's seven-case performance experiment."""
import copy
import importlib.util
import json
from pathlib import Path

_spec=importlib.util.spec_from_file_location('pre_producer',Path(__file__).with_name('propose.py'))
P=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(P)
C=P.C;K=C.K

def small_input(kind='normal'):
    x={'schema_version':K.VERSION,'model_id':'dual_robot_single_epoch_diagonal_v1','state_order':K.ORDER[:],
       'measurement_ids':K.IDS[:],'anchor_map':{'a0':['0','0'],'a1':['4','0'],'a2':['0','4'],'a3':['4','4']},
       'bias_incidence':[0]*8+[1],'domains':[['-6','6'] for _ in range(4)]+[['-3/5','3/5']],
       'observation_intervals':[['2','3'] for _ in range(8)]+[['0','4']],
       'noise_model':{'kind':'known_diagonal_gaussian','dimension':9,'variance':['1/26']*9,'independence':'nine_unique_raw_errors','bias_evolution':'single_constant'},
       'threshold_certificate':K.threshold(9),'arithmetic_policy':K.POLICY.copy(),
       'budget':{'max_nodes':100001,'max_seconds':'120','position_resolution':'1/8','bias_resolution':'1/20'},
       'source_commit':K.BASE,'case_id':'hand_'+kind,'units':'m','frame':'synthetic_xy','epoch':'t0','antenna_reference':'2d_antenna',
       'representation':'enclosing_closed_cartesian_intervals','position_prior':None,'motion':None}
    if kind=='collinear':
        x['anchor_map']={f'a{i}':[str(v),'0'] for i,v in enumerate((-3,-1,1,3))}
        x['observation_intervals']=[['1','4'] for _ in range(8)]+[['2','2']]
    elif kind in ('zero','boundary','empty'):
        x['anchor_map']={f'a{i}':['0','0'] for i in range(4)}
        x['observation_intervals']=[['0','0'] for _ in range(9)]
        if kind=='boundary':
            x['domains'][0]=['-2','1']
            x['observation_intervals']=[['0','0']]+[['1','1']]*3+[['0','0']]*4+[['1','1']]
        if kind=='empty':x['anchor_map']['a1']=['4','0']
    return K.seal(x)

def tree_fixture(x,split=False):
    root={'id':'r','box':copy.deepcopy(x['domains'][:4]),'kind':'UNDECIDED'};nodes=[root]
    if split:
        cut=str(sum(map(C.F,root['box'][0]))/2)
        left=copy.deepcopy(root['box']);right=copy.deepcopy(root['box']);left[0][1]=cut;right[0][0]=cut
        root.update(kind='SPLIT',axis=0,cut=cut,children=['l','h'])
        nodes += [{'id':'l','box':left,'kind':'PENDING'},{'id':'h','box':right,'kind':'PENDING'}]
    counts={k:sum(n['kind']==k for n in nodes) for k in ('SPLIT','OUTSIDE','INSIDE','UNDECIDED','PENDING')}
    return {'schema_version':K.VERSION,'input_hash':x['input_hash'],'source_commit':K.BASE,'mode':'4d','measurement_ids':K.IDS[:],
            'threshold_certificate':K.threshold(9),'root':'r','nodes':nodes,'queue':['l','h'] if split else [],
            'projections':K.projections(nodes),'domain_contact':True,'counts':counts,'status':'BUDGET_OUTER' if split else 'OUTER_CERTIFIED',
            'internal_semantics':'forall_position_exists_bias_and_observation','bias_recovery':[],
            'cost':{'processed_nodes':1,'search_seconds':'0','certificate_write_seconds':'0','peak_rss_bytes':'0','distance_evaluations':0}}

def composite_fixture(x,pre,split=False):
    y=C.restricted_input(x,pre)
    return {'schema_version':C.VERSION,'original_input_hash':x['input_hash'],'preprocessing':pre,'preprocess_hash':K.digest(pre),
            'restricted_input_hash':None if y is None else y['input_hash'],'search_certificate':None if y is None else tree_fixture(y,split)}

def write_examples(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    for kind in ('normal','collinear','boundary','zero','fallback','empty'):
        x=small_input(kind);skip={'p_y_min':'FALLBACK_UNCERTIFIED','s_x_max':'FALLBACK_TIMEOUT'} if kind=='fallback' else None
        p=P.propose(x,skip=skip);c=composite_fixture(x,p)
        result=C.check_composite(x,c)
        for suffix,obj in [('input',x),('preprocessing',p),('composite',c),('expected',result)]:
            (out/f'{kind}.{suffix}.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
    print('Wrote six hand fixtures; zero localization-search calls.')

if __name__=='__main__':
    import argparse
    a=argparse.ArgumentParser();a.add_argument('out');args=a.parse_args();write_examples(args.out)

"""Optional 6-epoch, one-channel stationary GMP check; no random samples."""
import itertools
import json
from fractions import Fraction as F

def det(matrix):
    a=[row[:] for row in matrix]; result=F(1)
    for j in range(len(a)):
        pivot=next((i for i in range(j,len(a)) if a[i][j]),None)
        if pivot is None:return F(0)
        if pivot!=j:a[pivot],a[j]=a[j],a[pivot];result=-result
        p=a[j][j]; result*=p
        for i in range(j+1,len(a)):
            ratio=a[i][j]/p
            for k in range(j+1,len(a)):a[i][k]-=ratio*a[j][k]
    return result

def minors(a):
    return [det([[a[i][j] for j in subset] for i in subset])
            for size in range(1,len(a)+1) for subset in itertools.combinations(range(len(a)),size)]

def run():
    G=[[F(1,6)]*6,[-F(1),F(0),F(0),F(0),F(0),F(1)]]
    over=[[2*F(3,5)**abs(i-j) for j in range(6)] for i in range(6)]
    rows=[]
    for alpha in (F(1,3),F(5,9),F(7,9)):
        diff=[[over[i][j]-alpha**abs(i-j) for j in range(6)] for i in range(6)]
        response=[[sum(G[i][k]*diff[k][l]*G[j][l] for k in range(6) for l in range(6)) for j in range(2)] for i in range(2)]
        ms=minors(diff); rs=minors(response)
        assert len(ms)==63 and all(v>=0 for v in ms+rs)
        rows.append({'alpha':str(alpha),'full_principal_minors':list(map(str,ms)), 'response_principal_minors':list(map(str,rs)), 'passed':True})
    return {'scope':'optional stationary GMP only; no initial variance reduction; not integrated into localization',
            'epochs':6,'channels':1,'sigma_squared':'1','alpha_domain':['1/3','7/9'], 'over_alpha':'3/5','k':'2',
            'fixed_G':[[str(v) for v in row] for row in G],'planned_parameter_points':3,'completed':3,'failed':0,'random_samples':0,'rows':rows}

if __name__=='__main__':print(json.dumps(run(),indent=2))

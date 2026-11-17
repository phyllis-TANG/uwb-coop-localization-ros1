"""Predeclared deterministic validation cases, not coverage Monte Carlo."""
from interval import point,add,sub,square,sqrt,LO,HI,D,encode

def make_model(anchors,truth,unknown,noise,override=None):
 ys=[]
 for k,a in enumerate(anchors):
  z=sqrt(add(square(sub(point(truth[0]),point(a[0]))),square(sub(point(truth[1]),point(a[1])))))
  if k==3:z=add(z,point(truth[2] if unknown else '.3'))
  z=add(z,point(noise[k]))
  # Exact finite nominal with stated measurement representation uncertainty.
  mid=LO.divide(LO.add(z[0],z[1]),D(2));eta=D('1e-24')
  ys.append([str(LO.subtract(mid,eta)),str(HI.add(mid,eta))])
 if override is not None:ys=[[v,v] for v in override]
 return dict(anchors=anchors,observations=ys,sigma=['.04']*4,affected_index=3,unknown_bias=unknown,known_bias='.3',domain=[['-6','6'],['-6','6']]+([['-.6','.6']] if unknown else []),representation_halfwidth_m='1e-24')

def cases(config):
 out=[]
 for stage in (1,2):
  for i,kind in enumerate(('good','mirror','boundary','empty' if stage==1 else 'budget')):
   anchors=config['anchors']['collinear' if kind=='mirror' else 'good']
   truth=['6','0'] if kind=='boundary' else ['1','2']
   if stage==2:truth+=['.6' if kind=='boundary' else '.3']
   noise=['0']*4 if kind in ('mirror','boundary') else ['.02','-.01','.03','-.02']
   model=make_model(anchors,truth,stage==2,noise,override=['-10']*4 if kind=='empty' else None)
   s=dict(config['settings']);s['max_boxes']=16 if kind=='budget' else s['max_boxes']
   out.append(dict(id=f's{stage}_{kind}',stage=stage,kind=kind,model=model,settings=s,evaluation=dict(truth=truth,prescribed_noise_m=noise,generated_under_model=kind!='empty',mirror_truth=[truth[0],str(-D(truth[1]))]+truth[2:] if kind=='mirror' else None)))
 return out

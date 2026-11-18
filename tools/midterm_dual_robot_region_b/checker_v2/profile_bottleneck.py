"""Post-run zero-search call attribution; never used for the admission timing."""
import argparse,cProfile,pstats,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import read,write,DOC
from checker_v2.a_loader import load_a

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);args=ap.parse_args();lock=read(DOC/'checker_v2/A_SOURCE_LOCK.json');_,a=load_a(lock);rows=[]
 # Fixed geometry representatives, not selected by measured timing or success.
 for case in ['normal_b0_zero','near_collinear_b0_zero','collinear_b0_zero']:
  for method in ['P4','N4']:
   unit=case+'_'+method;r=read(args.root/'deterministic'/(unit+'.result.json.gz'));c=read(args.root/'deterministic'/(unit+'.certificate.json.gz'));pr=cProfile.Profile();pr.enable();v=a.check(r['case']['a_input'],c);pr.disable();assert v==r['certificate_a']['validation'];stats=pstats.Stats(pr);functions=[]
   for (file,line,name),(cc,nc,tt,ct,callers) in stats.stats.items():
    if file.endswith('checker_v2.py') or (file.endswith('/core.py') and 'dual_robot_contract_a' in file):functions.append(dict(file=Path(file).name,line=line,function=name,primitive_calls=cc,total_calls=nc,self_seconds=tt,cumulative_seconds=ct))
   rows.append(dict(id=unit,functions=functions,profiled_total_seconds=stats.total_tt,status='PASS',search_calls=0))
 write(DOC/'checker_v2/BOTTLENECK_PROFILE.json',dict(policy='Six predeclared geometry/method representatives, cProfile overhead included; attribution only, not gate timings; cumulative function times overlap and must not be summed.',rows=rows,search_calls=0));print('Six zero-search A call profiles completed')
if __name__=='__main__':main()

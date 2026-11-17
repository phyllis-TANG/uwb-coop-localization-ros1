"""Add absolute bias diagnostics from complete saved signed columns, no reanalysis or fitting."""
from common import *
import argparse,shutil
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();protect();checks=json.loads((a.input/'CHECKS.json').read_text());assert checks['endpoints']==1800 and checks['region_points']==115200
 a.out.mkdir(parents=True,exist_ok=False)
 for path in a.input.iterdir():
  if path.name!='DECOMPOSITION.csv.gz':shutil.copyfile(path,a.out/path.name)
 rows=readcsv(a.input/'DECOMPOSITION.csv.gz')
 for row in rows:
  for name in ['gradient','remainder','jacobian','sum','difference','nonlinear_error','affine_error']:
   value=row[name+'_bias'];row[name+'_bias_abs']=abs(float(value)) if value else None
 table(a.out/'DECOMPOSITION.csv.gz',rows);print('Enriched all',len(rows),'saved rows; optimizer calls=0')

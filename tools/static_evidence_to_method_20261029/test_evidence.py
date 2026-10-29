#!/usr/bin/env python3
"""Independent standard-library readback of saved ranges, no analyzer/Jacobian import."""
import csv,gzip,hashlib,json,math,statistics,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];D=ROOT/'docs/research/static_evidence_to_method_20261029'
def rows(p):
 with p.open() as f:return list(csv.DictReader(f))
class Evidence(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.report=json.loads((D/'RUN_MANIFEST.json').read_text());cls.data=rows(D/'COMPACT_RESULTS.csv');cls.fresh=[r for r in cls.data if r['origin']=='supplement_this_run'];cls.by={r['id']:r for r in cls.report['inputs']}
 def test_exact_ten_and_no_extra_bag(self):
  self.assertEqual(set(self.by),{'P1','P4','clear_A','human_B','human_B_repeat','clear_C','T01','T02','T03','T04'})
  self.assertEqual(len(rows(D/'OLD_STATIC_EVIDENCE.csv')),10)
  self.assertEqual(self.report['holdout_bags_opened'],[]);self.assertEqual(self.report['new_FGO_runs'],0)
 def test_independent_integer_time_and_standard_library_median_MAD(self):
  checked=0
  for name,inp in self.by.items():
   p=Path(self.report['external_cache_root'])/(name+'_ranges.jsonl.gz')
   self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),inp['decoded_cache_sha256'])
   with gzip.open(p,'rt') as f:cache=[json.loads(x) for x in f]
   self.assertEqual(len(cache),inp['ranges_decoded']);self.assertEqual(len(cache),len({x['record_id'] for x in cache}))
   for r in (r for r in self.fresh if r['bag']==name):
    lo=inp['start_receive_ns']+round(float(r['start_s'])*1e9);hi=inp['start_receive_ns']+round(float(r['end_s'])*1e9);inc=r['end_inclusive']=='True'
    frames=[x for x in cache if x['car']==r['car'] and x['receive_ns']>=lo and (x['receive_ns']<=hi if inc else x['receive_ns']<hi)]
    vals=[];missing=invalid=dup=0
    for x in frames:
     v=[a['range'] for a in x['ranges'] if a['anchor']==r['link']]
     if len(v)==0:missing+=1
     elif len(v)>1:dup+=1
     elif v[0] is None or not math.isfinite(v[0]) or v[0]<=0:invalid+=1
     else:vals.append(v[0])
    self.assertEqual((len(frames),len(vals),missing,invalid,dup),tuple(int(r[k]) for k in ['frames','valid','missing_entry','invalid_entry','duplicate_target_frames']))
    if vals:
     med=statistics.median(vals);mad=statistics.median(abs(v-med) for v in vals)
     self.assertAlmostEqual(med,float(r['median_m']),places=12);self.assertAlmostEqual(mad,float(r['MAD_m']),places=12)
    else:self.assertEqual(r['median_m'],'');self.assertEqual(r['MAD_m'],'')
    checked+=1
  self.assertEqual(checked,300)
 def test_coverage_and_absence_denominators(self):
  for r in self.fresh:
   n=int(r['frames']);v=int(r['valid']);self.assertEqual(n,v+int(r['missing_entry'])+int(r['invalid_entry'])+int(r['duplicate_target_frames']))
   if n:self.assertAlmostEqual(float(r['coverage']),v/n)
   else:self.assertEqual(r['coverage'],'');self.assertEqual(r['status'],'topic_absent')
 def test_T02_prespecified_windows(self):
  r=[x for x in self.fresh if x['bag']=='T02' and x['car']=='car1' and x['link']=='node_0'];self.assertEqual([x['window'] for x in r],['whole','pre','wall_action','recovery1','peer_action','recovery2'])
  self.assertEqual([(float(x['start_s']),float(x['end_s'])) for x in r[1:5]],[(5,35),(45,75),(85,155),(165,195)])
 def test_no_geometry_invented_or_calibration_transferred(self):
  for r in self.fresh:
   if r['bag'] not in ['P1','P4']:
    self.assertEqual(r['P1_offset_m'],'');self.assertEqual(r['corrected_minus_geometry_m'],'')
    if r['link'] not in ['node_0','node_1']:self.assertEqual(r['manual_reference_m'],'')
  geom=json.loads((ROOT/'docs/field_tests/20261017/session_config.json').read_text())['anchors_xyz_m']
  for r in self.fresh:
   if r['manual_reference_m'] and r['reference_kind']=='manual_antenna_XYZ_slant':
    p=[2,2,.2] if r['bag']=='P1' else [3,3,.2];expected=math.sqrt(sum((x-y)**2 for x,y in zip(p,geom[r['link']])))
    self.assertAlmostEqual(expected,float(r['manual_reference_m']),places=12)
 def test_reuse_identity_and_precision(self):
  checks=json.loads((D/'CHECKS.json').read_text());self.assertEqual(len(checks),29);self.assertTrue(all(r['pass_'] for r in checks))
  self.assertEqual(sum(r['origin']=='reused_numeric' for r in self.data),34)
  for p,h in self.report['source_sha256'].items():
   src=Path(p);src=src if src.is_absolute() else ROOT/src;self.assertEqual(hashlib.sha256(src.read_bytes()).hexdigest(),h)
 def test_zero_is_valid_difference_not_missing(self):
  x=next(r for r in self.fresh if (r['bag'],r['window'],r['car'],r['link'])==('human_B_repeat','whole','car1','node_0'))
  self.assertEqual(float(x['median_minus_reference_m']),0.)
  absent=next(r for r in self.fresh if (r['bag'],r['car'],r['link'])==('P1','car1','node_0'));self.assertEqual(absent['median_minus_reference_m'],'')
if __name__=='__main__':unittest.main(verbosity=2)

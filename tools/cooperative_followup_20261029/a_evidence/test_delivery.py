"""Check readback identity/denominators and integer timestamps, without estimation."""
import json,tempfile,unittest
from pathlib import Path
from io_evidence import ART,sha,table
from summarize import parsed
class DeliveryContracts(unittest.TestCase):
 def test_integer_nanoseconds_are_not_float_coerced(self):
  with tempfile.TemporaryDirectory(dir=ART/'tmp') as tmp:
   p=Path(tmp)/'ns.csv';p.write_text('state_epoch_ns,cutoff_epoch_ns,value\n1790000000000000001,1790000001000000001,\n')
   r=parsed(p)[0];self.assertEqual(r['state_epoch_ns'],1790000000000000001);self.assertIsInstance(r['state_epoch_ns'],int);self.assertIsNone(r['value'])
 def test_full_publication_denominators_and_unknowns_preserved(self):
  rows=table(ART/'analysis-v2/diagnostics.csv');self.assertEqual(len(rows),1260)
  keys={(r['scenario'],r['method'],r['car'],r['state_epoch_ns']) for r in rows};self.assertEqual(len(keys),1260)
  self.assertEqual(sum(r['publication_mode']=='unknown' for r in rows),40)
  for r in rows:self.assertEqual(int(r['cutoff_epoch_ns'])-int(r['state_epoch_ns']),10**9)
  self.assertEqual(sum(r['local_GN_xy_trace_sigma_proxy_m']=='' for r in rows),40)
 def test_recomputed_table_receipt_matches_source(self):
  r=json.loads((ART/'analysis-v2/EXTRACTION_CHECK.json').read_text());self.assertEqual(r['status'],'PASS');self.assertEqual(r['estimator_runs'],0)
  self.assertEqual(r['source_reader_sha256'],sha(Path(__file__).with_name('extract.py')))
  self.assertEqual(r['signal_source_sha256'],sha(Path(__file__).with_name('signals.py')))
  self.assertEqual(r['max_original_metric_abs_difference'],0);self.assertEqual(r['original_metrics_rows_recomputed'],320)
 def test_summary_epoch_identity_and_tail_history(self):
  orig=table(ART/'analysis-v2/local_signals_offline_join.csv');w=table(ART/'summary-v2/local_witnesses.csv')
  lookup={(x['scenario'],x['car'],x['t_s']):x for x in orig}
  for x in w:
   self.assertEqual(x['state_epoch_ns'],lookup[x['scenario'],x['car'],x['t_s']]['state_epoch_ns'])
  history=table(ART/'summary-v2/history_readback.csv')
  for x in history:
   if float(x['t_s'])>=59:self.assertEqual(int(x['active_changed_wall_bin_n']),0);self.assertEqual(int(x['consumed_changed_wall_factor_n']),60)
if __name__=='__main__':unittest.main(verbosity=2)

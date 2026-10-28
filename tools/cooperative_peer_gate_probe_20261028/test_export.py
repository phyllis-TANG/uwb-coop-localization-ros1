import json,os,unittest
from pathlib import Path
from unittest.mock import patch
from probe import ProbeReplay,export_baseline,numeric
from records import read
class ExportTests(unittest.TestCase):
 def test_all_24_archived_cells_export_without_estimator_initialization(self):
  root=Path(os.environ['PEER_GATE_OLD_ROOT'])/'formal-v1';index=json.loads((root/'matrix.json').read_text());count=0
  with patch.object(ProbeReplay,'__init__',side_effect=AssertionError('No replay allowed in exporter')):
   for cell in index['cells']:
    method='G0' if cell['arm']=='D0' else 'G1'
    for row in read(root/cell['run_relative_path']/'updates.jsonl.gz'):
     self.assertEqual(numeric(row),numeric(export_baseline(row,method)));count+=1
  self.assertEqual(count,1512)
if __name__=='__main__':unittest.main(verbosity=2)

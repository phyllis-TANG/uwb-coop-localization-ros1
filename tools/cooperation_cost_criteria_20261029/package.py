"""Delivery identity and schema checks; never modifies source results."""
import csv,json,platform,subprocess
import numpy,matplotlib
from analyze import ROOT,DOC,HERE,sha,dump,load
from pathlib import Path
ART=Path('/home/ubuntu22/uwb-cooperation-cost-criteria-20261029-artifacts')
rows=json.loads((DOC/'TOLERANCE_SOURCES.json').read_text());csvrows=load(DOC/'TOLERANCE_SOURCES.csv');assert len(rows)==len(csvrows)==16
for r,c in zip(rows,csvrows):
 if r['status'] in ['UNSET','NOT_ESTABLISHED']:assert r['value'] is None and c['value']==''
assert len(load(DOC/'PER_CAR.csv'))==432 and len(load(DOC/'TRADEOFF_POINTS.csv'))==216
assert len(load(DOC/'PAIRWISE_RELATIONS.csv'))==240 and len(load(DOC/'GLOBAL_RELATIONS.csv'))==20
for r in load(DOC/'PER_CAR.csv'):
 if r['phase']=='all':assert r['denominator']=='63' and r['n']==('61' if r['scope']=='common_accepted' else '63') and r['unknown']=='2'
checks=json.loads((DOC/'CHECKS.json').read_text());assert checks['recomputed_metric_scalars']==864
sources=dict(checks['source_sha256'])
for p in ['docs/research/cooperative_followup_20261029/c_scope/LAB_PRECHECK_20261030.md','docs/research/cooperative_followup_20261029/c_scope/C_SCOPE_ONE_PAGE.md','docs/research/static_evidence_to_method_20261029/DECISION.md','docs/research/static_evidence_to_method_20261029/LAB_DELTA.md','docs/field_tests/20261024_25/video_reference_20261027/MISSING_EVIDENCE.md','docs/field_tests/20261024_25/research_roadmap_20261028/README.md','docs/research/history_recovery_minimal_20261029/PLAN.md']:
 sources[p]=sha(ROOT/p)
dump(DOC/'REFERENCE_SOURCES.json',dict(checked_date='2026-10-29',sources=[dict(url='https://www.iso.org/standard/62090.html',depth='official public abstract/status; not full standard',use='scope of localization test/evaluation guidance; no borrowed numerical damage threshold'),dict(url='https://www.nist.gov/ctl/pscr/isoiec-18305-2016-table-contents',depth='official public contents',use='accuracy and non-accuracy metrics including latency/availability'),dict(url='https://www.itl.nist.gov/div898/handbook/mpc/section5/mpc521.htm',depth='full short guidance webpage',use='define measurand and combine uncertainty components; no claimed universal 1/3 requirement')]))
manifest=dict(task='COOPERATION-COST-CRITERIA-20261029',base_commit='81fb509ba2d2a1b2e1f1151d53a7e73807820bd4',branch='analysis/20261029-cooperation-cost-criteria',source_pr78_delivery='66dee2c33a431f3b087df8dd9b09731053651dce',input_sha256=sources,analysis_source_sha256={str(p.relative_to(ROOT)):sha(p) for p in HERE.glob('*.py')},source_state_at_analysis='task files not yet committed; exact bytes locked here',estimator_runs=0,development_seeds=1,conditions='paired exposed seed101; not independent validation',raw_bag_reads=0,new_thresholds=0,tests=dict(status='PASS',unit_tests=4,log_path=str(ART/'tests.log'),log_sha256=sha(ART/'tests.log'),recomputed_rmse=864,all_finite_denominator=63,common_accepted=61,unknown=2,tolerance_null_semantics='PASS',numerical_csv_equal_after_plot_label_revision=True),runtime=dict(python=platform.python_version(),numpy=numpy.__version__,matplotlib=matplotlib.__version__),commands=['OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 /home/ubuntu22/uwb-single-car-quality-fgo-v1-artifacts/venv/bin/python -m unittest discover -s tools/cooperation_cost_criteria_20261029 -p test_*.py -v','OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 /home/ubuntu22/uwb-single-car-quality-fgo-v1-artifacts/venv/bin/python tools/cooperation_cost_criteria_20261029/analyze.py','Same analysis with --output /home/ubuntu22/uwb-cooperation-cost-criteria-20261029-artifacts/plot-label-revision; plotting label offsets revised; all numerical CSV bytes identical','PYTHONDONTWRITEBYTECODE=1 /home/ubuntu22/uwb-single-car-quality-fgo-v1-artifacts/venv/bin/python tools/cooperation_cost_criteria_20261029/package.py'],delivery_metadata_correction='Initial packaging assertion expected 15 tolerance rows but actual list has 16. Count/report corrected; no numerical results or tolerance values changed.',outputs={str(p.relative_to(ROOT)):sha(p) for p in DOC.iterdir() if p.is_file() and p.name not in ['RUN_MANIFEST.json','SHA256SUMS.json']})
dump(DOC/'RUN_MANIFEST.json',manifest)
dump(DOC/'SHA256SUMS.json',{str(p.relative_to(ROOT)):sha(p) for folder in [DOC,HERE] for p in folder.iterdir() if p.is_file() and p.name!='SHA256SUMS.json'})
for p,h in sources.items():assert sha(ROOT/p)==h
print('Delivery verified: 16 tolerance entries; 432 metrics; 216 paired points; source hashes unchanged')

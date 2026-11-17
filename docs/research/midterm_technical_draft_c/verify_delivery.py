#!/usr/bin/env python3
"""Read-only evidence and delivery audit; never imports or runs localization code."""
from pathlib import Path
import csv, hashlib, json, re, subprocess
ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
BASE = 'c51411433d30dc379bd69cf5fb20a11e196b7182'
ALLOWED = 'docs/research/midterm_technical_draft_c/'
checks = {}
def git(*args):
    return subprocess.check_output(['git', '-C', str(REPO), *args])
rows = list(csv.DictReader((ROOT/'CLAIM_EVIDENCE.csv').open(encoding='utf-8-sig')))
assert rows and len({r['claim_id'] for r in rows}) == len(rows)
for r in rows:
    assert re.fullmatch(r'[0-9a-f]{40}', r['fixed_commit']), r
    # Missing-original entries point to the document recording that absence.
    git('cat-file', '-e', r['fixed_commit']+':'+r['evidence_file'])
checks['claim_rows_with_existing_fixed_source'] = len(rows)
manifest=json.loads((ROOT/'evidence/SOURCE_COPIES.json').read_text())
for item in manifest['copies']:
    data=(ROOT/item['delivery_file']).read_bytes()
    assert hashlib.sha256(data).hexdigest()==item['sha256'], item
    assert data==git('show',item['fixed_commit']+':'+item['source_file']),item
checks['byte_identical_source_copies']=len(manifest['copies'])
text=(ROOT/'TECHNICAL_DRAFT_ZH.md').read_text()
parts='\n\n'.join((ROOT/s).read_text().rstrip() for s in ['sections/00_scope.md','sections/01_03_methods.md','sections/04_05_results.md'])+'\n'
assert text==parts
checks['assembled_body_matches_editable_sections']=True
images=re.findall(r'!\[[^\]]*\]\(([^\s)]+)',text)
for path in images:
    assert (ROOT/path).is_file(), path
checks['body_image_references']=len(images)
assert '99.01%' not in text and '3小时' not in text
for anchor in ['43200','14400','6400','65','per-robot cooperative benefit']:
    assert anchor in text,anchor
checks['required_numeric_and_terminology_anchors']=True
required=['README.md','TECHNICAL_DRAFT_ZH.md','CLAIM_EVIDENCE.csv','FIGURE_TABLE_INDEX.md','OPEN_QUESTIONS.md','HANDOFF.md','TECHNICAL_REPORT_ZH.tex','TECHNICAL_REPORT_ZH.pdf']
for file in required:
    assert (ROOT/file).is_file(),file
checks['required_deliverables']=required
tracked=git('diff','--name-only',BASE).decode().splitlines()
untracked=git('ls-files','--others','--exclude-standard').decode().splitlines()
assert all(p.startswith(ALLOWED) for p in tracked+untracked),tracked+untracked
checks['only_allowed_directory_changed']=True
checks['new_localization_runs']=0
checks['new_truth_linearized_diagnostics']=0
checks['scope_note']='File/source checks only. Human review handles mathematical meaning and statistical interpretations.'
print(json.dumps(checks,ensure_ascii=False,indent=2))

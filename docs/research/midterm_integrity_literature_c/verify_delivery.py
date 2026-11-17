#!/usr/bin/env python3
"""Read-only structure/source audit; no numerical experiment or web fetch."""
from pathlib import Path
import json,re,subprocess
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[2]
BASE='34f364d77c0964f22563bad6e5869567fe5f163c'
A='b340f6bd05a97ac3f80ea4796d4c317114f508a8'
PREFIX='docs/research/midterm_integrity_literature_c/'
def git(*args):return subprocess.check_output(['git','-C',str(REPO),*args],text=True).strip()
required=['README.md','LITERATURE_MATRIX.md','THEORY_AUDIT.md','METHOD_OPTIONS.md','DECISION_TREE.md','REFERENCES.bib','HANDOFF.md']
assert all((ROOT/x).is_file() for x in required)
anchors=[]
for sha,directory,files in [(A,'docs/research/midterm_noise_scale_a',['PROTOCOL.md','REPORT.md','DECISION_MEMO.md']),(BASE,'docs/research/midterm_bias_region_b',['PROTOCOL.md','MATH.md','REPORT.md','DECISION_MEMO.md']),(A,'tools/midterm_noise_scale_a',['model.py','common.py']),(BASE,'tools/midterm_bias_region_b',['regions.py','analyze.py'])]:
 for name in files:
  source=f'{sha}:{directory}/{name}';git('cat-file','-e',source);anchors.append(source)
bib=(ROOT/'REFERENCES.bib').read_text()
keys=re.findall(r'@\w+\{([^,]+),',bib);dois=re.findall(r'doi\s*=\s*\{([^}]+)\}',bib)
assert len(keys)==len(set(keys))==6
assert len(dois)==len(set(dois))==6
links=0
for p in ROOT.rglob('*.md'):
 text=p.read_text();assert text.count('$$')%2==0,p
 for target in re.findall(r'\]\(([^\s)]+)\)',text):
  if target.startswith(('https://','http://','#')):continue
  assert (p.parent/target.split('#')[0]).exists(),(p,target)
  links+=1
manifest=json.loads((ROOT/'notes/FULLTEXT_ACCESS.json').read_text())
assert len(manifest['documents'])==5
for item in manifest['documents']:assert re.fullmatch('[0-9a-f]{64}',item['sha256'])
changed=git('diff','--name-only',BASE).splitlines()+git('ls-files','--others','--exclude-standard').splitlines()
assert all(x.startswith(PREFIX) for x in changed),changed
print(json.dumps({'status':'PASS','fixed_source_paths_checked':len(anchors),'bib_entries':len(keys),'unique_dois':len(dois),'local_markdown_links_checked':links,'fulltexts_access_recorded':5,'required_deliverables':required,'only_allowed_directory_changed':True,'new_localization_runs':0,'new_simulations':0,'new_random_samples':0,'scope':'Structure/source checks only; theory reviewed separately; no solver imports or calls.'},ensure_ascii=False,indent=2))

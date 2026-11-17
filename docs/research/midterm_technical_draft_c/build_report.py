#!/usr/bin/env python3
"""Assemble Markdown and typeset saved research only. No estimator imports/calls."""
from pathlib import Path
import argparse, subprocess, shutil, os
ROOT = Path(__file__).resolve().parent
p = argparse.ArgumentParser()
p.add_argument('--pandoc', default='pandoc')
p.add_argument('--engine', default='tectonic')
p.add_argument('--assemble-only', action='store_true')
a = p.parse_args()
parts = [ROOT/'sections/00_scope.md', ROOT/'sections/01_03_methods.md', ROOT/'sections/04_05_results.md']
text = '\n\n'.join(s.read_text().rstrip() for s in parts) + '\n'
(ROOT/'TECHNICAL_DRAFT_ZH.md').write_text(text)
if a.assemble_only:
    raise SystemExit(0)
tex = ROOT/'TECHNICAL_REPORT_ZH.tex'
subprocess.run([a.pandoc, str(ROOT/'TECHNICAL_DRAFT_ZH.md'), '--from=markdown+tex_math_dollars', '--to=latex', '--standalone', '--top-level-division=section', '--template='+str(ROOT/'typeset/report-template.tex'), '--resource-path='+str(ROOT), '--output='+str(tex)], check=True, cwd=ROOT)
engine = shutil.which(a.engine) or a.engine
if 'tectonic' in Path(engine).name:
    command=[engine, str(tex), '--keep-logs']
else:
    command=[engine, '-interaction=nonstopmode', '-halt-on-error', str(tex)]
subprocess.run(command, check=True, cwd=ROOT)
if 'tectonic' not in Path(engine).name:
    subprocess.run(command, check=True, cwd=ROOT)

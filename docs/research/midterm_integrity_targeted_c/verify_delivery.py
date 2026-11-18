#!/usr/bin/env python3
"""Read-only document checks. Does not import or run any localization code."""
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = "b492c17d719013c31a93168994afe40beed5001f"
PREFIX = HERE.relative_to(ROOT).as_posix() + "/"


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True)


errors = []
required = ["README.md", "LITERATURE_MATRIX.md", "CLOSEST_WORK_COMPARISON.md",
            "THEORY_AUDIT.md", "METHOD_OPTIONS.md", "VALIDATION_PROTOCOL.md",
            "PR119_BRIDGE.md", "SEARCH_LOG.md", "REFERENCES.bib", "HANDOFF.md"]
for name in required:
    if not (HERE / name).is_file():
        errors.append("missing: " + name)

changes = git("diff", "--name-status", BASE, "--").splitlines()
untracked = git("ls-files", "--others", "--exclude-standard").splitlines()
for line in changes:
    status, path = line.split("\t", 1)
    if status != "A" or not path.startswith(PREFIX):
        errors.append("outside addition-only scope: " + line)
for path in untracked:
    if not path.startswith(PREFIX):
        errors.append("outside-scope untracked: " + path)

local_links = 0
source_links = set()
docs = sorted(HERE.rglob("*.md"))
for path in docs:
    content = path.read_text(encoding="utf-8")
    if content.count("$$") % 2:
        errors.append("unbalanced display math: " + str(path.relative_to(HERE)))
    prose = re.sub(r"\$\$[\s\S]*?\$\$|\$[^\n$]*\$", "", content)
    for target in re.findall(r"(?<!!)\[[^\]\n]+\]\(([^)\s]+)\)", prose):
        target = target.strip("<>")
        if target.startswith(("https://", "http://", "#", "mailto:")):
            continue
        target = unquote(target.split("#", 1)[0])
        if target and not (path.parent / target).exists():
            errors.append(f"broken link {path.name}: {target}")
        local_links += 1
    for sha, file, line in re.findall(
        r"https://github\.com/phyllis-TANG/uwb-coop-localization-ros1/blob/"
        r"([0-9a-f]{40})/([^\s)#]+)(?:#L(\d+))?", content
    ):
        source_links.add((sha, unquote(file), line))

for sha, path, line in sorted(source_links):
    try:
        content = git("show", f"{sha}:{path}")
        if line and not 1 <= int(line) <= len(content.splitlines()):
            errors.append(f"bad source line {sha}:{path} L{line}")
    except subprocess.CalledProcessError:
        errors.append(f"missing fixed source {sha}:{path}")

for path in HERE.rglob("*"):
    if path.is_file() and path.suffix not in {".md", ".json", ".bib", ".py"}:
        errors.append("unexpected artifact (no PDFs/source copies): " + str(path))
    if path.suffix == ".json":
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError) as exc:
            errors.append(f"invalid JSON {path}: {exc}")

bib = (HERE / "REFERENCES.bib").read_text(encoding="utf-8")
keys = re.findall(r"@\w+\{([^,]+),", bib)
if len(keys) != 7 or len(set(keys)) != len(keys):
    errors.append("bibliography must contain 7 distinct registered entries")
for key in keys:
    if f"`{key}`" not in (HERE / "LITERATURE_MATRIX.md").read_text(encoding="utf-8"):
        # Background entries are intentionally not all table rows.
        if key not in {"NicolaJaulin2020", "Rohou2018"}:
            errors.append("unmapped core/closest key: " + key)

result = {
    "base": BASE,
    "head_at_check": git("rev-parse", "HEAD").strip(),
    "markdown_files": len(docs),
    "local_links_checked": local_links,
    "fixed_repository_links_checked": len(source_links),
    "bibliography_entries": len(keys),
    "errors": errors,
    "passed": not errors,
    "limitations": ["no external website uptime guarantee", "no localization execution",
                    "no Monte Carlo or numerical method validation",
                    "formula review is recorded separately in notes/INDEPENDENT_REVIEW.md"],
}
print(json.dumps(result, ensure_ascii=False, indent=2))
sys.exit(bool(errors))

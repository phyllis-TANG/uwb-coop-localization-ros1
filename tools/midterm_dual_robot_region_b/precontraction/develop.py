"""Small development runs for both arms. A composite acceptance is pending."""
from pathlib import Path
import os
import sys
import tempfile
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import DOC, write, read
from bridge_tests import fixture
from prepare import convert
from core import solve
from geometry import evaluate
from checker_v2 import b_fast
from checker_v2.a_loader import load_a
from bounds import propose
from verify_pilot import verify, check

out = DOC / "precontraction"
cpu = min(os.sched_getaffinity(0))
os.sched_setaffinity(0, {cpu})
x = fixture()
x["noise_model"]["variance"] = ["1/625"] * 9
from bridge_tests import A
x = A.seal(x)
model = convert(x)
case = dict(model=model, a_input=x, evaluation=dict(noise=["0"] * 9, truth=["0"] * 5))
settings = dict(q="26", df=9, tolerance=[".05"] * 5, max_boxes=40, max_seconds=2)
rows = []
for contracted in (False, True):
    with tempfile.TemporaryDirectory() as td:
        record = {}
        costs = {}
        start = perf_counter()
        def timed(name, function, *args):
            before = perf_counter()
            value = function(*args)
            costs[name] = perf_counter() - before
            return value
        domain, witnesses = (timed("preprocess", propose, model, "26") if contracted
                             else (model["domain"], [None] * 8))
        timed("preprocess_check", verify, model, settings, domain, witnesses)
        inner = dict(model, domain=domain)
        tree = timed("search", solve, inner, "P4", settings, {"9":"26","8":"24"})
        b = timed("B_check", b_fast.audit, inner, "P4", settings, tree)
        regions = timed("projection", b_fast.projections, inner, tree)
        timed("projection_audit", b_fast.audit_projection, inner, tree, regions)
        if not contracted:
            _, checker = load_a(read(DOC / "checker_v2/A_SOURCE_LOCK.json"))
            cert = timed("conversion", b_fast.make_certificate, case, "P4", settings, tree, regions)
            assert timed("A_check", checker.check, x, cert)["certificate_valid"]
        ev = evaluate(model, "P4", settings, tree, case["evaluation"])
        record.update(tree=tree, domain=domain, witnesses=witnesses, b=b, regions=regions, evaluation=ev)
        path = Path(td) / "result.json.gz"
        timed("write", write, path, record)
        costs["development_total"] = perf_counter() - start
        check(read(path), case, settings)
        # Persist the development inputs and tree for separate-process replay.
        evidence = out / "development"
        write(evidence / "case.json", case)
        write(evidence / "settings.json", settings)
        arm = "contracted" if contracted else "original"
        write(evidence / (arm + ".json.gz"), record)
        if contracted:
            assert all(w is not None for w in witnesses)
            invalid = [list(interval) for interval in domain]
            invalid[0][0] = '0'
            try:
                verify(model, settings, invalid, witnesses)
            except AssertionError:
                pass
            else:
                raise ValueError("Inward bound was accepted")
        rows.append(dict(contracted=contracted, cpu=cpu, costs=costs, domain=domain,
                         witnesses=witnesses, nodes=len(tree["nodes"]), independent_B="PASS",
                         A_status="MISSING_COMPOSITE_READY" if contracted else "PASS_V2"))
write(out / "DEVELOPMENT.json", rows)

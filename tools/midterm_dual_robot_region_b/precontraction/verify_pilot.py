"""Verify direction witnesses by squaring rational inequalities, then audit the tree."""
import sys
from fractions import Fraction as F
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import read
from certificate import audit
from geometry import projections, evaluate


def verify(model, settings, domain, witnesses):
    assert len(domain) == 4 and len(witnesses) == 8
    for axis, (lo, hi) in enumerate(domain):
        old_lo, old_hi = map(F, model["domain"][axis])
        assert old_lo <= F(lo) <= F(hi) <= old_hi
        for side, endpoint in enumerate((lo, hi)):
            witness = witnesses[2 * axis + side]
            if witness is None:
                assert F(endpoint) == (old_lo, old_hi)[side]
                continue
            assert witness in range(4 * (axis // 2), 4 * (axis // 2 + 1))
            center = F(model["anchors"][witness % 4][axis % 2])
            radius = (2 * side - 1) * (F(endpoint) - center)
            slack = radius - F(model["observations"][witness][1])
            assert radius >= 0 and slack >= 0
            assert slack**2 >= F(settings["q"]) * F(model["R"][witness][witness])


def check(record, case, settings):
    verify(case["model"], settings, record["domain"], record["witnesses"])
    inner = dict(case["model"], domain=record["domain"])
    tree = record["tree"]
    assert audit(inner, "P4", settings, tree) == record["b"]
    assert projections(inner, tree) == record["regions"]
    assert evaluate(case["model"], "P4", settings, tree, case["evaluation"]) == record["evaluation"]


if __name__ == "__main__":
    record, case, settings = map(read, sys.argv[1:])
    check(record, case, settings)

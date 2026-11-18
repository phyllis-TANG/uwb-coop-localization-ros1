"""Reproduce registered outer radii without writing to the previous round."""
import csv
import sys
from pathlib import Path
from unittest.mock import patch

BASE=Path(__file__).resolve().parents[2]
import witness
import check
import figure

sys.path.append(str(BASE/'tools/ground_b_round2'))
import resolution


def compare_table(name, rows):
    with (BASE/'docs/research/ground_b_round2/evaluation'/name).open() as stream:
        old=list(csv.DictReader(stream))
    fresh=[{k:'' if v is None else str(v) for k,v in row.items()} for row in rows]
    if fresh!=old:
        raise ValueError('Recomputed outer radii differ from #149')


if __name__=='__main__':
    with patch.object(resolution,'save',compare_table):
        resolution.compare()
    witness.main()
    check.main()
    figure.main()

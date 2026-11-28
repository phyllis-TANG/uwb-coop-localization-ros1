"""Read-only stage diagnosis of the joint survey + validated links arm."""
import csv
import gzip
import json
from pathlib import Path
from statistics import NormalDist
import sys
import tempfile

import numpy as np

from development import OUT, frozen

K = NormalDist().inv_cdf(1 - .005 / 2)


def diagnose():
    with gzip.open(OUT / "nominal_survey_links.json.gz", "rt") as stream:
        first, second = json.load(stream)[:2]
    if [(r["t"], r["action"]) for r in (first, second)] != [(1, "ACCEPT"), (2, "ACCEPT")]:
        raise ValueError("requires two consecutive accepted epochs")
    with tempfile.TemporaryDirectory() as directory:
        q = frozen(Path(directory)).ref.Q.diagonal()[:4]
    for i in range(2):
        axes = slice(2*i, 2*i+2)
        var1, var2 = [np.array(e["covariance_diag"][axes]) for e in (first, second)]
        bias1, bias2 = [np.array(e["cars"][i]["history_B"]) for e in (first, second)]
        for stage, var, bias, archive in [
            ("t1_updated", var1, bias1, first),
            ("t2_predicted", var1 + q[axes], bias1, None),
            ("t2_updated", var2, bias2, second),
        ]:
            gaussian = K * np.sqrt(var)
            radius = np.linalg.norm(gaussian + bias)
            if archive is not None:
                car = archive["cars"][i]
                np.testing.assert_allclose(np.sqrt(var), car["sigma"], atol=1e-14, rtol=0)
                np.testing.assert_allclose(radius, car["hcpl"]["history"], atol=1e-14, rtol=0)
            yield [i+1, stage, *var, *bias, *gaussian, np.linalg.norm(gaussian), radius]


if __name__ == "__main__":
    rows = list(diagnose())
    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(["car", "stage", "var_x_m2", "var_y_m2", "history_x_m", "history_y_m",
                     "gaussian_x_m", "gaussian_y_m", "gaussian_only_radius_m", "radius_m"])
    writer.writerows(rows)

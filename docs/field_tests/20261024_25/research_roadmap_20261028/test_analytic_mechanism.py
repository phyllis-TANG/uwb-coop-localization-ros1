"""Analytic optimality and scope checks, using Python standard library only."""

import unittest

from analytic_mechanism import (build_report, equal_precision_box, gradient,
                                objective, unconstrained)


class AnalyticChecks(unittest.TestCase):
    def test_stationary_and_positive_definite_quadratic(self):
        for a, b in ((1., 1.), (4., 1.), (.25, 3.)):
            for gamma in (0., 1., 25., 1000.):
                u, v = unconstrained(a, b, gamma, .30, -.05)
                gu, gv = gradient(u, v, a, b, gamma, .30, -.05)
                self.assertLess(abs(gu), 1e-10)
                self.assertLess(abs(gv), 1e-10)
                self.assertGreater((a+gamma)*(b+gamma)-gamma**2, 0)
                # A nonzero perturbation must increase this strictly convex cost.
                self.assertGreater(objective(u+.01, v-.02, a, b, gamma, .30, -.05),
                                   objective(u, v, a, b, gamma, .30, -.05))

    def test_peer_off_is_independent(self):
        self.assertEqual(unconstrained(4., 1., 0., .30, -.05), (.30, -.05))

    def test_common_bias_cannot_be_seen_by_relative_measurement(self):
        for gamma in (0., 1., 25., 1000.):
            u, v = unconstrained(4., 1., gamma, .30, .30)
            self.assertAlmostEqual(u, .30)
            self.assertAlmostEqual(v, .30)

    def test_role_swap_and_translation(self):
        first = unconstrained(4., 1., 25., .30, -.05)
        swapped = unconstrained(1., 4., 25., -.05, .30)
        shifted = unconstrained(4., 1., 25., 1.30, .95)
        for x, y in zip(first, reversed(swapped)):
            self.assertAlmostEqual(x, y)
        for x, y in zip(first, shifted):
            self.assertAlmostEqual(x+1., y)

    def test_box_optimum_satisfies_kkt_and_budget(self):
        # Convex differentiable objective + box: coordinate KKT is sufficient.
        # Covers both signs, active/inactive bounds, and the degenerate zero box.
        for z1, z2 in ((.30, 0.), (-.30, 0.), (0., .30), (.30, .30)):
            for gamma in (0., 1., 25.):
                for cap in (0., .04, .50):
                    point = equal_precision_box(1., gamma, z1, z2, cap)
                    grad = gradient(*point, 1., 1., gamma, z1, z2)
                    for x, center, g in zip(point, (z1, z2), grad):
                        self.assertLessEqual(abs(x-center), cap+1e-12)
                        if cap == 0:
                            continue
                        if abs(x-(center-cap)) < 1e-12:
                            self.assertGreaterEqual(g, -1e-10)
                        elif abs(x-(center+cap)) < 1e-12:
                            self.assertLessEqual(g, 1e-10)
                        else:
                            self.assertLess(abs(g), 1e-10)

    def test_report_exposes_clipping_equivalence(self):
        report = build_report()
        self.assertEqual(report["case_count"], 9)
        checked = [x for x in report["cases"] if "equal_precision_box" in x]
        self.assertEqual(len(checked), 8)
        self.assertTrue(all(x["box_equals_post_clip_within_1e_12"] for x in checked))
        for row in checked:
            for i in (1, 2):
                bounded = row["equal_precision_box"]
                independent = row["independent"]
                self.assertLessEqual(abs(bounded[f"car{i}_abs_error_m"]-independent[f"car{i}_abs_error_m"]),
                                     report["budget_m"]+1e-12)

    def test_invalid_weights_and_budgets(self):
        for a, b, gamma in ((0., 1., 1.), (1., -1., 1.), (1., 1., -1.)):
            with self.assertRaises(ValueError):
                unconstrained(a, b, gamma, .3, 0.)
        for cap in (-.1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                equal_precision_box(1., 1., .3, 0., cap)


if __name__ == "__main__":
    unittest.main()

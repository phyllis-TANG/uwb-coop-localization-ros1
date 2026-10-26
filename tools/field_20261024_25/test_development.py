import unittest

import development


class DevelopmentTests(unittest.TestCase):
    def test_peer_comparison_never_reads_future(self):
        left=[(100,2.),(200,3.),(300,4.)]
        right=[(110,99.),(180,1.),(400,999.)]
        rows=development.peer_asof(left,right,30)
        self.assertEqual(rows,[{"receive_epoch_ns":200,"other_receive_epoch_ns":180,
                                "age_ns":20,"car1_minus_car2_m":2.}])

    def test_no_match_is_unknown_not_zero(self):
        self.assertEqual(development.peer_asof([(100,2.)],[(0,2.)],30),[])

    def test_holdout_gate_is_explicit(self):
        development.validate_trials(["T08","T10","T12","T14"])
        with self.assertRaisesRegex(ValueError,"development"):
            development.validate_trials(["T08","T09"])

    def test_coverage_denominator_is_frames_not_nominal_frequency(self):
        report=development.link_summary([(0,1.,-80.,-75.),(20,2.,None,None)],4)
        self.assertEqual(report["valid_frame_fraction"],.5)
        self.assertEqual(report["fp_rssi_db"]["n"],1)
        self.assertEqual(report["successive_range_delta_m"]["max"],1.)

    def test_batching_requires_header_progress(self):
        config={"receipt_batch_max_gap_ns":1,"header_progress_min_ns":10}
        d=development.arrival_summary([(0,100),(1,120),(2,120),(100,140)],config)
        self.assertEqual(d["batch_progress_pairs"],1)
        self.assertEqual(d["large_receipt_small_header_pairs"],0)


if __name__=="__main__":unittest.main()

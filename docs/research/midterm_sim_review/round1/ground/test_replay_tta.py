import unittest
from replay_tta import classify, excursions

def row(status, error=""):
    return {"status": status, "error_m": str(error)}

class TimingTest(unittest.TestCase):
    def test_gap_alarm_and_recovery_boundary(self):
        rows = [row("AVAILABLE", .11), row("EXPIRED"), row("AVAILABLE", .12),
                row("ALARM", .15), row("AVAILABLE", .1), row("AVAILABLE", .13)]
        event, censored = excursions(rows)
        self.assertEqual((event["start"], event["alarm"], event["end"], event["exposed"]), (0, 3, 4, 2))
        self.assertEqual(classify(event, 1, rows), "no_position_at_deadline")
        self.assertEqual(classify(event, 2, rows), "exceed_available_at_deadline")
        self.assertEqual(classify(event, 3, rows), "timely_alarm")
        self.assertEqual(classify(censored, 6, rows), "right_censored_before_deadline")

    def test_alarm_already_present_and_short_recovery(self):
        rows = [row("ALARM", .15), row("AVAILABLE", .1), row("NO_DECISION", .22), row("AVAILABLE", .09)]
        alarmed, recovered = excursions(rows)
        self.assertEqual(classify(alarmed, 0, rows), "timely_alarm")
        self.assertEqual(classify(recovered, 2, rows), "exceed_withheld_at_deadline")
        self.assertEqual(classify(recovered, 3, rows), "recovered_before_or_at_deadline")

if __name__ == "__main__":
    unittest.main()

import copy
import json
from pathlib import Path
import unittest

import replay
from test_model import ORIGIN, odom
import verify_outputs


class IndependentVerificationTests(unittest.TestCase):
    def fixture(self):
        field=json.loads(Path(__file__).with_name("field_config.json").read_text())
        events=[odom(index=0),odom("car2",index=1)]
        rows=[r for rr,d,e in replay.replay_events(events,field,"T08",ORIGIN,ORIGIN+100_000_000) for r in rr]
        return rows,[e["row"] for e in events]

    def test_verification_agrees_and_detects_altered_position(self):
        rows,source=self.fixture()
        result=verify_outputs.verify_rows(rows,source,ORIGIN)
        self.assertEqual(result["rows"],12)
        self.assertEqual(result["blocked_rows_verified"],8)
        for row in rows:
            if row["method_id"]=="odom_only" and row["valid"]:
                row["x_m"] += .001
                break
        with self.assertRaisesRegex(AssertionError,"source x"):
            verify_outputs.verify_rows(rows,source,ORIGIN)

    def test_fabricated_room_state_is_rejected(self):
        rows,source=self.fixture()
        rows[2]["x_m"]=0.
        with self.assertRaisesRegex(AssertionError,"fabricated"):
            verify_outputs.verify_rows(rows,source,ORIGIN)


if __name__=="__main__":unittest.main()

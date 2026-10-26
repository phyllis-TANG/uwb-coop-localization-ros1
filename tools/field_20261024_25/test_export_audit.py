"""Independent row-signature audit detects numeric and one-nanosecond corruption."""
import csv
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

import audit_exports as check
import normalize
from test_audit_bags import encode_fields, record


def string(value):
    b=value.encode()
    return struct.pack("<I",len(b))+b


class ExportAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name)
        stamp=1792925285431466217
        definition="Header header\nstring tag_id\nRange[] ranges\n===\nMSG: std_msgs/Header\nuint32 seq\ntime stamp\nstring frame_id\n===\nMSG: test/Range\nstring anchor_id\nfloat64 range\nfloat64 quality\n"
        connection=record([("op",b"\x07"),("conn",struct.pack("<I",0)),("topic",b"/car2/uwb/ranges")],
            encode_fields([("type",b"test/Ranges"),("md5sum",b"fixture"),("message_definition",definition.encode())]))
        data=struct.pack("<III",7,stamp//10**9,stamp%10**9)+string("car2/uwb")+string("node_0")+struct.pack("<I",1)+string("node_1")+struct.pack("<dd",1.25,float("nan"))
        message=record([("op",b"\x02"),("conn",struct.pack("<I",0)),("time",struct.pack("<II",stamp//10**9,stamp%10**9))],data)
        path=root/"fixture.bag"
        path.write_bytes(b"#ROSBAG V2.0\n"+connection+message)
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        row={"id":"T08","relative_path":"fixture.bag","sha256":digest,"first_bag_receive_epoch_ns":stamp}
        self.manifest={"formal_bags":[row]}
        self.planned=[(row,path,digest)]
        tables,_=normalize.convert([(0,stamp,"/car2/uwb/ranges",{"header":{"seq":7,"stamp":{"secs":stamp//10**9,"nsecs":stamp%10**9},"frame_id":"car2/uwb"},
            "tag_id":"node_0","ranges":[{"anchor_id":"node_1","range":1.25,"quality":float("nan")} ]})],"T08",digest,stamp)
        self.out=root/"normalized"
        self.out.mkdir()
        for kind in normalize.COLUMNS:normalize.write_table(self.out/(kind+".csv"),tables[kind],normalize.COLUMNS[kind])

    def test_independent_decode_agrees_with_exported_entries_and_frames(self):
        expected,ec=check.expected_signatures(self.planned)
        actual,ac=check.actual_signatures(self.out,self.manifest)
        self.assertEqual(ec,ac)
        self.assertEqual(ec[("T08","ranges")],1)
        for key in ec:self.assertEqual(expected[key].hexdigest(),actual[key].hexdigest())

    def change(self,key,value):
        path=self.out/"ranges.csv"
        with path.open(newline="") as f:
            reader=csv.DictReader(f)
            fields=reader.fieldnames
            rows=list(reader)
        rows[0][key]=value
        with path.open("w",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=fields)
            writer.writeheader();writer.writerows(rows)

    def test_altered_range_does_not_pass_signature(self):
        self.change("range_m","1.26")
        expected,_=check.expected_signatures(self.planned)
        actual,_=check.actual_signatures(self.out,self.manifest)
        self.assertNotEqual(expected[("T08","ranges")].hexdigest(),actual[("T08","ranges")].hexdigest())

    def test_one_ns_shift_is_detected(self):
        self.change("receive_epoch_ns","1792925285431466218")
        with self.assertRaisesRegex(ValueError,"arrival time arithmetic"):
            check.actual_signatures(self.out,self.manifest)


if __name__=="__main__":unittest.main()

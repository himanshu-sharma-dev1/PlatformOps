import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from contract import map_aviat_row, validate_mapped_event


ROOT = Path(__file__).resolve().parents[2]


class MappedContractTests(unittest.TestCase):
    def test_mapping_is_stable_and_keeps_webhook_aliases(self):
        row = {
            "Event": "Ethernet port link down",
            "Object": "L1LA1",
            "Site": "UEMWBSNA01",
            "Raised": "2026-08-14T10:00:00Z",
            "Severity": "Major",
            "State": "Active",
            "Event ID": "1603",
        }
        first = map_aviat_row(row, source_file="alarm.csv", source_row=1, ingested_at="2026-08-14T10:00:01Z")
        second = map_aviat_row(row, source_file="alarm.csv", source_row=1, ingested_at="2026-08-14T10:00:01Z")
        self.assertEqual(first, second)
        self.assertEqual(first["alarm_key"], "aviat:UEMWBSNA01:1603")
        self.assertEqual(first["canonical_category"], "LINK_DOWN")
        self.assertEqual(first["AlarmID"], "1603")
        self.assertEqual(first["Raised"], "2026-08-14T10:00:00Z")
        self.assertEqual(validate_mapped_event(first), [])

    def test_duplicate_delivery_metadata_does_not_change_identity(self):
        row = {"Event": "RSL low", "Site": "S1", "Raised": "2026-08-14 10:00:00", "Severity": "Critical", "State": "Active", "Event ID": "A-1"}
        one = map_aviat_row(row, source_file="one.csv", source_row=1, ingested_at="2026-08-14T10:01:00Z")
        two = map_aviat_row(row, source_file="two.csv", source_row=99, ingested_at="2026-08-14T10:02:00Z")
        self.assertEqual(one["event_id"], two["event_id"])
        self.assertEqual(one["alarm_key"], two["alarm_key"])

    def test_schema_and_example_are_json_and_example_is_valid(self):
        schema = json.loads((ROOT / "contracts" / "noc_alarm_mapped_v1.schema.json").read_text())
        example = json.loads((ROOT / "contracts" / "noc_alarm_mapped_v1.example.json").read_text())
        self.assertEqual(schema["$id"], "https://cplatform.local/contracts/noc-alarm-mapped.v1.schema.json")
        self.assertEqual(validate_mapped_event(example), [])


if __name__ == "__main__":
    unittest.main()

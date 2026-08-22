from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "cPlatform"))

from cPlatformIO.src.demo_control_plane import (  # noqa: E402
    NORMALIZED_ALARM_TOPIC,
    RAW_ALARM_TOPIC,
    build_stream_contract,
)


class HttpV2ContractTests(unittest.TestCase):
    def _payload(self, **extra):
        payload = {
            "stream_id": "agenticnoc_aviat",
            "source_type": "LOCAL",
            "local_path": "/data/incoming",
            "local_file_pattern": "*alarm*.csv",
            "vendor": "aviat",
            "replay_mode": "one_shot",
            "topic": NORMALIZED_ALARM_TOPIC,
        }
        payload.update(extra)
        return payload

    def test_http_v2_uses_normalized_topic_as_primary(self):
        contract = build_stream_contract(self._payload())

        self.assertEqual(contract["kafka"]["topic"], NORMALIZED_ALARM_TOPIC)
        self.assertEqual(contract["kafka"]["raw_topic"], RAW_ALARM_TOPIC)
        self.assertFalse(contract["nifi"]["publishes_raw_row_json"])
        self.assertTrue(contract["nifi"]["publishes_canonical_alarm_json"])

    def test_legacy_raw_request_is_accepted_and_canonicalized(self):
        contract = build_stream_contract(self._payload(topic=RAW_ALARM_TOPIC))

        self.assertEqual(contract["kafka"]["topic"], NORMALIZED_ALARM_TOPIC)

    def test_unknown_topic_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "HTTP-v2"):
            build_stream_contract(self._payload(topic="noc.unknown.v1"))


if __name__ == "__main__":
    unittest.main()

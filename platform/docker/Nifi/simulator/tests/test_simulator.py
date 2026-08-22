import csv
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from simulator import Handler, Simulator, SimulatorConfig, _csv_payload


class SimulatorTests(unittest.TestCase):
    def test_csv_payload_drops_unnamed_trailing_vendor_column(self):
        payload = _csv_payload(
            ["Event", "Site", "Device Cleared", ""],
            ["LINK_DOWN", "SITE-1", "-", ""],
        ).decode("utf-8")
        self.assertEqual(payload, "Event,Site,Device Cleared\nLINK_DOWN,SITE-1,-\n")

    def test_configure_endpoint_sets_cycle_and_sender_metadata(self):
        config = SimulatorConfig(
            target_url="http://nifi:9080/aviat",
            rate=1,
            continuous=True,
            stream_id="initial-stream",
        )
        simulator = Simulator(config)
        Handler.simulator = simulator
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            request = Request(
                f"http://127.0.0.1:{server.server_port}/configure",
                data=json.dumps(
                    {
                        "cycle_id": "cycle-9",
                        "stream_id": "stream-7",
                        "rate": 25,
                        "continuous": False,
                        "input_dir": "/data/replay",
                        "archive_dir": "/data/archive",
                        "target_url": "http://nifi:9080/aviat",
                    }
                ).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=2) as response:
                body = json.loads(response.read().decode("utf-8"))
            self.assertEqual(response.status, 200)
            self.assertTrue(body["configured"])
            self.assertEqual(body["cycle_id"], "cycle-9")
            self.assertEqual(body["stream_id"], "stream-7")
            self.assertEqual(body["rate"], 25.0)
            self.assertFalse(body["continuous"])
            repeat = Request(
                f"http://127.0.0.1:{server.server_port}/configure",
                data=request.data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(repeat, timeout=2) as response:
                repeated_body = json.loads(response.read().decode("utf-8"))
            self.assertEqual(response.status, 200)
            self.assertEqual(repeated_body["cycle_id"], body["cycle_id"])
            self.assertEqual(repeated_body["stream_id"], body["stream_id"])

            class FakeResponse:
                status = 202

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return False

                @staticmethod
                def read():
                    return b""

            with patch("simulator.urlopen", return_value=FakeResponse()) as opened:
                self.assertEqual(
                    simulator._default_sender(
                        b"Event\nrow\n", "alarm.csv", 1, "http://nifi:9080/aviat"
                    ),
                    202,
                )
            sent_request = opened.call_args.args[0]
            headers = {key.lower(): value for key, value in sent_request.header_items()}
            self.assertEqual(headers["x-replay-cycle-id"], "cycle-9")
            self.assertEqual(headers["x-replay-sequence"], "1")
            self.assertEqual(headers["x-stream-id"], "stream-7")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_one_row_per_request_and_lifecycle(self):
        sent = []

        def sender(payload, source_file, row_number, target_url):
            sent.append((payload, source_file, row_number, target_url))
            return 200

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "alarm.csv"
            source.write_text(
                "Report generated\nReport type: alarm\nEvent,Object,Site,Raised,Severity,State,Event ID\n"
                "Link down,L1,S1,2026-08-14T10:00:00Z,Major,Active,A1\n"
                "RSL low,L2,S1,2026-08-14T10:00:01Z,Critical,Active,A2\n",
                encoding="utf-8",
            )
            config = SimulatorConfig(
                input_dir=root,
                archive_dir=root / "sent",
                target_url="http://nifi:9080/aviat",
                rate=1000,
                continuous=False,
                file_delay_seconds=0,
                idle_delay_seconds=0,
            )
            simulator = Simulator(config, sender=sender)
            simulator.start()
            deadline = time.monotonic() + 2
            while simulator.status()["state"] != "stopped" and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertEqual(len(sent), 2)
            self.assertEqual([item[2] for item in sent], [1, 2])
            self.assertEqual([item[1] for item in sent], ["alarm.csv", "alarm.csv"])
            self.assertEqual(simulator.status()["rows_sent"], 2)
            for payload, _, _, _ in sent:
                rows = list(csv.reader(io.StringIO(payload.decode("utf-8"))))
                self.assertEqual(len(rows), 2)
                self.assertEqual(len(rows[0]), len(rows[1]))

            simulator.pause()
            self.assertEqual(simulator.status()["state"], "stopped")

    def test_non_alarm_files_are_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "performance.csv").write_text("ignored", encoding="utf-8")
            simulator = Simulator(SimulatorConfig(input_dir=root, rate=1, continuous=False, idle_delay_seconds=0))
            simulator.start()
            deadline = time.monotonic() + 2
            while simulator.status()["state"] != "stopped" and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertEqual(simulator.status()["rows_sent"], 0)
            self.assertEqual(simulator.status()["rows_failed"], 0)


if __name__ == "__main__":
    unittest.main()

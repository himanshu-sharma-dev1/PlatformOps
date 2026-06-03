from __future__ import annotations

import os
import time
from datetime import datetime


LOG_PATH = os.environ.get("LOG_PATH", "/var/log/platformops/worker.log")


def main() -> None:
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    while True:
        line = f"{datetime.utcnow().isoformat()}Z INFO worker heartbeat queue=default\n"
        print(line, end="", flush=True)
        with open(LOG_PATH, "a", encoding="utf-8") as handle:
            handle.write(line)
        time.sleep(5)


if __name__ == "__main__":
    main()

"""
Standalone healthcheck script.
Run via Task Scheduler every 5 minutes to verify service is alive.
If service is down, log an alert (extend with email/Telegram later).
"""

import sys
import requests
from datetime import datetime

URL = "http://localhost:8000/health"
LOG_FILE = "healthcheck.log"


def check():
    try:
        r = requests.get(URL, timeout=5)
        data = r.json()
        status = data.get("status", "unknown")
        uptime = data.get("uptime_seconds", 0)
        reqs = data.get("total_requests", 0)

        msg = (f"{datetime.now().isoformat()} | "
               f"status={status} | uptime={uptime:.0f}s | "
               f"requests={reqs}")

        if status != "ok":
            msg += " | WARNING: service degraded"

        print(msg)
        with open(LOG_FILE, "a") as f:
            f.write(msg + "\n")

        return 0 if status == "ok" else 1

    except requests.exceptions.ConnectionError:
        msg = f"{datetime.now().isoformat()} | ERROR: service unreachable"
        print(msg)
        with open(LOG_FILE, "a") as f:
            f.write(msg + "\n")
        return 2

    except Exception as e:
        msg = f"{datetime.now().isoformat()} | ERROR: {e}"
        print(msg)
        with open(LOG_FILE, "a") as f:
            f.write(msg + "\n")
        return 2


if __name__ == "__main__":
    sys.exit(check())

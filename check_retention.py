"""
Quick retention check: query a specific date's inverterDay data and report
whether it's still available. Useful for testing how far back SolisCloud
keeps daily records.

Usage:
    python check_retention.py                # checks yesterday
    python check_retention.py 2026-08-01      # checks a specific date
"""

import os
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from solis_auth import solis_post

load_dotenv()

KEY_ID = os.environ.get("SOLIS_KEY_ID")
KEY_SECRET = os.environ.get("SOLIS_KEY_SECRET")
INVERTER_ID = os.environ.get("SOLIS_INVERTER_ID")
INVERTER_SN = os.environ.get("SOLIS_INVERTER_SN")

missing = [k for k, v in {
    "SOLIS_KEY_ID": KEY_ID,
    "SOLIS_KEY_SECRET": KEY_SECRET,
    "SOLIS_INVERTER_ID": INVERTER_ID,
    "SOLIS_INVERTER_SN": INVERTER_SN,
}.items() if not v]
if missing:
    sys.exit(f"Missing .env values: {', '.join(missing)}")

def timezone_offset_for(query_date: str) -> int:
    dt = datetime.strptime(query_date, "%Y-%m-%d").replace(
        tzinfo=ZoneInfo("Europe/London")
    )
    return int(dt.utcoffset().total_seconds() / 3600)


if len(sys.argv) > 1:
    check_date = sys.argv[1]
else:
    check_date = (date.today() - timedelta(days=1)).isoformat()


def main():
    payload = {
        "id": int(INVERTER_ID),
        "sn": INVERTER_SN,
        "money": "GBP",
        "time": check_date,
        "timeZone": timezone_offset_for(check_date),
    }
    print(f"Checking {check_date}...")
    result = solis_post(KEY_ID, KEY_SECRET, "/v1/api/inverterDay", payload)

    code = str(result.get("code"))
    if code != "0":
        print(f"SolisCloud error {code}: {result.get('msg')}")
        return

    points = result.get("data", [])
    if not points:
        print(f"RETENTION LIMIT (or no data ever existed) for {check_date}: "
              f"empty response.")
        return

    final_etoday = points[-1].get("eToday")
    print(f"STILL AVAILABLE: {len(points)} points for {check_date}, "
          f"final eToday = {final_etoday} kWh")


if __name__ == "__main__":
    main()

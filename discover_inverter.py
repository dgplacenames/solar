"""
Run this once to find your inverter's ID and SN, which inverterDetail
needs on every subsequent poll. Fill SOLIS_INVERTER_ID / SOLIS_INVERTER_SN
into your .env once you have them.

Usage:
    python discover_inverter.py
"""

import os
import sys

from dotenv import load_dotenv

from solis_auth import solis_post

load_dotenv()

KEY_ID = os.environ.get("SOLIS_KEY_ID")
KEY_SECRET = os.environ.get("SOLIS_KEY_SECRET")

if not KEY_ID or not KEY_SECRET:
    sys.exit("Set SOLIS_KEY_ID and SOLIS_KEY_SECRET in .env first.")


def main():
    payload = {"pageNo": 1, "pageSize": 20}
    result = solis_post(KEY_ID, KEY_SECRET, "/v1/api/inverterList", payload)

    if result.get("code") != "0" and result.get("code") != 0:
        print("SolisCloud returned an error:")
        print(result)
        return

    records = result.get("data", {}).get("page", {}).get("records", [])
    if not records:
        print("No inverters found on this account. Full response:")
        print(result)
        return

    print(f"Found {len(records)} inverter(s):\n")
    for inv in records:
        print(f"  Name       : {inv.get('name')}")
        print(f"  Inverter ID: {inv.get('id')}")
        print(f"  Serial (SN): {inv.get('sn')}")
        print(f"  Station ID : {inv.get('stationId')}")
        print(f"  State      : {inv.get('state')}  (1=online, 2=offline, 3=alarm)")
        print()

    print("Copy the Inverter ID and SN for your inverter into .env as")
    print("SOLIS_INVERTER_ID and SOLIS_INVERTER_SN.")


if __name__ == "__main__":
    main()

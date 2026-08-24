"""
SolisCloud API request signing.

Auth scheme per SolisCloud Platform API Document V2.0.2, section 2:

  Authorization = "API " + KeyId + ":" + Sign
  Sign = base64(HMAC-SHA1(KeySecret,
            VERB + "\n" + Content-MD5 + "\n" + Content-Type + "\n"
            + Date + "\n" + CanonicalizedResource))

All requests are POST with a JSON body. Content-MD5 is the base64-encoded
MD5 digest of the exact request body bytes (empty string if body is empty).
Date must be RFC 1123 / GMT, e.g. "Wed, 10 Jul 2019 07:23:22 GMT".
"""

import base64
import hashlib
import hmac
import json
import time
from email.utils import formatdate

import requests

BASE_URL = "https://www.soliscloud.com:13333"


def _content_md5(body_bytes: bytes) -> str:
    digest = hashlib.md5(body_bytes).digest()
    return base64.b64encode(digest).decode("utf-8")


def _gmt_date() -> str:
    # formatdate(usegmt=True) gives RFC 1123 format, which is what Solis wants
    return formatdate(timeval=None, localtime=False, usegmt=True)


def _sign(key_secret: str, verb: str, content_md5: str, content_type: str,
          date: str, resource: str) -> str:
    string_to_sign = f"{verb}\n{content_md5}\n{content_type}\n{date}\n{resource}"
    digest = hmac.new(
        key_secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


def solis_post(key_id: str, key_secret: str, resource: str, payload: dict,
                timeout: int = 30, retries: int = 3, backoff_seconds: int = 10) -> dict:
    """POST to a SolisCloud endpoint. Retries on timeout/502/503/504."""
    content_type = "application/json"
    body_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    content_md5 = _content_md5(body_bytes)

    last_error = None
    for attempt in range(1, retries + 2):  # e.g. retries=3 -> 4 total tries
        # Date/signature must be freshly generated per attempt: Solis
        # rejects requests where Date is more than ~15 min from server time,
        # and a stale Date from a slow/waited first attempt could trip that.
        date = _gmt_date()
        sign = _sign(key_secret, "POST", content_md5, content_type, date, resource)
        headers = {
            "Content-MD5": content_md5,
            "Content-Type": content_type,
            "Date": date,
            "Authorization": f"API {key_id}:{sign}",
        }

        try:
            resp = requests.post(
                BASE_URL + resource,
                data=body_bytes,
                headers=headers,
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ReadTimeout as e:
            last_error = e
            print(f"  [attempt {attempt}] Read timeout.")
        except requests.exceptions.HTTPError as e:
            last_error = e
            status = e.response.status_code if e.response is not None else None
            print(f"  [attempt {attempt}] HTTP error {status}.")
            if status not in (502, 503, 504):
                # Not a transient gateway issue - no point retrying (e.g. 401/403)
                raise
        except requests.exceptions.RequestException as e:
            last_error = e
            print(f"  [attempt {attempt}] Request error: {e}")

        if attempt <= retries:
            print(f"  Waiting {backoff_seconds}s before retry...")
            time.sleep(backoff_seconds)
        else:
            print("  Giving up.")

    raise last_error

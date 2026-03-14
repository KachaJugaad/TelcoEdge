#!/usr/bin/env python3
"""Monitor tool: verify MSC GeoMet weather API is reachable.

GET https://api.weather.gc.ca/collections — expects HTTP 200.
NO API KEY NEEDED — MSC GeoMet is anonymous and free (Government of Canada).

Standalone: python tools/weather_api_check.py
Exit 0 = PASS, Exit 1 = FAIL
"""
import sys
import time
import urllib.request
import urllib.error

URL = "https://api.weather.gc.ca/collections"
TIMEOUT_SECONDS = 10
MAX_RETRIES = 3
BACKOFF_BASE = 3  # 3-second exponential backoff per PROJECT.md


def check_weather_api():
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(URL, method="GET")
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
                status = resp.getcode()
                if status == 200:
                    print(f"PASS: GET {URL} returned HTTP {status} (no API key, anonymous)")
                    return True
                else:
                    print(f"FAIL: GET {URL} returned HTTP {status} (expected 200)")
                    return False
        except urllib.error.HTTPError as e:
            code = e.code
            if code in (429, 500, 502, 503, 504) and attempt < MAX_RETRIES:
                wait = BACKOFF_BASE ** attempt
                print(f"WARN: HTTP {code} on attempt {attempt}/{MAX_RETRIES}, retrying in {wait}s...")
                time.sleep(wait)
                continue
            print(f"FAIL: GET {URL} returned HTTP {code}")
            return False
        except (urllib.error.URLError, OSError) as e:
            if attempt < MAX_RETRIES:
                wait = BACKOFF_BASE ** attempt
                print(f"WARN: connection error on attempt {attempt}/{MAX_RETRIES}: {e}, retrying in {wait}s...")
                time.sleep(wait)
                continue
            print(f"FAIL: GET {URL} unreachable — {e}")
            print("Action: log to .canedge/incidents/, use cached weather data")
            return False

    print(f"FAIL: GET {URL} failed after {MAX_RETRIES} attempts")
    return False


def main():
    ok = check_weather_api()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

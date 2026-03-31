#!/usr/bin/env python3
"""
process_site_extract.py — Extract Big 3 carrier cell sites from ISED Site Data Extract.

This is the better dataset for cellular towers (vs TAFL which is mostly microwave).
The Site_Data_Extract.csv has proper column headers and good lat/lon coverage for
all three major Canadian carriers.

Source: https://www.ic.gc.ca/engineering/SMS_TAFL_Files/Site_Data_Extract.zip
License: Open Government Licence - Canada
"""

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CARRIER_PATTERNS = {
    "bell": {
        "patterns": ["Bell Mobility", "Bell MTS", "Bell Canada"],
        "display": "Bell",
        "color": "#0066A4",
        "file": "towers_bell.json",
    },
    "rogers": {
        "patterns": ["Rogers Communications", "FIDO SOLUTIONS"],
        "display": "Rogers",
        "color": "#DA291C",
        "file": "towers_rogers.json",
    },
    "telus": {
        "patterns": ["TELUS Communications", "Telus  Regulatory"],
        "display": "TELUS",
        "color": "#4B286D",
        "file": "towers_telus.json",
    },
}

# Canadian mobile frequency bands (MHz)
MOBILE_BANDS = [
    (694, 756),     # Band 12/17/29 — 700 MHz (rural LTE)
    (758, 803),     # Band 13/14 — 700 MHz upper
    (824, 894),     # Band 5/26 — 850 MHz
    (1710, 1780),   # Band 3/4/66 — AWS 1700 MHz
    (1850, 1990),   # Band 2/25 — PCS 1900 MHz
    (2110, 2200),   # Band 1/4/66 — 2100 MHz + AWS-3
    (2496, 2690),   # Band 7/41 — 2600 MHz
    (3450, 3980),   # n77/n78 — 3500+ MHz (5G)
]


def is_mobile_freq(freq_mhz: float) -> bool:
    """Return True if frequency is in a Canadian mobile band."""
    return any(low <= freq_mhz <= high for low, high in MOBILE_BANDS)


def match_carrier(licensee: str) -> str | None:
    """Match licensee name to carrier key, or None."""
    upper = licensee.upper()
    for key, cfg in CARRIER_PATTERNS.items():
        if any(p.upper() in upper for p in cfg["patterns"]):
            return key
    return None


def safe_float(val: str, default: float = 0.0) -> float:
    """Parse float from CSV field, returning default on failure."""
    try:
        return float((val or "").strip().strip('"'))
    except (ValueError, TypeError):
        return default


def process(csv_path: str, output_dir: str) -> dict:
    """
    Process ISED Site Data Extract CSV → per-carrier JSON files.

    Deduplicates by rounding lat/lon to 3 decimal places (~111m),
    which collapses co-located sector antennas into one site.
    """
    # Collect unique sites: key = (carrier, round(lat,3), round(lon,3))
    sites = defaultdict(dict)
    row_count = 0
    match_count = 0

    print(f"Reading {csv_path} ...")

    with open(csv_path, "r", encoding="latin-1") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row_count += 1

            # Parse frequency
            freq = safe_float(row.get("TRANSMIT_FREQ", ""))
            if not is_mobile_freq(freq):
                continue

            # Match carrier
            licensee = (row.get("LICENSEE") or "").strip()
            carrier = match_carrier(licensee)
            if carrier is None:
                continue

            # Parse coordinates
            lat = safe_float(row.get("LATITUDE", ""))
            lon = safe_float(row.get("LONGITUDE", ""))

            # Valid Canadian coordinates check
            if not (41.0 <= lat <= 84.0 and -141.0 <= lon <= -52.0):
                continue

            match_count += 1

            # Parse tower metadata
            elev = safe_float(row.get("SITE_ELEV", ""))
            ant_ht = safe_float(row.get("TX_ANT_HT", ""))
            ant_gain = safe_float(row.get("TX_ANT_GAIN", ""))
            tx_pwr = safe_float(row.get("TX_PWR", ""))
            prov = (row.get("PROV") or "").strip()
            location = (row.get("LOCATION") or "").strip()

            # Deduplicate: round to 3 decimal places (~111m grid)
            site_key = (round(lat, 3), round(lon, 3))

            if site_key not in sites[carrier]:
                sites[carrier][site_key] = {
                    "lat": round(lat, 4),
                    "lon": round(lon, 4),
                    "elev": round(elev),
                    "ht": round(ant_ht),
                    "prov": prov,
                    "bands": set(),
                    "gain": ant_gain,
                    "pwr": tx_pwr,
                }

            # Accumulate band info and keep max gain/power
            site = sites[carrier][site_key]
            site["bands"].add(round(freq))
            if ant_gain > site["gain"]:
                site["gain"] = ant_gain
            if tx_pwr > site["pwr"]:
                site["pwr"] = tx_pwr

    print(f"Processed {row_count:,} rows, {match_count:,} mobile entries matched")

    # Write per-carrier JSON
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    summary = {}

    for carrier_key, cfg in CARRIER_PATTERNS.items():
        carrier_sites = list(sites[carrier_key].values())

        # Sort by lat for efficient binary search in JS
        carrier_sites.sort(key=lambda s: s["lat"])

        # Compact output format
        compact = []
        for s in carrier_sites:
            # Classify bands into categories for the signal model
            bands = sorted(s["bands"])
            band_cats = set()
            for b in bands:
                if b < 1000:
                    band_cats.add("low")      # 700/850 — best rural coverage
                elif b < 2500:
                    band_cats.add("mid")      # 1700/1900/2100 — urban/suburban
                else:
                    band_cats.add("high")     # 2600/3500 — 5G capacity

            compact.append({
                "lt": s["lat"],           # latitude
                "ln": s["lon"],           # longitude
                "el": s["elev"],          # elevation (m ASL)
                "ht": s["ht"],            # antenna height (m AGL)
                "pv": s["prov"],          # province code
                "gn": round(s["gain"], 1),# antenna gain (dBi)
                "pw": round(s["pwr"], 1), # TX power (W)
                "bc": sorted(band_cats),  # band categories: low/mid/high
            })

        out_file = output_path / cfg["file"]
        with open(out_file, "w") as f:
            json.dump(compact, f, separators=(",", ":"))

        size_kb = out_file.stat().st_size / 1024
        summary[cfg["display"]] = {
            "sites": len(compact),
            "file": cfg["file"],
            "size_kb": round(size_kb, 1),
            "color": cfg["color"],
        }
        print(f"  {cfg['display']}: {len(compact):,} unique sites → "
              f"{cfg['file']} ({size_kb:.1f} KB)")

    # Write metadata
    meta_file = output_path / "towers_meta.json"
    with open(meta_file, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nMetadata: {meta_file}")

    return summary


if __name__ == "__main__":
    csv_file = sys.argv[1] if len(sys.argv) > 1 else "/tmp/Site_Data_Extract.csv"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else str(
        Path(__file__).resolve().parent.parent / "data"
    )
    process(csv_file, out_dir)
    print("Done.")

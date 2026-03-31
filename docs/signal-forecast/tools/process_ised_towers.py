#!/usr/bin/env python3
"""
process_ised_towers.py — Extract Big 3 Canadian carrier tower data from ISED TAFL database.

Reads the ISED TAFL_LTAF.csv (Spectrum Management System tower data) and outputs
compact JSON files per carrier for use in the Signal Forecast app.

ISED TAFL CSV column mapping (no headers in file):
  col 1:  Frequency (MHz)
  col 10: Bandwidth (kHz)
  col 14: EIRP (dBW)
  col 31: Location name
  col 39: Province
  col 40: Latitude (decimal degrees)
  col 41: Longitude (decimal degrees)
  col 42: Ground elevation (m ASL)
  col 43: Antenna height (m AGL)
  col 54: Licensee name

Source: https://www.ic.gc.ca/engineering/SMS_TAFL_Files/TAFL_LTAF.zip
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

# Carrier name patterns in ISED data → display name
CARRIER_PATTERNS = {
    "bell": {
        "patterns": ["Bell Mobility", "Bell Canada"],
        "display": "Bell",
        "file": "towers_bell.json",
    },
    "rogers": {
        "patterns": ["Rogers Communications", "Rogers Comm"],
        "display": "Rogers",
        "file": "towers_rogers.json",
    },
    "telus": {
        "patterns": ["TELUS Communi", "TELUS Mobility"],
        "display": "TELUS",
        "file": "towers_telus.json",
    },
}

# Mobile frequency bands (MHz) — LTE and 5G bands used in Canada
# Covers all ISED-auctioned cellular spectrum allocations
MOBILE_BANDS = [
    (694, 756),     # Band 12/17/29 — 700 MHz (rural workhorse)
    (758, 803),     # Band 13/14 — 700 MHz upper
    (824, 894),     # Band 5/26 — 850 MHz (legacy + LTE)
    (1710, 1780),   # Band 3/4/66 — AWS/1700 MHz
    (1850, 1990),   # Band 2/25 — PCS/1900 MHz
    (2110, 2200),   # Band 1/4/66 — 2100 MHz + AWS-3 (2180-2200)
    (2496, 2690),   # Band 7/41 — 2600 MHz
    (3450, 3980),   # n77/n78 — 3500-3980 MHz (5G mid-band, full C-band)
]


def is_mobile_frequency(freq_mhz: float) -> bool:
    """Check if a frequency falls within a Canadian mobile band."""
    return any(low <= freq_mhz <= high for low, high in MOBILE_BANDS)


def match_carrier(licensee: str) -> str | None:
    """Match a licensee name to a carrier key. Returns None if no match."""
    for key, cfg in CARRIER_PATTERNS.items():
        if any(pattern.lower() in licensee.lower() for pattern in cfg["patterns"]):
            return key
    return None


def parse_float(val: str, default: float = 0.0) -> float:
    """Safely parse a float from CSV field."""
    try:
        return float(val.strip().strip('"'))
    except (ValueError, TypeError):
        return default


def process_tafl(csv_path: str, output_dir: str) -> dict:
    """
    Process ISED TAFL CSV and output per-carrier tower JSON files.

    Returns a summary dict with counts per carrier.
    """
    # Collect unique tower sites per carrier
    # Key: (carrier, round(lat,4), round(lon,4)) to deduplicate co-located antennas
    sites = defaultdict(dict)

    print(f"Reading {csv_path} ...")
    row_count = 0
    match_count = 0

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for row in reader:
            row_count += 1
            if len(row) < 55:
                continue

            # Extract fields
            freq_mhz = parse_float(row[1])
            eirp_dbw = parse_float(row[14])
            lat = parse_float(row[40])
            lon = parse_float(row[41])
            elevation_m = parse_float(row[42])
            antenna_height_m = parse_float(row[43])
            licensee = row[54].strip().strip('"')
            province = row[39].strip().strip('"')
            location = row[31].strip().strip('"')

            # Filter: must be mobile frequency + Big 3 carrier
            if not is_mobile_frequency(freq_mhz):
                continue
            carrier = match_carrier(licensee)
            if carrier is None:
                continue

            # Valid coordinates check
            if not (41.0 <= lat <= 84.0 and -141.0 <= lon <= -52.0):
                continue

            match_count += 1

            # Deduplicate by rounding to ~11m precision (4 decimal places)
            site_key = (round(lat, 4), round(lon, 4))

            if site_key not in sites[carrier]:
                sites[carrier][site_key] = {
                    "lat": round(lat, 5),
                    "lon": round(lon, 5),
                    "elev": round(elevation_m),
                    "ht": round(antenna_height_m),
                    "prov": province,
                    "loc": location,
                    "freq": [],        # collect all frequencies at this site
                    "eirp_max": eirp_dbw,
                }

            # Track max EIRP and all frequencies at this site
            site = sites[carrier][site_key]
            if freq_mhz not in site["freq"]:
                site["freq"].append(round(freq_mhz, 1))
            if eirp_dbw > site["eirp_max"]:
                site["eirp_max"] = eirp_dbw

    print(f"Processed {row_count:,} rows, {match_count:,} mobile entries matched")

    # Write per-carrier JSON files
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    summary = {}

    for carrier_key, cfg in CARRIER_PATTERNS.items():
        carrier_sites = list(sites[carrier_key].values())

        # Sort by province then lat for efficient spatial search
        carrier_sites.sort(key=lambda s: (s["prov"], s["lat"]))

        # Compact format: only keep fields needed by the signal model
        compact = []
        for s in carrier_sites:
            compact.append({
                "lat": s["lat"],
                "lon": s["lon"],
                "elev": s["elev"],
                "ht": s["ht"],
                "prov": s["prov"],
                "eirp": round(s["eirp_max"], 1),
                "bands": sorted(set(round(f) for f in s["freq"])),
            })

        out_file = output_path / cfg["file"]
        with open(out_file, "w") as f:
            json.dump(compact, f, separators=(",", ":"))

        size_kb = out_file.stat().st_size / 1024
        summary[cfg["display"]] = {
            "sites": len(compact),
            "file": cfg["file"],
            "size_kb": round(size_kb, 1),
        }
        print(f"  {cfg['display']}: {len(compact):,} unique sites → {cfg['file']} ({size_kb:.1f} KB)")

    return summary


if __name__ == "__main__":
    csv_file = sys.argv[1] if len(sys.argv) > 1 else "/tmp/TAFL_LTAF.csv"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else str(
        Path(__file__).resolve().parent.parent / "data"
    )
    summary = process_tafl(csv_file, out_dir)

    # Write summary metadata
    meta_file = Path(out_dir) / "towers_meta.json"
    with open(meta_file, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nMetadata written to {meta_file}")
    print("Done.")

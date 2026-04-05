"""
Preprocess LA Parking Citations CSV → compact JSON for the React map.

Strategy:
  - Stream the 2.2 GB CSV in chunks (never loads fully into RAM)
  - Drop rows missing lat/lng
  - Keep only the columns the map needs
  - Reservoir-sample 80,000 rows so the browser stays snappy
  - Output: spotwise-app/public/citations.json  (~6-8 MB)
"""

import csv
import json
import random
import os
import sys
from pathlib import Path

SRC  = Path(__file__).parent / "data" / "Parking_Citations.csv"
DEST = Path(__file__).parent / "spotwise-app" / "public" / "citations.json"
DEST.parent.mkdir(parents=True, exist_ok=True)

TARGET  = 80_000   # max records in output
SEED    = 42
random.seed(SEED)

# Violation → short display label
LABEL = {
    "DOUBLE PARKING":               "Double Parking",
    "STREET CLEANING":              "Street Cleaning",
    "EXPIRED METER":                "Expired Meter",
    "NO PARK/STREET CLEAN":         "Street Cleaning",
    "METER EXPIRED":                "Expired Meter",
    "FIRE HYDRANT":                 "Fire Hydrant",
    "RED ZONE":                     "Red Zone",
    "NO STOPPING/STANDING":         "No Stopping",
    "BLOCKING DRIVEWAY":            "Blocking Driveway",
    "OVERTIME PARKING":             "Overtime Parking",
    "NO PARKING":                   "No Parking",
    "PREFERENTIAL PARKING":         "Pref. Parking",
    "DISPLAY OF PLATES":            "Display of Plates",
    "DISABLED VEHICLE":             "Disabled Vehicle",
    "TOW AWAY ZONE":                "Tow Away Zone",
    "BUS ZONE":                     "Bus Zone",
}

# Violation → hex color for the map dot
COLOR = {
    "Street Cleaning":  "#ef4444",   # red
    "Expired Meter":    "#f97316",   # orange
    "Double Parking":   "#8b5cf6",   # purple
    "Fire Hydrant":     "#ec4899",   # pink
    "Red Zone":         "#dc2626",   # dark red
    "No Stopping":      "#f59e0b",   # amber
    "Blocking Driveway":"#14b8a6",   # teal
    "Overtime Parking": "#06b6d4",   # cyan
    "No Parking":       "#eab308",   # yellow
    "Pref. Parking":    "#84cc16",   # lime
    "Display of Plates":"#a78bfa",   # violet
    "Disabled Vehicle": "#fb7185",   # rose
    "Tow Away Zone":    "#f43f5e",   # deep red
    "Bus Zone":         "#10b981",   # emerald
    "Other":            "#64748b",   # slate
}

def normalize_viol(raw: str) -> str:
    raw = raw.strip().upper()
    for key, label in LABEL.items():
        if key in raw:
            return label
    return "Other"

def parse_time(t: str) -> str:
    """Convert '904' → '09:04', '1430' → '14:30'"""
    t = t.strip().zfill(4)
    return f"{t[:2]}:{t[2:]}"

def parse_date(d: str) -> str:
    """'2025 Apr 26 12:00:00 AM' → '2025-04-26'"""
    parts = d.strip().split()
    if len(parts) >= 3:
        months = {"Jan":"01","Feb":"02","Mar":"03","Apr":"04","May":"05","Jun":"06",
                  "Jul":"07","Aug":"08","Sep":"09","Oct":"10","Nov":"11","Dec":"12"}
        y, m, day = parts[0], months.get(parts[1], "01"), parts[2]
        return f"{y}-{m}-{day.zfill(2)}"
    return d

print(f"Reading {SRC}  ({SRC.stat().st_size / 1e9:.2f} GB)…")

reservoir = []
total_read = 0
skipped    = 0

with open(SRC, newline="", encoding="utf-8", errors="replace") as f:
    reader = csv.DictReader(f)
    for i, row in enumerate(reader):
        total_read += 1
        if total_read % 1_000_000 == 0:
            print(f"  …scanned {total_read:,} rows  (kept {len(reservoir):,})", flush=True)

        try:
            lat = float(row["loc_lat"])
            lng = float(row["loc_long"])
        except (ValueError, KeyError):
            skipped += 1
            continue

        # LA bounding box sanity check
        if not (33.6 <= lat <= 34.8 and -118.8 <= lng <= -117.8):
            skipped += 1
            continue

        viol  = normalize_viol(row.get("violation_description", ""))
        color = COLOR.get(viol, COLOR["Other"])
        fine  = row.get("fine_amount", "").strip()
        make  = row.get("make", "").strip().title()
        body  = row.get("body_style", "").strip()
        date  = parse_date(row.get("issue_date", ""))
        time  = parse_time(row.get("issue_time", "0000"))

        record = {
            "lat":   round(lat, 6),
            "lng":   round(lng, 6),
            "v":     viol,
            "c":     color,
            "fine":  fine,
            "make":  make,
            "body":  body,
            "date":  date,
            "time":  time,
        }

        # Reservoir sampling (Algorithm R)
        if len(reservoir) < TARGET:
            reservoir.append(record)
        else:
            j = random.randint(0, total_read)
            if j < TARGET:
                reservoir[j] = record

print(f"\nScanned {total_read:,} rows — kept {len(reservoir):,} — skipped {skipped:,} (bad coords)")

# Build legend metadata
from collections import Counter
counts = Counter(r["v"] for r in reservoir)
legend = [
    {"label": label, "color": COLOR.get(label, COLOR["Other"]), "count": counts.get(label, 0)}
    for label in sorted(counts, key=lambda x: -counts[x])
]

output = {"records": reservoir, "legend": legend, "total_source_rows": total_read}

print(f"Writing {DEST}…", end=" ", flush=True)
with open(DEST, "w") as f:
    json.dump(output, f, separators=(",", ":"))

size_mb = DEST.stat().st_size / 1e6
print(f"done  ({size_mb:.1f} MB)")
print("\nTop violations in sample:")
for item in legend[:8]:
    print(f"  {item['color']}  {item['label']:25s} {item['count']:6,}")

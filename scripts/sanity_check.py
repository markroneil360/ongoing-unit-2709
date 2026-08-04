#!/usr/bin/env python3
"""Three independent public-artifact checks for the R6E8A dashboard."""
from __future__ import annotations

import json
import math
import re
from datetime import date, timedelta
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
HDF_COUNTS_PER_PA = 56_000.0
PROHIBITED_PUBLIC_KEYS = {
    "above_median_percent",
    "above_window_median_percent",
    "daily_median_rms_counts",
    "window_median_rms_counts",
    "multiple_of_median",
    "multiple_of_window_median",
    "simultaneous_ehz_robust_z",
    "classification",
}
PROHIBITED_PUBLIC_PHRASES = (
    "above median",
    "same-channel context",
    "same-day difference",
    "peer percentile",
)


def load(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def walk_keys(value, path="root"):
    if isinstance(value, dict):
        overlap = PROHIBITED_PUBLIC_KEYS.intersection(value)
        assert not overlap, f"prohibited keys at {path}: {sorted(overlap)}"
        for key, child in value.items():
            walk_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            walk_keys(child, f"{path}[{index}]")


def check_structure_and_rules():
    source = (ROOT / "index.html").read_text(encoding="utf-8")
    lower = source.lower()
    for phrase in PROHIBITED_PUBLIC_PHRASES:
        assert phrase not in lower, f"prohibited public wording: {phrase}"
    required = (
        "ISO 7196",
        "ANSI/ASA + ASHRAE",
        "Defra NANR45",
        "WHO night noise + ISO 1996",
        "Tier 1",
        "Tier 2",
        "Tier 3",
        "Tier 4",
        "Current recommendation: hold the result at N/A",
        "Infrasound Detected",
    )
    for phrase in required:
        assert phrase in source, f"missing required public element: {phrase}"
    assert source.index("HDF pressure / infrasound") < source.index("EHZ seismic record")
    assert source.index('id="missing-title"') < source.index('id="methods-title"')
    visible = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", source, flags=re.I)
    visible = re.sub(r"<[^>]+>", " ", visible)
    assert len(re.findall(r"\bFDSN\b", visible, flags=re.I)) == 1
    print("PASS 1/3 - public structure, HDF priority, four guides, four tiers, and wording")


def check_data_and_math():
    live = load("data/daily-highest.json")
    history = load("data/daily-highest-history.json")
    archive = load("data/unified_daily.json")
    walk_keys(live)
    walk_keys(history)
    assert live.get("schema_version") == 3
    channels = live["channels"]
    assert set(channels) == {"HDF", "EHZ"}
    assert channels["HDF"]["available"] and channels["EHZ"]["available"]
    assert "pressure" in channels["HDF"]["role"].lower()
    assert "vertical" in channels["EHZ"]["role"].lower()

    hdf_events = [
        channels["HDF"]["detroit_day_highest"],
        channels["HDF"]["trailing_24h_highest"],
        *history["days"],
        history["archived_reference"],
    ]
    for event in hdf_events:
        expected = float(event["peak_rms_counts"]) / HDF_COUNTS_PER_PA
        actual = float(event["estimated_pressure_pa_rms_nominal"])
        assert math.isclose(actual, expected, rel_tol=0, abs_tol=5e-7), (event.get("event_date_et"), actual, expected)

    archive_days = archive["days"]
    assert len(archive_days) == 49
    assert archive_days[0]["date"] == "2026-04-12" and archive_days[-1]["date"] == "2026-05-30"
    assert sum(day["status"] == "gap" for day in archive_days) == 9
    assert sum(day["status"] in {"local", "source"} for day in archive_days) == 40
    history_dates = {day["event_date_et"] for day in history["days"]}
    assert len(history_dates) == len(history["days"]) == 7
    span = (date.fromisoformat("2026-08-04") - date.fromisoformat("2026-04-12")).days + 1
    source_backed = 40 + 8 + len(history_dates)
    unretained = span - source_backed - 9
    assert (span, source_backed, unretained) == (115, 55, 51)
    print("PASS 2/3 - dual-channel data, pressure conversion, dates, gaps, and full-span accounting")


def check_pdfs():
    paths = (
        ROOT / "downloads" / "R6E8A-24-hour-report.pdf",
        ROOT / "downloads" / "R6E8A-7-day-trailing-report.pdf",
    )
    for path in paths:
        raw = path.read_bytes()
        assert raw.startswith(b"%PDF-") and b"%%EOF" in raw[-1024:]
        reader = PdfReader(str(path))
        assert len(reader.pages) == 2
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        lower = text.lower()
        for phrase in PROHIBITED_PUBLIC_PHRASES:
            assert phrase not in lower, f"{path.name}: {phrase}"
        for phrase in ("ISO 7196", "ASHRAE", "NANR45", "WHO", "TIER 1", "TIER 4"):
            assert phrase.lower() in lower, f"{path.name}: missing {phrase}"
        assert "account for up to 30 minutes of lag" in lower
        uris = []
        for page in reader.pages:
            for annotation in page.get("/Annots", []):
                obj = annotation.get_object()
                action = obj.get("/A")
                if action and action.get("/URI"):
                    uris.append(str(action.get("/URI")))
        assert any("raspberryshake.org" in uri for uri in uris), f"{path.name}: missing verification link"
    print("PASS 3/3 - two-page PDF integrity, text rules, and verification links")


def main():
    check_structure_and_rules()
    check_data_and_math()
    check_pdfs()
    print("SANITY CHECK: 3/3 PASS")


if __name__ == "__main__":
    main()

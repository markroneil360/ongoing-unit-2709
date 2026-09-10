#!/usr/bin/env python3
"""Current public FDSN status for AM.R6E8A, with channel and coverage validation."""
from __future__ import annotations

import datetime
import io
import json
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

from obspy import UTCDateTime, read

BASE = "https://data.raspberryshake.org/fdsnws"
TZ = ZoneInfo("America/Detroit")
OUT = Path(__file__).resolve().parents[1] / "data" / "current-status.json"
EXPECTED = {"network": "AM", "station": "R6E8A", "location": "00"}


def _iso_utc(value: UTCDateTime) -> str:
    return value.datetime.replace(tzinfo=datetime.timezone.utc).isoformat()


def _interval_union_seconds(traces, start: UTCDateTime, end: UTCDateTime) -> float:
    intervals = []
    start_s, end_s = float(start), float(end)
    for tr in traces:
        sr = float(tr.stats.sampling_rate)
        a = max(start_s, float(tr.stats.starttime))
        b = min(end_s, float(tr.stats.endtime) + 1.0 / sr)
        if b > a:
            intervals.append((a, b))
    intervals.sort()
    merged = []
    for a, b in intervals:
        if not merged or a > merged[-1][1]:
            merged.append([a, b])
        else:
            merged[-1][1] = max(merged[-1][1], b)
    return sum(b - a for a, b in merged)


def fetch(chan: str, start: UTCDateTime, end: UTCDateTime) -> dict:
    url = (
        f"{BASE}/dataselect/1/query?net=AM&sta=R6E8A&loc=00&cha={chan}"
        f"&start={start.isoformat()}&end={end.isoformat()}&format=miniseed&nodata=404"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "r6e8a-hourly-status/2.0"})
    try:
        raw = urllib.request.urlopen(req, timeout=120).read()
        stream = read(io.BytesIO(raw))
    except Exception as exc:
        return {"channel": chan, "ok": False, "error": str(exc), "url": url}

    unexpected = []
    for tr in stream:
        got = {
            "network": str(tr.stats.network),
            "station": str(tr.stats.station),
            "location": str(tr.stats.location),
            "channel": str(tr.stats.channel),
        }
        if got != {**EXPECTED, "channel": chan}:
            unexpected.append(got)
    if unexpected:
        return {
            "channel": chan,
            "ok": False,
            "error": "unexpected MiniSEED identity",
            "unexpected_ids": unexpected,
            "url": url,
        }

    stream.merge(method=0, fill_value=None)
    stream.trim(starttime=start, endtime=end, pad=False, nearest_sample=False)
    traces = stream.split()
    if not traces:
        return {"channel": chan, "ok": False, "error": "no traces in requested window", "url": url}

    expected_seconds = float(end - start)
    observed_seconds = _interval_union_seconds(traces, start, end)
    coverage = 100.0 * observed_seconds / expected_seconds if expected_seconds > 0 else 0.0
    latest = max(tr.stats.endtime for tr in traces)
    edge_gap_seconds = max(0.0, float(end - latest))
    sample_rates = sorted({round(float(tr.stats.sampling_rate), 6) for tr in traces})
    ok = coverage >= 99.0 and edge_gap_seconds <= 2.0

    return {
        "channel": chan,
        "ok": ok,
        "coverage_pct": round(min(100.0, coverage), 3),
        "segments": len(traces),
        "sample_rates_hz": sample_rates,
        "latest_sample_utc": _iso_utc(latest),
        "latest_sample_et": latest.datetime.replace(tzinfo=datetime.timezone.utc).astimezone(TZ).strftime(
            "%Y-%m-%d %I:%M:%S %p %Z"
        ),
        "edge_gap_seconds": round(edge_gap_seconds, 6),
        "identity_verified": True,
        "window_clipped_before_coverage": True,
        "url": url,
    }


def main() -> None:
    now = datetime.datetime.now(datetime.timezone.utc)
    end_dt = now - datetime.timedelta(minutes=30)
    start_dt = end_dt - datetime.timedelta(minutes=20)
    start = UTCDateTime(end_dt - datetime.timedelta(minutes=20))
    end = UTCDateTime(end_dt)
    channels = {channel: fetch(channel, start, end) for channel in ("HDF", "EHZ")}
    payload = {
        "station": "AM.R6E8A.00",
        "generated_utc": now.isoformat(),
        "generated_et": now.astimezone(TZ).strftime("%Y-%m-%d %I:%M:%S %p %Z"),
        "window_start_utc": start_dt.isoformat(),
        "window_end_utc": end_dt.isoformat(),
        "channels": channels,
        "source": "Raspberry Shake public FDSN DataSelect",
        "display_note": "*Account for up to 30 minutes of lag. Missing acquisition time is not scored as zero, quiet, normal, compliant, or below benchmark.",
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if not all(item.get("ok") for item in channels.values()):
        raise SystemExit("Current HDF/EHZ validation failed.")


if __name__ == "__main__":
    main()

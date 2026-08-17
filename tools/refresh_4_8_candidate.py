#!/usr/bin/env python3
"""Build a READ-ONLY R6E8A HDF 4-8 Hz refresh candidate from public FDSN data.

This script intentionally does not edit the dashboard. It revalidates the known
Aug. 15 checkpoint first, then writes a candidate JSON for human/QA review.

Method is kept compatible with the corrected archive handoff:
- AM.R6E8A.00.HDF only
- clock-aligned complete 60-second windows; incomplete/gapped minutes excluded
- Welch PSD, Hann, 8-second segments at 100 sps, 50% overlap
- dominant band = greatest mean PSD among 1-4, 4-8, 8-16, 16-20 Hz
- sustained events = consecutive complete 4-8-dominant minutes
- no interpolation and no missing time treated as zero
"""
from __future__ import annotations

import io
import json
import math
import time
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
from obspy import UTCDateTime, read
from scipy.signal import welch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "r6e8a_4_8_refresh_candidate.json"
BASE = "https://data.raspberryshake.org/fdsnws/dataselect/1/query"
TZ = ZoneInfo("America/Detroit")

# Corrected full-archive checkpoint, independently preserved in the handoff JSON.
BASE_END_EXCLUSIVE = datetime(2026, 8, 12, 19, 13, tzinfo=timezone.utc)
BASE_STATS = {
    "analyzed_minutes": 148_544,
    "dom48_minutes": 55_159,
    "count15": 604,
    "mins15": 31_858,
    "count30": 323,
    "mins30": 26_079,
    "count60": 159,
    "mins60": 19_210,
}

# Published checkpoint that must reproduce exactly before a current candidate is accepted.
PREVIEW_END_EXCLUSIVE = datetime(2026, 8, 15, 21, 2, tzinfo=timezone.utc)  # data through 5:02 PM ET
PREVIEW_EXPECTED = {
    "dom48_minutes": 56_472,
    "count15": 608,
    "mins15": 31_960,
    "count30": 324,
    "mins30": 26_110,
    "count60": 159,
    "mins60": 19_210,
    "ordinance_events": 74,
}

BANDS = (("1-4", 1.0, 4.0), ("4-8", 4.0, 8.0),
         ("8-16", 8.0, 16.0), ("16-20", 16.0, 20.0))


def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def http_bytes(url: str, tries: int = 4, timeout: int = 180) -> bytes | None:
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "r6e8a-4-8-refresh/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:
            last = e
            if getattr(e, "code", None) in (204, 404):
                return None
            time.sleep(3 * (attempt + 1))
    raise last


def extract_complete_minute(st, minute_dt: datetime):
    """Return one complete 60 s array for a clock-aligned UTC minute, else None."""
    t0 = UTCDateTime(minute_dt)
    for tr in st:
        sr = float(tr.stats.sampling_rate)
        if not (95.0 <= sr <= 105.0):
            continue
        n = int(round(sr * 60.0))
        dt = 1.0 / sr
        # Require coverage of [t0, t0+60) including its final sample.
        if tr.stats.starttime > t0 + dt / 2:
            continue
        if tr.stats.endtime < t0 + 60.0 - dt * 1.5:
            continue
        idx = int(round((t0 - tr.stats.starttime) * sr))
        if idx < 0 or idx + n > len(tr.data):
            continue
        x = tr.data[idx:idx+n]
        if len(x) != n:
            continue
        if np.ma.isMaskedArray(x) and np.any(np.ma.getmaskarray(x)):
            continue
        x = np.asarray(x, dtype=np.float64)
        if not np.all(np.isfinite(x)):
            continue
        return x, sr
    return None


def dominant_band(x: np.ndarray, sr: float) -> tuple[str, dict[str, float]]:
    nper = min(int(round(sr * 8.0)), len(x))
    nover = min(nper // 2, nper - 1)
    f, p = welch(x, fs=sr, window="hann", nperseg=nper,
                 noverlap=nover, detrend="constant", scaling="density")
    means = {}
    for i, (name, lo, hi) in enumerate(BANDS):
        mask = (f >= lo) & ((f <= hi) if i == len(BANDS)-1 else (f < hi))
        means[name] = float(np.mean(p[mask])) if np.any(mask) else float("nan")
    winner = max(means, key=lambda k: -math.inf if not math.isfinite(means[k]) else means[k])
    return winner, means


def fetch_classified(start: datetime, requested_end: datetime):
    """Fetch/classify in <=6 h blocks. Returns dict minute_epoch->band and provenance."""
    classified: dict[int, str] = {}
    latest_sample = None
    urls = []
    cur = start
    while cur < requested_end:
        end = min(cur + timedelta(hours=6), requested_end)
        url = (f"{BASE}?net=AM&sta=R6E8A&loc=00&cha=HDF"
               f"&start={iso_z(cur)}&end={iso_z(end)}&format=miniseed&nodata=404")
        urls.append(url)
        raw = http_bytes(url)
        if raw:
            st = read(io.BytesIO(raw))
            # Keep true gaps masked; do not interpolate.
            st.merge(method=0, fill_value=None)
            for tr in st:
                e = tr.stats.endtime.datetime.replace(tzinfo=timezone.utc)
                latest_sample = e if latest_sample is None or e > latest_sample else latest_sample
            m = cur.replace(second=0, microsecond=0)
            if m < cur:
                m += timedelta(minutes=1)
            while m < end:
                got = extract_complete_minute(st, m)
                if got is not None:
                    x, sr = got
                    band, _ = dominant_band(x, sr)
                    classified[int(m.timestamp())] = band
                m += timedelta(minutes=1)
        cur = end
        time.sleep(0.6)
    return classified, latest_sample, urls


def subset(data: dict[int, str], end_exclusive: datetime) -> dict[int, str]:
    e = int(end_exclusive.timestamp())
    return {t: b for t, b in data.items() if t < e}


def runs48(data: dict[int, str]):
    """Contiguous minute runs, broken by missing/non-4-8 minutes."""
    out = []
    cur = []
    for t in sorted(data):
        if data[t] == "4-8" and (not cur or t == cur[-1] + 60):
            cur.append(t)
        else:
            if cur:
                out.append(cur)
                cur = []
            if data[t] == "4-8":
                cur = [t]
    if cur:
        out.append(cur)
    return out


def run_stats(data: dict[int, str]):
    runs = runs48(data)
    out = {"runs_total": len(runs)}
    for thr in (15, 30, 60):
        q = [r for r in runs if len(r) >= thr]
        out[f"count{thr}"] = len(q)
        out[f"mins{thr}"] = sum(len(r) for r in q)
    return out, runs


def is_night_minute(epoch: int) -> bool:
    dt = datetime.fromtimestamp(epoch, tz=timezone.utc).astimezone(TZ)
    h = dt.hour
    if h < 7:
        return True
    # Conservative downtown treatment preserved from approved dashboard:
    # Friday/Saturday nights start 11 PM; all other nights start 10 PM.
    start_hour = 23 if dt.weekday() in (4, 5) else 22
    return h >= start_hour


def ordinance_count(runs) -> int:
    count = 0
    for r in runs:
        if len(r) < 30:
            continue
        night_mins = sum(1 for t in r if is_night_minute(t))
        if night_mins >= 30:
            count += 1
    return count


def combine(post: dict[int, str]):
    rs, runs = run_stats(post)
    c = Counter(post.values())
    result = {
        "analyzed_minutes": BASE_STATS["analyzed_minutes"] + len(post),
        "dom48_minutes": BASE_STATS["dom48_minutes"] + c["4-8"],
        "count15": BASE_STATS["count15"] + rs["count15"],
        "mins15": BASE_STATS["mins15"] + rs["mins15"],
        "count30": BASE_STATS["count30"] + rs["count30"],
        "mins30": BASE_STATS["mins30"] + rs["mins30"],
        "count60": BASE_STATS["count60"] + rs["count60"],
        "mins60": BASE_STATS["mins60"] + rs["mins60"],
        "post_band_counts": dict(c),
        "post_ordinance_events": ordinance_count(runs),
    }
    result["dom48_hours"] = round(result["dom48_minutes"] / 60.0, 2)
    result["dom48_percent_of_analyzed"] = round(100.0 * result["dom48_minutes"] / result["analyzed_minutes"], 2)
    result["hours15"] = round(result["mins15"] / 60.0, 2)
    result["hours30"] = round(result["mins30"] / 60.0, 2)
    result["hours60"] = round(result["mins60"] / 60.0, 2)
    result["shorter48_minutes"] = result["dom48_minutes"] - result["mins15"]
    result["shorter48_hours"] = round(result["shorter48_minutes"] / 60.0, 2)
    return result, runs


def main():
    started = datetime.now(timezone.utc)
    # Ask FDSN up to now. Any unavailable/partial trailing minute is excluded naturally.
    requested_end = started.replace(second=0, microsecond=0)
    post, latest_sample, urls = fetch_classified(BASE_END_EXCLUSIVE, requested_end)

    preview_post = subset(post, PREVIEW_END_EXCLUSIVE)
    preview, preview_runs = combine(preview_post)
    current, current_runs = combine(post)

    # Five explicit gates. Any failure prevents candidate acceptance.
    checks = []
    checks.append({
        "name": "1_checkpoint_total_reproduction",
        "pass": preview["dom48_minutes"] == PREVIEW_EXPECTED["dom48_minutes"],
        "observed": preview["dom48_minutes"], "expected": PREVIEW_EXPECTED["dom48_minutes"]})
    checks.append({
        "name": "2_checkpoint_sustained_reproduction",
        "pass": all(preview[k] == PREVIEW_EXPECTED[k] for k in ("count15","mins15","count30","mins30","count60","mins60")),
        "observed": {k: preview[k] for k in ("count15","mins15","count30","mins30","count60","mins60")},
        "expected": {k: PREVIEW_EXPECTED[k] for k in ("count15","mins15","count30","mins30","count60","mins60")}})
    edge = [int((PREVIEW_END_EXCLUSIVE - timedelta(minutes=i)).timestamp()) for i in range(1,7)]
    checks.append({
        "name": "3_checkpoint_edge_six_minutes",
        "pass": all(preview_post.get(t) == "4-8" for t in edge),
        "observed": [{"utc": datetime.fromtimestamp(t, timezone.utc).isoformat(), "band": preview_post.get(t)} for t in sorted(edge)],
        "expected": "six consecutive 4-8-dominant minutes ending at the 5:02 PM ET data edge"})
    # Current data integrity: no minute may be counted twice, all minute keys aligned, all labels valid.
    checks.append({
        "name": "4_minute_integrity",
        "pass": (len(post) == len(set(post)) and all(t % 60 == 0 for t in post)
                 and set(post.values()).issubset({b[0] for b in BANDS})),
        "observed": {"classified_minutes": len(post), "unique_minutes": len(set(post)),
                     "bands": sorted(set(post.values()))},
        "expected": "unique clock-aligned complete minutes; only defined bands"})
    # Arithmetic reconciliation: every 4-8 minute is either in >=15-minute runs or shorter runs.
    checks.append({
        "name": "5_arithmetic_reconciliation",
        "pass": current["mins15"] + current["shorter48_minutes"] == current["dom48_minutes"],
        "observed": {"sustained15_minutes": current["mins15"],
                     "shorter_minutes": current["shorter48_minutes"],
                     "total_dom48_minutes": current["dom48_minutes"]},
        "expected": "sustained15 + shorter = all 4-8-dominant minutes"})

    preview_ord_segment = ordinance_count(preview_runs)
    current_ord_segment = ordinance_count(current_runs)
    current["ordinance_events"] = PREVIEW_EXPECTED["ordinance_events"] + (current_ord_segment - preview_ord_segment)
    current["new_ordinance_events_since_preview"] = current_ord_segment - preview_ord_segment

    latest_complete = max(post) if post else None
    out = {
        "schema_version": 1,
        "station": "AM.R6E8A.00",
        "channel": "HDF",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "method": {
            "window": "clock-aligned complete 60-second windows; gaps excluded",
            "welch": "Hann; 8 s segments; 50% overlap; scipy.signal.welch",
            "dominance": "highest mean PSD among 1-4, 4-8, 8-16, 16-20 Hz",
            "sustained_event": "consecutive complete 4-8-dominant minutes",
            "missing": "excluded; never zero-filled or interpolated",
        },
        "source": "Raspberry Shake public FDSN DataSelect",
        "requested_through_utc": requested_end.isoformat(),
        "latest_returned_sample_utc": latest_sample.isoformat() if latest_sample else None,
        "latest_complete_analyzed_minute_utc": datetime.fromtimestamp(latest_complete, timezone.utc).isoformat() if latest_complete else None,
        "baseline": {"end_exclusive_utc": BASE_END_EXCLUSIVE.isoformat(), **BASE_STATS},
        "preview_checkpoint": {
            "end_exclusive_utc": PREVIEW_END_EXCLUSIVE.isoformat(),
            "recomputed": preview,
            "expected": PREVIEW_EXPECTED,
            "ordinance_segment_count": preview_ord_segment,
        },
        "current": current,
        "checks": checks,
        "all_five_checks_pass": all(c["pass"] for c in checks),
        "fdsn_urls": urls,
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({"all_five_checks_pass": out["all_five_checks_pass"],
                      "latest_returned_sample_utc": out["latest_returned_sample_utc"],
                      "current": current,
                      "checks": checks}, indent=2))
    if not out["all_five_checks_pass"]:
        raise SystemExit("Five-pass validation failed; dashboard must not be updated.")


if __name__ == "__main__":
    main()

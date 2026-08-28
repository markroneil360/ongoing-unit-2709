#!/usr/bin/env python3
"""Full AM.R6E8A.00.HDF 4-8 Hz recalculation with a >=10 minute sustained threshold.

Scope:
- Start: 2026-04-12 00:00 America/Detroit (2026-04-12 04:00 UTC)
- End: latest public FDSN edge with a conservative 30-minute lag allowance
- HDF only for pressure/infrasound spectral classification; EHZ is not mixed in
- Clock-aligned complete 60-second windows; incomplete/gapped minutes excluded
- Welch PSD, Hann, 8-second segments, 50% overlap
- Dominant band = greatest mean PSD among 1-4, 4-8, 8-16, 16-20 Hz
- Sustained event = consecutive complete 4-8-dominant minutes
- Primary sustained threshold = >=10 minutes; >=15/30/60 retained as secondary breakouts
- No interpolation; missing acquisition time is never scored as zero

The output is a candidate data file only. Publishing is a separate reviewed step.
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
OUT = ROOT / "data" / "r6e8a_4_8_10min_full.json"
BASE = "https://data.raspberryshake.org/fdsnws/dataselect/1/query"
TZ = ZoneInfo("America/Detroit")
START_ET = datetime(2026, 4, 12, 0, 0, tzinfo=TZ)
START_UTC = START_ET.astimezone(timezone.utc)
LAG_MINUTES = 30
CHUNK_HOURS = 12

PREVIEW_END_EXCLUSIVE = datetime(2026, 8, 15, 21, 2, tzinfo=timezone.utc)
PREVIEW_EXPECTED = {
    "analyzed_minutes": 152_973,
    "dom48_minutes": 56_472,
    "count15": 608,
    "mins15": 31_960,
    "count30": 324,
    "mins30": 26_110,
    "count60": 159,
    "mins60": 19_210,
}
BANDS = (("1-4", 1.0, 4.0), ("4-8", 4.0, 8.0),
         ("8-16", 8.0, 16.0), ("16-20", 16.0, 20.0))


def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def http_bytes(url: str, tries: int = 5, timeout: int = 240) -> bytes | None:
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "r6e8a-full-10min/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:
            last = e
            if getattr(e, "code", None) in (204, 404):
                return None
            time.sleep(3 * (attempt + 1))
    raise last


def extract_complete_minute(st, minute_dt: datetime):
    t0 = UTCDateTime(minute_dt)
    for tr in st:
        sr = float(tr.stats.sampling_rate)
        if not (95.0 <= sr <= 105.0):
            continue
        n = int(round(sr * 60.0))
        dt = 1.0 / sr
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


def classify_batch(items):
    """Classify complete minutes while preserving the exact Welch method."""
    by_sr: dict[float, list[tuple[int, np.ndarray]]] = {}
    for epoch, x, sr in items:
        key = round(sr, 6)
        by_sr.setdefault(key, []).append((epoch, x))
    out: dict[int, str] = {}
    for sr_key, group in by_sr.items():
        sr = float(sr_key)
        nper = int(round(sr * 8.0))
        nover = nper // 2
        X = np.stack([g[1] for g in group], axis=0)
        f, p = welch(X, fs=sr, window="hann", nperseg=nper,
                     noverlap=nover, detrend="constant", scaling="density", axis=1)
        means = []
        for i, (_name, lo, hi) in enumerate(BANDS):
            mask = (f >= lo) & ((f <= hi) if i == len(BANDS)-1 else (f < hi))
            means.append(np.mean(p[:, mask], axis=1))
        M = np.stack(means, axis=1)
        winners = np.argmax(M, axis=1)
        for (epoch, _), idx in zip(group, winners):
            out[epoch] = BANDS[int(idx)][0]
    return out


def fetch_classified(start: datetime, requested_end: datetime):
    classified: dict[int, str] = {}
    latest_sample = None
    urls = []
    cur = start
    chunk_no = 0
    while cur < requested_end:
        end = min(cur + timedelta(hours=CHUNK_HOURS), requested_end)
        url = (f"{BASE}?net=AM&sta=R6E8A&loc=00&cha=HDF"
               f"&start={iso_z(cur)}&end={iso_z(end)}&format=miniseed&nodata=404")
        urls.append(url)
        raw = http_bytes(url)
        if raw:
            st = read(io.BytesIO(raw))
            st.merge(method=0, fill_value=None)
            for tr in st:
                e = tr.stats.endtime.datetime.replace(tzinfo=timezone.utc)
                latest_sample = e if latest_sample is None or e > latest_sample else latest_sample
            batch = []
            m = cur.replace(second=0, microsecond=0)
            if m < cur:
                m += timedelta(minutes=1)
            while m < end:
                got = extract_complete_minute(st, m)
                if got is not None:
                    x, sr = got
                    batch.append((int(m.timestamp()), x, sr))
                m += timedelta(minutes=1)
            if batch:
                classified.update(classify_batch(batch))
        chunk_no += 1
        if chunk_no % 20 == 0:
            print(f"classified through {end.isoformat()} | minutes={len(classified)}", flush=True)
        cur = end
        time.sleep(0.15)
    return classified, latest_sample, urls


def runs48(data: dict[int, str]):
    runs = []
    cur = []
    prev_t = None
    for t in sorted(data):
        b = data[t]
        if b == "4-8" and cur and prev_t is not None and t == prev_t + 60:
            cur.append(t)
        elif b == "4-8":
            if cur:
                runs.append(cur)
            cur = [t]
        else:
            if cur:
                runs.append(cur)
                cur = []
        prev_t = t
    if cur:
        runs.append(cur)
    return runs


def is_night_minute(epoch: int) -> bool:
    dt = datetime.fromtimestamp(epoch, tz=timezone.utc).astimezone(TZ)
    if dt.hour < 7:
        return True
    start_hour = 23 if dt.weekday() in (4, 5) else 22
    return dt.hour >= start_hour


def ordinance_count(runs) -> int:
    count = 0
    for r in runs:
        if len(r) < 30:
            continue
        if sum(1 for t in r if is_night_minute(t)) >= 30:
            count += 1
    return count


def summarize(data: dict[int, str]):
    c = Counter(data.values())
    runs = runs48(data)
    out = {
        "analyzed_minutes": len(data),
        "dom48_minutes": c["4-8"],
        "band_counts": {name: c[name] for name, _lo, _hi in BANDS},
        "runs_total": len(runs),
    }
    for thr in (10, 15, 30, 60):
        q = [r for r in runs if len(r) >= thr]
        out[f"count{thr}"] = len(q)
        out[f"mins{thr}"] = sum(len(r) for r in q)
        out[f"hours{thr}"] = round(out[f"mins{thr}"] / 60.0, 2)
    out["dom48_hours"] = round(out["dom48_minutes"] / 60.0, 2)
    out["dom48_percent_of_analyzed"] = round(
        100.0 * out["dom48_minutes"] / out["analyzed_minutes"], 2
    ) if out["analyzed_minutes"] else 0.0
    out["shorter10_minutes"] = out["dom48_minutes"] - out["mins10"]
    out["shorter10_hours"] = round(out["shorter10_minutes"] / 60.0, 2)
    out["ordinance_events"] = ordinance_count(runs)
    longest = sorted(runs, key=lambda r: (-len(r), r[0]))[:10]
    out["longest_runs"] = [
        {
            "start_utc": datetime.fromtimestamp(r[0], timezone.utc).isoformat(),
            "start_et": datetime.fromtimestamp(r[0], timezone.utc).astimezone(TZ).isoformat(),
            "end_utc": datetime.fromtimestamp(r[-1] + 60, timezone.utc).isoformat(),
            "end_et": datetime.fromtimestamp(r[-1] + 60, timezone.utc).astimezone(TZ).isoformat(),
            "duration_minutes": len(r),
            "duration_hours": round(len(r) / 60.0, 2),
        } for r in longest
    ]
    return out, runs


def subset(data: dict[int, str], end_exclusive: datetime):
    e = int(end_exclusive.timestamp())
    return {t: b for t, b in data.items() if t < e}


def main():
    started = datetime.now(timezone.utc)
    requested_end = (started - timedelta(minutes=LAG_MINUTES)).replace(second=0, microsecond=0)
    if requested_end <= START_UTC:
        raise SystemExit("Invalid end before start")
    data, latest_sample, urls = fetch_classified(START_UTC, requested_end)
    current, current_runs = summarize(data)
    preview_data = subset(data, PREVIEW_END_EXCLUSIVE)
    preview, _preview_runs = summarize(preview_data)

    checks = []
    checks.append({
        "name": "1_known_checkpoint_totals",
        "pass": (preview["analyzed_minutes"] == PREVIEW_EXPECTED["analyzed_minutes"] and
                 preview["dom48_minutes"] == PREVIEW_EXPECTED["dom48_minutes"]),
        "observed": {"analyzed_minutes": preview["analyzed_minutes"],
                     "dom48_minutes": preview["dom48_minutes"]},
        "expected": {"analyzed_minutes": PREVIEW_EXPECTED["analyzed_minutes"],
                     "dom48_minutes": PREVIEW_EXPECTED["dom48_minutes"]},
    })
    checks.append({
        "name": "2_known_checkpoint_legacy_sustained",
        "pass": all(preview[k] == PREVIEW_EXPECTED[k]
                    for k in ("count15", "mins15", "count30", "mins30", "count60", "mins60")),
        "observed": {k: preview[k] for k in ("count15", "mins15", "count30", "mins30", "count60", "mins60")},
        "expected": {k: PREVIEW_EXPECTED[k] for k in ("count15", "mins15", "count30", "mins30", "count60", "mins60")},
    })
    edge = [int((PREVIEW_END_EXCLUSIVE - timedelta(minutes=i)).timestamp()) for i in range(1, 7)]
    checks.append({
        "name": "3_known_checkpoint_six_minute_edge",
        "pass": all(preview_data.get(t) == "4-8" for t in edge),
        "observed": [
            {"utc": datetime.fromtimestamp(t, timezone.utc).isoformat(), "band": preview_data.get(t)}
            for t in sorted(edge)
        ],
        "expected": "six consecutive 4-8-dominant minutes ending at the Aug 15 5:02 PM ET checkpoint edge",
    })
    checks.append({
        "name": "4_minute_integrity_and_band_domain",
        "pass": (len(data) == len(set(data)) and all(t % 60 == 0 for t in data)
                 and set(data.values()).issubset({b[0] for b in BANDS})),
        "observed": {"classified_minutes": len(data), "unique_minutes": len(set(data)),
                     "bands": sorted(set(data.values()))},
        "expected": "unique clock-aligned complete minutes using only the four defined bands",
    })
    nested_ok = (current["count10"] >= current["count15"] >= current["count30"] >= current["count60"] and
                 current["mins10"] >= current["mins15"] >= current["mins30"] >= current["mins60"])
    checks.append({
        "name": "5_10min_arithmetic_and_nested_thresholds",
        "pass": (current["mins10"] + current["shorter10_minutes"] == current["dom48_minutes"] and nested_ok),
        "observed": {
            "sustained10_minutes": current["mins10"],
            "shorter10_minutes": current["shorter10_minutes"],
            "total_dom48_minutes": current["dom48_minutes"],
            "counts_10_15_30_60": [current["count10"], current["count15"], current["count30"], current["count60"]],
            "minutes_10_15_30_60": [current["mins10"], current["mins15"], current["mins30"], current["mins60"]],
        },
        "expected": ">=10 sustained + <10 shorter = all 4-8 minutes; threshold counts/minutes monotonic",
    })

    latest_complete = max(data) if data else None
    out = {
        "schema_version": 2,
        "station": "AM.R6E8A.00",
        "channel": "HDF",
        "display_timezone": "America/Detroit",
        "analysis_start_et": START_ET.isoformat(),
        "analysis_start_utc": START_UTC.isoformat(),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "lag_allowance_minutes": LAG_MINUTES,
        "requested_through_utc": requested_end.isoformat(),
        "latest_returned_sample_utc": latest_sample.isoformat() if latest_sample else None,
        "latest_complete_analyzed_minute_utc": datetime.fromtimestamp(latest_complete, timezone.utc).isoformat() if latest_complete else None,
        "source": "Raspberry Shake public FDSN DataSelect",
        "method": {
            "window": "clock-aligned complete 60-second windows; gaps excluded",
            "welch": "Hann; 8 s segments; 50% overlap; scipy.signal.welch",
            "dominance": "highest mean PSD among 1-4, 4-8, 8-16, 16-20 Hz",
            "sustained_event_primary": "consecutive complete 4-8-dominant minutes; primary threshold >=10 minutes",
            "secondary_thresholds": [15, 30, 60],
            "missing": "excluded; never zero-filled or interpolated",
            "channel_boundary": "HDF only; EHZ is separate and not combined into these spectral totals",
        },
        "preview_checkpoint": {
            "end_exclusive_utc": PREVIEW_END_EXCLUSIVE.isoformat(),
            "recomputed": preview,
            "expected": PREVIEW_EXPECTED,
        },
        "current": current,
        "checks": checks,
        "all_five_checks_pass": all(c["pass"] for c in checks),
        "fdsn_request_count": len(urls),
        "fdsn_urls": urls,
        "publication_note": "No extrapolated hours. Values are derived only from successfully retrieved complete HDF minutes. The >=10-minute threshold is a reporting/event-definition choice, not a medical or legal exposure limit.",
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({
        "all_five_checks_pass": out["all_five_checks_pass"],
        "analysis_start_et": out["analysis_start_et"],
        "requested_through_utc": out["requested_through_utc"],
        "latest_returned_sample_utc": out["latest_returned_sample_utc"],
        "current": current,
        "checks": checks,
    }, indent=2), flush=True)
    if not out["all_five_checks_pass"]:
        raise SystemExit("Five-pass validation failed; dashboard must not be updated.")


if __name__ == "__main__":
    main()

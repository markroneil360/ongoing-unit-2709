#!/usr/bin/env python3
"""Read-only full-day R6E8A analysis for 2026-08-17 Detroit time.

Outputs HDF pressure/infrasound and EHZ vertical-motion context separately.
No dashboard files are modified.

Method compatibility for frequency classification:
- complete clock-aligned 60-second windows only
- Welch PSD, Hann, 8 s segments, 50% overlap
- dominant band = highest mean PSD among 1-4, 4-8, 8-16, 16-20 Hz
- gaps/missing minutes excluded, never zero-filled

Amplitude fields are raw-sensor 1-20 Hz band-limited RMS indices derived from PSD.
They are useful only for within-channel, adjacent-hour change description and are
NOT calibrated Pa/dB (HDF) or physical ground-motion units (EHZ).
"""
from __future__ import annotations

import io
import json
import math
import time
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
from obspy import UTCDateTime, read
from scipy.signal import welch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "r6e8a_2026-08-17_hourly.json"
BASE = "https://data.raspberryshake.org/fdsnws/dataselect/1/query"
TZ = ZoneInfo("America/Detroit")
UTC = timezone.utc
STATION = "AM.R6E8A.00"
LOCAL_START = datetime(2026, 8, 17, 0, 0, tzinfo=TZ)
LOCAL_END = datetime(2026, 8, 17, 23, 30, tzinfo=TZ)
START = LOCAL_START.astimezone(UTC)
END = LOCAL_END.astimezone(UTC)
BANDS = (("1-4", 1.0, 4.0), ("4-8", 4.0, 8.0),
         ("8-16", 8.0, 16.0), ("16-20", 16.0, 20.0))


def iso_z(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def http_bytes(url: str, tries: int = 4, timeout: int = 180) -> bytes | None:
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "r6e8a-hourly-analysis/1.0"})
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


def minute_metrics(x: np.ndarray, sr: float):
    nper = min(int(round(sr * 8.0)), len(x))
    nover = min(nper // 2, nper - 1)
    f, p = welch(x, fs=sr, window="hann", nperseg=nper,
                 noverlap=nover, detrend="constant", scaling="density")
    means = {}
    powers = {}
    for i, (name, lo, hi) in enumerate(BANDS):
        mask = (f >= lo) & ((f <= hi) if i == len(BANDS)-1 else (f < hi))
        vals = p[mask]
        ff = f[mask]
        means[name] = float(np.mean(vals)) if len(vals) else float("nan")
        powers[name] = float(np.trapz(vals, ff)) if len(vals) > 1 else 0.0
    winner = max(means, key=lambda k: -math.inf if not math.isfinite(means[k]) else means[k])
    mask20 = (f >= 1.0) & (f <= 20.0)
    ff20, pp20 = f[mask20], p[mask20]
    peak_hz = float(ff20[int(np.argmax(pp20))]) if len(pp20) else float("nan")
    total_power = float(np.trapz(pp20, ff20)) if len(pp20) > 1 else float("nan")
    rms_1_20 = math.sqrt(max(total_power, 0.0)) if math.isfinite(total_power) else float("nan")
    return {"dominant_band": winner, "band_mean_psd": means, "band_power": powers,
            "peak_hz": peak_hz, "rms_1_20_raw": rms_1_20}


def fetch_channel(channel: str):
    minutes = {}
    urls = []
    latest = None
    cur = START
    while cur < END:
        stop = min(cur + timedelta(hours=6), END)
        url = (f"{BASE}?net=AM&sta=R6E8A&loc=00&cha={channel}"
               f"&start={iso_z(cur)}&end={iso_z(stop)}&format=miniseed&nodata=404")
        urls.append(url)
        raw = http_bytes(url)
        if raw:
            st = read(io.BytesIO(raw))
            st.merge(method=0, fill_value=None)
            for tr in st:
                e = tr.stats.endtime.datetime.replace(tzinfo=UTC)
                latest = e if latest is None or e > latest else latest
            m = cur.replace(second=0, microsecond=0)
            while m < stop:
                got = extract_complete_minute(st, m)
                if got is not None:
                    x, sr = got
                    minutes[int(m.timestamp())] = minute_metrics(x, sr)
                m += timedelta(minutes=1)
        cur = stop
        time.sleep(0.5)
    return minutes, latest, urls


def expected_minutes_for_hour(hour: int) -> int:
    return 30 if hour == 23 else 60


def summarize_hourly(minutes: dict[int, dict]):
    grouped = defaultdict(list)
    for epoch, m in minutes.items():
        dt = datetime.fromtimestamp(epoch, UTC).astimezone(TZ)
        if dt.date().isoformat() != "2026-08-17":
            continue
        grouped[dt.hour].append((epoch, m))

    rows = []
    prev_rms = None
    for hour in range(24):
        arr = sorted(grouped.get(hour, []))
        expected = expected_minutes_for_hour(hour)
        if not arr:
            rows.append({
                "hour_et": f"{hour:02d}:00-{('23:30' if hour == 23 else f'{(hour+1)%24:02d}:00')}",
                "expected_minutes": expected, "valid_minutes": 0, "coverage_pct": 0.0,
                "dominant_band": None, "dominant_band_minutes": {}, "median_peak_hz": None,
                "band_power_share_pct": {}, "median_rms_1_20_raw": None,
                "max_rms_1_20_raw": None, "change_vs_prior_hour_pct": None,
            })
            prev_rms = None
            continue
        band_counts = Counter(m["dominant_band"] for _, m in arr)
        dominant = band_counts.most_common(1)[0][0]
        peaks = [m["peak_hz"] for _, m in arr if math.isfinite(m["peak_hz"])]
        rmses = [m["rms_1_20_raw"] for _, m in arr if math.isfinite(m["rms_1_20_raw"])]
        power_sums = {name: sum(m["band_power"][name] for _, m in arr if math.isfinite(m["band_power"][name])) for name, _, _ in BANDS}
        total_band_power = sum(power_sums.values())
        shares = {k: (100.0*v/total_band_power if total_band_power > 0 else None) for k, v in power_sums.items()}
        med_rms = float(np.median(rmses)) if rmses else None
        change = None
        if med_rms is not None and prev_rms is not None and prev_rms != 0:
            change = 100.0 * (med_rms - prev_rms) / prev_rms
        rows.append({
            "hour_et": f"{hour:02d}:00-{('23:30' if hour == 23 else f'{(hour+1)%24:02d}:00')}",
            "expected_minutes": expected,
            "valid_minutes": len(arr),
            "coverage_pct": round(100.0 * len(arr) / expected, 2),
            "dominant_band": dominant,
            "dominant_band_minutes": dict(band_counts),
            "median_peak_hz": round(float(np.median(peaks)), 3) if peaks else None,
            "band_power_share_pct": {k: (round(v, 2) if v is not None else None) for k, v in shares.items()},
            "median_rms_1_20_raw": med_rms,
            "max_rms_1_20_raw": max(rmses) if rmses else None,
            "change_vs_prior_hour_pct": round(change, 2) if change is not None else None,
        })
        prev_rms = med_rms
    return rows


def build_channel_summary(channel: str, minutes: dict[int, dict], latest, urls):
    counts = Counter(m["dominant_band"] for m in minutes.values())
    peaks = [m["peak_hz"] for m in minutes.values() if math.isfinite(m["peak_hz"])]
    rmses = [m["rms_1_20_raw"] for m in minutes.values() if math.isfinite(m["rms_1_20_raw"])]
    return {
        "channel": channel,
        "role": "pressure/infrasound" if channel == "HDF" else "vertical motion / seismic context",
        "latest_returned_sample_utc": latest.isoformat() if latest else None,
        "latest_returned_sample_et": latest.astimezone(TZ).isoformat() if latest else None,
        "valid_complete_minutes": len(minutes),
        "requested_minutes": 1410,
        "coverage_pct": round(100.0 * len(minutes) / 1410.0, 2),
        "dominant_band_minutes": dict(counts),
        "median_peak_hz": round(float(np.median(peaks)), 3) if peaks else None,
        "median_rms_1_20_raw": float(np.median(rmses)) if rmses else None,
        "hourly": summarize_hourly(minutes),
        "fdsn_urls": urls,
    }


def main():
    hdf, hdf_latest, hdf_urls = fetch_channel("HDF")
    ehz, ehz_latest, ehz_urls = fetch_channel("EHZ")
    hsum = build_channel_summary("HDF", hdf, hdf_latest, hdf_urls)
    esum = build_channel_summary("EHZ", ehz, ehz_latest, ehz_urls)

    # Five sanity gates.
    checks = []
    checks.append({
        "name": "1_time_bounds_and_unique_minutes",
        "pass": (len(hdf) == len(set(hdf)) and len(ehz) == len(set(ehz))
                 and all(int(START.timestamp()) <= t < int(END.timestamp()) for t in hdf)
                 and all(int(START.timestamp()) <= t < int(END.timestamp()) for t in ehz)),
        "observed": {"hdf_unique": len(hdf), "ehz_unique": len(ehz),
                     "start_utc": START.isoformat(), "end_utc": END.isoformat()},
    })
    allowed = {x[0] for x in BANDS}
    checks.append({
        "name": "2_frequency_classification_integrity",
        "pass": (all(m["dominant_band"] in allowed and 1.0 <= m["peak_hz"] <= 20.0 for m in hdf.values())
                 and all(m["dominant_band"] in allowed and 1.0 <= m["peak_hz"] <= 20.0 for m in ehz.values())),
        "observed": {"allowed_bands": sorted(allowed)}
    })
    h_hour_sum = sum(r["valid_minutes"] for r in hsum["hourly"])
    e_hour_sum = sum(r["valid_minutes"] for r in esum["hourly"])
    checks.append({
        "name": "3_hourly_reconciliation",
        "pass": h_hour_sum == len(hdf) and e_hour_sum == len(ehz),
        "observed": {"hdf_hourly_sum": h_hour_sum, "hdf_total": len(hdf),
                     "ehz_hourly_sum": e_hour_sum, "ehz_total": len(ehz)}
    })
    h48 = sum(1 for m in hdf.values() if m["dominant_band"] == "4-8")
    e48 = sum(1 for m in ehz.values() if m["dominant_band"] == "4-8")
    checks.append({
        "name": "4_band_count_reconciliation",
        "pass": h48 == hsum["dominant_band_minutes"].get("4-8", 0) and e48 == esum["dominant_band_minutes"].get("4-8", 0),
        "observed": {"hdf_4_8_direct": h48, "hdf_4_8_summary": hsum["dominant_band_minutes"].get("4-8", 0),
                     "ehz_4_8_direct": e48, "ehz_4_8_summary": esum["dominant_band_minutes"].get("4-8", 0)}
    })
    checks.append({
        "name": "5_channel_separation_and_edge",
        "pass": (hsum["channel"] == "HDF" and esum["channel"] == "EHZ"
                 and hdf_latest is not None and ehz_latest is not None
                 and hdf_latest <= END + timedelta(seconds=5)
                 and ehz_latest <= END + timedelta(seconds=5)),
        "observed": {"hdf_role": hsum["role"], "ehz_role": esum["role"],
                     "hdf_latest_et": hsum["latest_returned_sample_et"],
                     "ehz_latest_et": esum["latest_returned_sample_et"]}
    })

    out = {
        "schema_version": 1,
        "station": STATION,
        "generated_utc": datetime.now(UTC).isoformat(),
        "requested_window_et": {"start": LOCAL_START.isoformat(), "end": LOCAL_END.isoformat()},
        "requested_window_note": "Detroit is on EDT (UTC-4) on Aug. 17, 2026; user said EST colloquially.",
        "source": "Raspberry Shake public FDSN DataSelect",
        "method": {
            "minute_window": "clock-aligned complete 60-second windows; gaps excluded",
            "welch": "Hann; 8 s segments; 50% overlap; scipy.signal.welch",
            "dominant_band": "highest mean PSD among 1-4, 4-8, 8-16, 16-20 Hz",
            "peak_frequency": "maximum Welch PSD bin from 1-20 Hz; hourly value is median minute peak",
            "band_power_share": "integrated Welch PSD in each band divided by total integrated 1-20 Hz band power",
            "hourly_amplitude": "median minute 1-20 Hz band-limited RMS in raw sensor units",
            "increase_decrease": "percent change in hourly median raw 1-20 Hz RMS versus immediately preceding hour; descriptive only, not a benchmark",
            "missing": "excluded; never zero-filled or interpreted as quiet/normal/compliant",
            "calibration_boundary": "raw amplitude indices are not presented as Pa/dB for HDF or physical motion units for EHZ",
        },
        "HDF": hsum,
        "EHZ": esum,
        "checks": checks,
        "all_five_checks_pass": all(c["pass"] for c in checks),
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({"all_five_checks_pass": out["all_five_checks_pass"],
                      "HDF_latest_et": hsum["latest_returned_sample_et"],
                      "HDF_minutes": len(hdf), "HDF_band_counts": hsum["dominant_band_minutes"],
                      "EHZ_latest_et": esum["latest_returned_sample_et"],
                      "EHZ_minutes": len(ehz), "EHZ_band_counts": esum["dominant_band_minutes"],
                      "checks": checks}, indent=2))
    if not out["all_five_checks_pass"]:
        raise SystemExit("Five sanity gates failed; do not use this result.")


if __name__ == "__main__":
    main()

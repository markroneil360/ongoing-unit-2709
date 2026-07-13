#!/usr/bin/env python3
"""Recompute DOY102-109 daily statistics for HDF (primary) and EHZ (secondary)
from local MiniSEED, memory-safe (one file/day/channel at a time).

Method (matches dashboard "Methods"): decimate 100 -> 20 Hz, StationXML response
removal with 0.05/0.1/8/9 Hz cosine prefilter and 60 dB water level. HDF -> Pa,
EHZ -> m/s (reported µm/s). 60 s demeaned per-minute RMS; daily mean/median/peak/p95
are aggregates of those minute values. No interpolation; missing minutes are dropped.
"""
import hashlib, json, os, glob, sys
from datetime import date, timedelta
import numpy as np
from obspy import read, read_inventory, UTCDateTime

SRC = "/home/user/workspace/uploaded_attachments/aa8aa6fbb2e246dd8383886d5f55ea59"
DUP = "/home/user/workspace/uploaded_attachments/1dee1ee9f43f499e858a123549212eb1"
INV = read_inventory("/home/user/workspace/R6E8A_stationxml.xml")
DOYS = list(range(102, 110))            # 102..109
PREFILT = (0.05, 0.1, 8.0, 9.0)
BAND = "0.1-8 Hz"
TARGET_SR = 20.0
YEAR = 2026

def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def doy_to_date(doy):
    return date(YEAR, 1, 1) + timedelta(days=doy - 1)

def process(path, chan, day_start):
    """Return (minute_index->rms dict, peak_abs, peak_abs_time) for one day file."""
    st = read(path)
    st.merge(method=1, fill_value=None)   # keep gaps as masked, no interpolation
    tr = st[0]
    # decimate 100 -> 20 (factor 5) with anti-alias; handle masked arrays via split
    st = st.split()                        # contiguous segments only (no gap fill)
    minute_rms = {}                        # minute-of-day -> list of segment (sumsq,n)
    peak_abs = 0.0
    peak_time = None
    out = "VEL" if chan == "EHZ" else "DEF"
    for seg in st:
        if seg.stats.sampling_rate != 100.0:
            continue
        seg.detrend("demean")
        seg.decimate(int(round(seg.stats.sampling_rate / TARGET_SR)), no_filter=False)
        seg.remove_response(inventory=INV, output=out, pre_filt=PREFILT,
                            water_level=60.0, taper=True)
        data = seg.data.astype(np.float64)
        if chan == "EHZ":
            data = data * 1e6              # m/s -> µm/s
        sr = seg.stats.sampling_rate
        start = seg.stats.starttime
        # instantaneous peak (abs)
        idx = int(np.argmax(np.abs(data)))
        if abs(data[idx]) > peak_abs:
            peak_abs = float(abs(data[idx]))
            peak_time = start + idx / sr
        # per-minute binning by minute-of-day
        offs = start - day_start           # seconds from midnight
        sec = offs + np.arange(len(data)) / sr
        minute = np.floor(sec / 60.0).astype(int)
        # accumulate sum of squares per minute
        order = np.argsort(minute, kind="stable")
        minute_s = minute[order]; data_s = data[order]
        uniq, starts = np.unique(minute_s, return_index=True)
        splits = np.split(data_s, starts[1:])
        for m, arr in zip(uniq, splits):
            if m < 0 or m >= 1440:
                continue
            ss, n = float(np.sum(arr * arr)), int(arr.size)
            if m in minute_rms:
                minute_rms[m][0] += ss; minute_rms[m][1] += n
            else:
                minute_rms[m] = [ss, n]
    rms = {m: (v[0] / v[1]) ** 0.5 for m, v in minute_rms.items() if v[1] > 0}
    return rms, peak_abs, peak_time

def summarize(rms):
    vals = np.array(list(rms.values()), dtype=np.float64)
    obs = int(vals.size)
    if obs == 0:
        return dict(obs=0, coverage=0.0, mean=None, median=None, peak=None, p95=None)
    return dict(
        obs=obs,
        coverage=round(obs / 1440.0 * 100.0, 1),
        mean=round(float(np.mean(vals)), 4),
        median=round(float(np.median(vals)), 4),
        peak=round(float(np.max(vals)), 4),
        p95=round(float(np.percentile(vals, 95)), 4),
    )

def main():
    # --- dedup DOY109 by sha256 ---
    dedup = {}
    for chan in ("HDF", "EHZ"):
        a = os.path.join(SRC, f"AM.R6E8A.00.{chan}.D.{YEAR}.109")
        b = os.path.join(DUP, f"AM.R6E8A.00.{chan}.D.{YEAR}.109")
        ha, hb = sha256(a), sha256(b)
        dedup[chan] = dict(primary=a, dup=b, sha_primary=ha, sha_dup=hb,
                           identical=(ha == hb))

    result = {"channels": {}, "dedup_doy109": dedup, "band": BAND,
              "prefilt": PREFILT, "target_sr": TARGET_SR}
    per_minute_hdf = {}   # (doy)-> rms dict for event detection
    for chan in ("HDF", "EHZ"):
        days = []
        worst_inst = dict(value=0.0, time=None, doy=None)
        for doy in DOYS:
            path = os.path.join(SRC, f"AM.R6E8A.00.{chan}.D.{YEAR}.{doy}")
            d = doy_to_date(doy)
            day_start = UTCDateTime(f"{d.isoformat()}T00:00:00")
            if not os.path.exists(path):
                days.append(dict(doy=doy, date=d.isoformat(), status="gap",
                                 obs=None, coverage=None, mean=None, median=None,
                                 peak=None, p95=None))
                continue
            rms, pk, pkt = process(path, chan, day_start)
            s = summarize(rms)
            row = dict(doy=doy, date=d.isoformat(),
                       status=("source" if s["obs"] > 0 else "gap"), **s)
            days.append(row)
            if pk > worst_inst["value"]:
                worst_inst = dict(value=round(pk, 4),
                                  time=(pkt.isoformat() if pkt else None), doy=doy)
            if chan == "HDF":
                per_minute_hdf[doy] = (d, day_start, rms)
            sys.stderr.write(f"{chan} DOY{doy}: obs={s['obs']} peak={s['peak']}\n")
        result["channels"][chan] = dict(days=days, worst_instantaneous=worst_inst)

    # --- worst sustained event (HDF) ---
    # concat per-minute RMS across days into a continuous timeline
    all_minutes = []   # (utc_iso, doy, minute, value)
    flat = []
    for doy in DOYS:
        if doy not in per_minute_hdf:
            continue
        d, day_start, rms = per_minute_hdf[doy]
        for m, v in rms.items():
            flat.append((doy, m, v, (day_start + m * 60)))
    flat.sort(key=lambda x: (x[0], x[1]))
    vals = np.array([f[2] for f in flat], dtype=np.float64)
    med = float(np.median(vals))
    thresh = 2.0 * med                    # transparent: 2x the 8-day baseline median
    # maximal runs of consecutive minutes (contiguous in real time, <=90s gap)
    # above threshold; worst = longest sustained run (tie-break by peak).
    best = None
    i = 0
    n = len(flat)
    while i < n:
        if vals[i] >= thresh:
            j = i
            while j + 1 < n and vals[j + 1] >= thresh and \
                  (flat[j + 1][3] - flat[j][3]) <= 90:
                j += 1
            seg_vals = vals[i:j + 1]
            dur = int(j - i + 1)
            peak = float(np.max(seg_vals))
            evt = dict(start=flat[i][3].isoformat(), doy=int(flat[i][0]),
                       duration_min=dur, peak=round(peak, 4),
                       mean=round(float(np.mean(seg_vals)), 4))
            if best is None or dur > best["duration_min"] or \
               (dur == best["duration_min"] and peak > best["peak"]):
                best = evt
            i = j + 1
        else:
            i += 1
    result["channels"]["HDF"]["worst_sustained"] = dict(
        baseline_median=round(med, 4), threshold=round(thresh, 4),
        rule="contiguous minutes with per-minute RMS >= 2x 8-day median (<=90s gaps)",
        band=BAND, event=best)

    # day counts
    for chan in ("HDF", "EHZ"):
        src = [d for d in result["channels"][chan]["days"] if d["status"] == "source"]
        result["channels"][chan]["day_count"] = len(src)
    result["day_count_overall"] = len(DOYS)
    with open("/home/user/workspace/R6E8A_hist_computed.json", "w") as f:
        json.dump(result, f, indent=1)
    print(json.dumps(result, indent=1))

if __name__ == "__main__":
    main()

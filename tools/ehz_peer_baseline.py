#!/usr/bin/env python3
"""Build an external network-peer EHZ arithmetic-mean baseline for AM.R6E8A.00.

Metric-matched to the HDF peer baseline and fully independent of it (EHZ ground
velocity, not pressure):
  * Matched window: single UTC day 2026-04-18 (R6E8A DOY108, 100% coverage).
  * Metric: per-minute 60 s demeaned RMS of EHZ velocity in the 0.1-8 Hz band
    after per-station StationXML response removal (output VEL, m/s), reported in
    micrometres/second (um/s); decimated to 20 Hz.
  * Per station -> daily mean-of-per-minute-RMS (um/s) and daily peak minute.
  * Cross-station ARITHMETIC MEAN (one value per unique station, R6E8A excluded).

Station set: the SAME deterministic longitude-stratified public stations selected
for the HDF peer baseline (data/peer_baseline.json), using their EHZ channel.
Stations lacking a public EHZ channel on the matched day (e.g. infrasound-only
Boom units) are excluded and reported. This keeps the geographic stratification
identical and transparent while sampling the independent EHZ metric.
"""
import urllib.request, io, json, sys, time, datetime
import numpy as np
from obspy import read, read_inventory, UTCDateTime

ROOT = "/home/user/workspace/tremorlens-r6e8a-restored"
BASE = "https://data.raspberryshake.org/fdsnws"
HDF_BASELINE = f"{ROOT}/data/peer_baseline.json"
OUT = f"{ROOT}/data/ehz_peer_baseline.json"
LOG = f"{ROOT}/peer_cache/ehz_peer_run.log"

DAY = "2026-04-18"
SELF = "R6E8A"
PREFILT = (0.05, 0.1, 8, 9)
RMS_BAND = "0.1-8 Hz"
# R6E8A matched-day EHZ (um/s) from local reprocessing (DOY108).
R6E8A_MEAN = 7.60
R6E8A_PEAK = 19.53


def log(msg):
    line = f"[{datetime.datetime.now(datetime.timezone.utc).strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def http(url, timeout=120, tries=3):
    last = None
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ehz-peer/1.0"})
            return urllib.request.urlopen(req, timeout=timeout).read()
        except Exception as e:
            last = e
            code = getattr(e, "code", None)
            if code == 404:
                raise
            time.sleep(3 * (k + 1))
    raise last


def peer_station_meta():
    """Return {sta: (lat, lon)} for the HDF-baseline stations (valid + failed)."""
    p = json.load(open(HDF_BASELINE))
    meta = {}
    for x in p["peers"]:
        meta[x["sta"]] = (x["lat"], x["lon"])
    for s in p.get("failed_stations", []):
        meta.setdefault(s, (None, None))
    return meta


def daily_ehz(sta):
    """Return (daily_mean_umps, daily_peak_umps, n_minutes) or None."""
    ds = (f"{BASE}/dataselect/1/query?net=AM&sta={sta}&loc=00&cha=EHZ"
          f"&start={DAY}T00:00:00&end={DAY}T23:59:59&format=miniseed&nodata=404")
    try:
        raw = http(ds)
    except Exception:
        return None
    if not raw:
        return None
    try:
        st = read(io.BytesIO(raw))
        inv = read_inventory(io.BytesIO(http(
            f"{BASE}/station/1/query?net=AM&sta={sta}&loc=00&cha=EHZ&level=response")))
    except Exception:
        return None
    try:
        st.merge(method=0)
        st = st.split()
        st.detrend("demean")
        for tr in st:
            sr = tr.stats.sampling_rate
            factor = int(round(sr / 20.0))
            if factor >= 2:
                tr.decimate(factor, no_filter=False)
        st.remove_response(inventory=inv, output="VEL",
                           pre_filt=PREFILT, water_level=60)
    except Exception:
        return None
    mins = {}
    for tr in st:
        data = tr.data.astype("float64") * 1e6  # m/s -> um/s
        sr = tr.stats.sampling_rate
        n = int(round(sr * 60))
        if n <= 0:
            continue
        start = tr.stats.starttime
        for i in range(0, len(data), n):
            seg = data[i:i + n]
            if len(seg) < n * 0.5:
                continue
            seg = seg - seg.mean()
            key = int((start + i / sr).timestamp // 60)
            mins[key] = float(np.sqrt(np.mean(seg ** 2)))
    if not mins:
        return None
    vals = list(mins.values())
    return (float(np.mean(vals)), float(np.max(vals)), len(vals))


def main():
    open(LOG, "w").close()
    t0 = time.time()
    meta = peer_station_meta()
    order = sorted(meta.keys())
    log(f"EHZ peer candidates (reuse HDF-stratified set): {len(order)}")
    peers, failed = [], []
    for i, sta in enumerate(order):
        ts = time.time()
        r = daily_ehz(sta)
        if r is None:
            failed.append(sta)
            log(f"  [{i+1}/{len(order)}] {sta} no-EHZ/failed ({time.time()-ts:.0f}s)")
            continue
        mean_v, peak_v, nmin = r
        lat, lon = meta[sta]
        peers.append({"sta": sta, "lat": lat, "lon": lon,
                      "daily_mean_umps": round(mean_v, 5),
                      "daily_peak_umps": round(peak_v, 5), "minutes": nmin})
        log(f"  [{i+1}/{len(order)}] {sta} mean={mean_v:.3f} peak={peak_v:.3f} n={nmin} ({time.time()-ts:.0f}s)")

    means = sorted(p["daily_mean_umps"] for p in peers)
    peaks = sorted(p["daily_peak_umps"] for p in peers)

    def pct(vals, q):
        return round(float(np.percentile(vals, q)), 5) if vals else None

    def rank_of(vals, v):
        if not vals:
            return None
        below = sum(1 for x in vals if x < v)
        return round(100.0 * below / len(vals), 1)

    arith_mean = round(float(np.mean(means)), 5) if means else None
    result = {
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "kind": "external_network_peer_ehz_arithmetic_mean",
        "network": "AM (Raspberry Shake)",
        "channel": "EHZ",
        "units": "um/s",
        "matched_window_utc": DAY,
        "matched_window_note": (
            "Single UTC day 2026-04-18 (R6E8A DOY108). EHZ velocity, response-corrected, "
            "independent of the HDF baseline."),
        "metric": ("Per-minute 60 s demeaned RMS of EHZ velocity (um/s), then daily "
                   "mean-of-minutes and daily peak minute."),
        "rms_band": RMS_BAND,
        "response_removal": "Per-station StationXML, output VEL (m/s -> um/s), "
                            "pre_filt (0.05,0.1,8,9) Hz, water level 60, decimated to 20 Hz.",
        "selection_rule": (
            "Same deterministic longitude-stratified public AM stations selected for the "
            "HDF peer baseline (data/peer_baseline.json), using their EHZ channel. Stations "
            "without a public EHZ channel on the matched day are excluded and reported. "
            "R6E8A excluded; each station counted once."),
        "counts": {
            "reused_candidates": len(order),
            "valid_computed": len(peers),
            "excluded_no_ehz": len(failed),
        },
        "excluded_stations": failed,
        "peer_arithmetic_mean_umps": arith_mean,
        "peer_daily_mean_umps": {
            "n": len(means), "arithmetic_mean": arith_mean,
            "median": pct(means, 50), "p75": pct(means, 75),
            "p90": pct(means, 90), "p95": pct(means, 95), "p99": pct(means, 99),
            "min": means[0] if means else None, "max": means[-1] if means else None,
        },
        "peer_daily_peak_umps": {
            "n": len(peaks), "arithmetic_mean": round(float(np.mean(peaks)), 5) if peaks else None,
            "median": pct(peaks, 50), "p75": pct(peaks, 75),
            "p90": pct(peaks, 90), "p95": pct(peaks, 95), "p99": pct(peaks, 99),
            "min": peaks[0] if peaks else None, "max": peaks[-1] if peaks else None,
        },
        "r6e8a": {
            "matched_day_daily_mean_umps": R6E8A_MEAN,
            "matched_day_daily_peak_umps": R6E8A_PEAK,
            "mean_percent_vs_peer_mean": (round(100.0 * (R6E8A_MEAN - arith_mean) / arith_mean, 1)
                                          if arith_mean else None),
            "mean_percentile_vs_peers": rank_of(means, R6E8A_MEAN),
        },
        "peers": peers,
    }
    with open(OUT, "w") as f:
        json.dump(result, f, indent=1)
    log(f"WROTE {OUT}")
    log(f"EHZ peer arithmetic mean (um/s): {arith_mean}  N={len(means)}")
    log(f"total elapsed {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()

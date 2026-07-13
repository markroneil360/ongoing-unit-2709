#!/usr/bin/env python3
"""Build an external network-peer HDF percentile baseline for AM.R6E8A.00.

Metric-matched, transparent, reproducible:
  * Matched window: a single UTC day 2026-04-18 (R6E8A DOY108, 100% coverage).
  * Metric: per-minute 60 s demeaned RMS of HDF pressure (Pa) in the 0.1-8 Hz
    band after per-station StationXML response removal; decimated to 20 Hz.
  * Per station -> daily-mean-of-per-minute-RMS (Pa) and daily peak minute (Pa),
    exactly the aggregation R6E8A is measured on.
  * Cross-station distribution (ONE value per unique station, R6E8A excluded,
    no double-count) -> median, P75, P90, P95, P99.

Selection is deterministic and geographically stratified by longitude so the
sample is not "all worldwide" and is reproducible: candidates are every unique
public AM HDF station whose station epoch covers the matched day; each is
cheaply probed for data existence; available stations are bucketed into 12
longitude bands (30 deg) and, within each band, taken in ascending station-code
order up to a fixed per-band cap.
"""
import urllib.request, io, json, sys, time, datetime, math
import numpy as np
from obspy import read, read_inventory, UTCDateTime

ROOT = "/home/user/workspace/tremorlens-r6e8a-restored"
BASE = "https://data.raspberryshake.org/fdsnws"
STATIONS_TXT = f"{ROOT}/peer_cache/am_hdf_stations.txt"
OUT = f"{ROOT}/data/peer_baseline.json"
LOG = f"{ROOT}/peer_cache/peer_run.log"

DAY = "2026-04-18"
DAY_T0 = UTCDateTime(DAY + "T00:00:00")
SELF = "R6E8A"
PER_BAND_CAP = 5          # deterministic cap per 30-deg longitude band
BAND_WIDTH = 30           # degrees
PREFILT = (0.05, 0.1, 8, 9)
RMS_BAND = "0.1-8 Hz"


def log(msg):
    line = f"[{datetime.datetime.now(datetime.timezone.utc).strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def http(url, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": "peer-baseline/1.0"})
    return urllib.request.urlopen(req, timeout=timeout).read()


def parse_candidates():
    """Unique stations whose epoch covers the matched day; keep lat/lon."""
    rows = [l.split("|") for l in open(STATIONS_TXT).read().splitlines()
            if l.strip() and not l.startswith("#")]
    cand = {}
    for r in rows:
        net, sta, lat, lon, elev, site, start, end = r[:8]
        if sta == SELF:
            continue
        try:
            s = UTCDateTime(start)
            e = UTCDateTime(end) if end.strip() else UTCDateTime("2100-01-01")
        except Exception:
            continue
        if s <= DAY_T0 <= e:
            # keep first-seen lat/lon per station (deterministic: file order)
            cand.setdefault(sta, (float(lat), float(lon)))
    return cand


def has_data(sta):
    """Cheap existence probe: request 120 s of HDF; True if bytes returned."""
    url = (f"{BASE}/dataselect/1/query?net=AM&sta={sta}&loc=00&cha=HDF"
           f"&start={DAY}T00:00:00&end={DAY}T00:02:00&format=miniseed&nodata=404")
    try:
        raw = http(url, timeout=30)
        return bool(raw)
    except Exception:
        return False


def daily_hdf(sta):
    """Return (daily_mean_pa, daily_peak_pa, n_minutes) or None on failure."""
    ds = (f"{BASE}/dataselect/1/query?net=AM&sta={sta}&loc=00&cha=HDF"
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
            f"{BASE}/station/1/query?net=AM&sta={sta}&loc=00&cha=HDF&level=response")))
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
        st.remove_response(inventory=inv, output="DEF",
                           pre_filt=PREFILT, water_level=60)
    except Exception:
        return None
    mins = {}
    for tr in st:
        data = tr.data.astype("float64")
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
    t_start = time.time()
    cand = parse_candidates()
    log(f"candidates (unique AM HDF stations, epoch covers {DAY}, R6E8A excluded): {len(cand)}")

    # Phase 1: deterministic order (sorted station code), cheap existence probe.
    order = sorted(cand.keys())
    available = []   # (sta, lat, lon)
    for i, sta in enumerate(order):
        if has_data(sta):
            lat, lon = cand[sta]
            available.append((sta, lat, lon))
        if (i + 1) % 50 == 0:
            log(f"  probed {i+1}/{len(order)}  available so far: {len(available)}")
    log(f"available with data on {DAY}: {len(available)}")

    # Phase 2: stratify by 30-deg longitude band, deterministic pick.
    bands = {}
    for sta, lat, lon in available:
        b = int(math.floor((lon + 180) / BAND_WIDTH))
        bands.setdefault(b, []).append((sta, lat, lon))
    selected = []
    for b in sorted(bands):
        picks = sorted(bands[b])[:PER_BAND_CAP]
        selected.extend(picks)
    log(f"longitude bands populated: {len(bands)}; selected (cap {PER_BAND_CAP}/band): {len(selected)}")

    # Phase 3: compute daily HDF RMS for each selected station.
    peers = []
    failed = []
    for i, (sta, lat, lon) in enumerate(selected):
        ts = time.time()
        r = daily_hdf(sta)
        if r is None:
            failed.append(sta)
            log(f"  [{i+1}/{len(selected)}] {sta} FAILED ({time.time()-ts:.0f}s)")
            continue
        mean_pa, peak_pa, nmin = r
        peers.append({"sta": sta, "lat": round(lat, 3), "lon": round(lon, 3),
                      "daily_mean_pa": round(mean_pa, 5),
                      "daily_peak_pa": round(peak_pa, 5), "minutes": nmin})
        log(f"  [{i+1}/{len(selected)}] {sta} mean={mean_pa:.4f} peak={peak_pa:.4f} "
            f"n={nmin} ({time.time()-ts:.0f}s)")

    means = sorted(p["daily_mean_pa"] for p in peers)
    peaks = sorted(p["daily_peak_pa"] for p in peers)

    def pct(sorted_vals, q):
        if not sorted_vals:
            return None
        return round(float(np.percentile(sorted_vals, q)), 5)

    def rank_of(sorted_vals, v):
        if not sorted_vals:
            return None
        below = sum(1 for x in sorted_vals if x < v)
        return round(100.0 * below / len(sorted_vals), 1)

    R6E8A_MEAN = 0.1964   # 2026-04-18 daily-mean HDF RMS (Pa)
    R6E8A_PEAK = 1.2005   # 2026-04-18 daily-peak minute (Pa)

    result = {
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "kind": "external_network_peer_percentile",
        "network": "AM (Raspberry Shake)",
        "channel": "HDF",
        "matched_window_utc": DAY,
        "matched_window_note": (
            "Single UTC day 2026-04-18 (R6E8A DOY108, 100% coverage). Peers and "
            "R6E8A measured identically on this day."),
        "metric": ("Per-minute 60 s demeaned RMS of HDF pressure (Pa), then daily "
                   "mean-of-minutes and daily peak minute."),
        "rms_band": RMS_BAND,
        "response_removal": "Per-station StationXML, output DEF (pressure Pa), "
                            "pre_filt (0.05,0.1,8,9) Hz, water level 60, decimated to 20 Hz.",
        "selection_rule": (
            f"Every unique public AM HDF station whose station epoch covers {DAY} "
            f"(R6E8A excluded, multi-epoch stations de-duplicated) was probed for "
            f"data existence. Available stations were bucketed into {BAND_WIDTH}-degree "
            f"longitude bands and, within each band, taken in ascending station-code "
            f"order up to {PER_BAND_CAP} per band. Deterministic and reproducible."),
        "counts": {
            "candidates_epoch_covers_day": len(cand),
            "available_with_data": len(available),
            "selected": len(selected),
            "valid_computed": len(peers),
            "failed_retrieval": len(failed),
            "longitude_bands": len(bands),
        },
        "failed_stations": failed,
        "no_station_overlap": "R6E8A excluded; each station counted once.",
        "peer_daily_mean_pa": {
            "n": len(means),
            "median": pct(means, 50), "p75": pct(means, 75),
            "p90": pct(means, 90), "p95": pct(means, 95), "p99": pct(means, 99),
            "min": means[0] if means else None, "max": means[-1] if means else None,
        },
        "peer_daily_peak_pa": {
            "n": len(peaks),
            "median": pct(peaks, 50), "p75": pct(peaks, 75),
            "p90": pct(peaks, 90), "p95": pct(peaks, 95), "p99": pct(peaks, 99),
            "min": peaks[0] if peaks else None, "max": peaks[-1] if peaks else None,
        },
        "r6e8a": {
            "matched_day_daily_mean_pa": R6E8A_MEAN,
            "matched_day_daily_peak_pa": R6E8A_PEAK,
            "mean_percentile_vs_peers": rank_of(means, R6E8A_MEAN),
            "peak_percentile_vs_peers": rank_of(peaks, R6E8A_PEAK),
        },
        "peers": peers,
    }
    with open(OUT, "w") as f:
        json.dump(result, f, indent=1)
    log(f"WROTE {OUT}")
    log(f"peer daily-mean percentiles: {result['peer_daily_mean_pa']}")
    log(f"R6E8A placement: {result['r6e8a']}")
    log(f"total elapsed {time.time()-t_start:.0f}s")


if __name__ == "__main__":
    main()

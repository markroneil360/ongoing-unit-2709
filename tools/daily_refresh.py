#!/usr/bin/env python3
"""Daily derived-data refresh for the public GitHub Pages build.

Runs after the FDSN archive lag has cleared (workflow gates on 07:xx America/Detroit).
Produces ONLY derived assets — raw MiniSEED is streamed/processed and discarded:

  1. Fetches the most recent complete fixed window (07:00 ET -> 07:00 ET) for HDF+EHZ
     from FDSN, computes per-minute 60 s demeaned RMS (response-corrected), and merges
     the new day into data/minute_cache.json (dedup by date; no interpolation).
  2. Rebuilds data/events_embed.js (Top/Bottom-20 contiguous events vs channel peer mean).
  3. Regenerates the composite snapshot PNGs at the latest 07:00 ET cutoff.
  4. Writes data/daily_report.json (report window, generated/retrieved times, data-through).

Peer baselines are treated as slow-moving derived aggregates and are NOT refetched here;
regenerate them out-of-band with tools/peer_baseline.py + tools/ehz_peer_baseline.py.
"""
import io, os, json, time, datetime, urllib.request
from zoneinfo import ZoneInfo
import numpy as np
from obspy import read, read_inventory, UTCDateTime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INV_PATH = os.environ.get("R6E8A_STATIONXML", f"{ROOT}/data/R6E8A_stationxml.xml")
if not os.path.exists(INV_PATH):
    # fall back to network metadata if the XML is not vendored in the repo
    INV_PATH = None
CACHE = f"{ROOT}/data/minute_cache.json"
BASE = "https://data.raspberryshake.org/fdsnws"
TZ = ZoneInfo("America/Detroit")
PREFILT = (0.05, 0.1, 8, 9)

if INV_PATH:
    INV = read_inventory(INV_PATH)
else:
    INV = read_inventory(f"{BASE}/station/1/query?net=AM&sta=R6E8A&loc=00"
                         f"&cha=HDF,EHZ&level=response")

CFG = {"HDF": ("DEF", 1.0), "EHZ": ("VEL", 1e6)}


def http(url, timeout=180, tries=4):
    last = None
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "r6e8a-daily/1.0"})
            return urllib.request.urlopen(req, timeout=timeout).read()
        except Exception as e:
            last = e
            if getattr(e, "code", None) == 404:
                return None
            time.sleep(4 * (k + 1))
    raise last


def per_minute(chan, t0, t1):
    url = (f"{BASE}/dataselect/1/query?net=AM&sta=R6E8A&loc=00&cha={chan}"
           f"&start={t0.isoformat()}&end={t1.isoformat()}&format=miniseed&nodata=404")
    raw = http(url)
    if not raw:
        return {}, url
    st = read(io.BytesIO(raw))
    st.merge(method=0)
    st = st.split()
    st.detrend("demean")
    for tr in st:
        factor = int(round(tr.stats.sampling_rate / 20.0))
        if factor >= 2:
            tr.decimate(factor, no_filter=False)
    output, scale = CFG[chan]
    st.remove_response(inventory=INV, output=output, pre_filt=PREFILT, water_level=60)
    mins = {}
    for tr in st:
        data = tr.data.astype("float64") * scale
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
            key = int((start + i / sr).timestamp // 60) * 60
            mins[key] = float(np.sqrt(np.mean(seg ** 2)))
    return mins, url


def recs_from(mins):
    out = []
    for e in sorted(mins):
        dt = datetime.datetime.fromtimestamp(e, tz=datetime.timezone.utc)
        out.append({"utc": dt.strftime("%Y-%m-%dT%H:%M"),
                    "et": dt.astimezone(TZ).strftime("%Y-%m-%d %H:%M"),
                    "v": round(mins[e], 6)})
    return out


def latest_cutoff_utc():
    now_et = datetime.datetime.now(TZ)
    cutoff = now_et.replace(hour=7, minute=0, second=0, microsecond=0)
    if now_et < cutoff:
        cutoff -= datetime.timedelta(days=1)
    return cutoff


def main():
    cutoff_et = latest_cutoff_utc()
    win_start_et = cutoff_et - datetime.timedelta(days=1)  # 07:00 ET previous day
    t1 = UTCDateTime(cutoff_et.astimezone(datetime.timezone.utc))
    t0 = UTCDateTime(win_start_et.astimezone(datetime.timezone.utc))
    report_date = win_start_et.strftime("%Y-%m-%d")

    # ---- 1. per-minute for the report window, merge into cache ----
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {
        "generated_utc": None, "metric": "per-minute 60 s demeaned RMS, 0.1-8 Hz",
        "hdf_units": "Pa", "ehz_units": "um/s", "tz": "America/Detroit", "days": [],
        "gap_doys": []}
    prov_urls = {}
    day_entry = {"doy": int(win_start_et.strftime("%j")), "date": report_date,
                 "status": "source"}
    data_through = None
    for chan in ("HDF", "EHZ"):
        mins, url = per_minute(chan, t0, t1)
        prov_urls[chan] = url
        recs = recs_from(mins)
        if recs:
            through = max(r["et"] for r in recs)
            data_through = through if not data_through else max(data_through, through)
        day_entry[chan.lower()] = {
            "coverage_pct": round(100.0 * len(recs) / 1440.0, 1),
            "minutes": recs,
            "provenance": {"source": "fdsn_dataselect", "url": url,
                           "retrieved_utc": datetime.datetime.now(
                               datetime.timezone.utc).isoformat()}}
        time.sleep(1.5)
    # dedup by date
    cache["days"] = [d for d in cache["days"] if d.get("date") != report_date]
    cache["days"].append(day_entry)
    cache["days"].sort(key=lambda d: d["date"])
    cache["generated_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with open(CACHE, "w") as f:
        json.dump(cache, f, separators=(",", ":"))

    # ---- 2. rebuild events ----
    os.system(f"python3 {ROOT}/tools/build_events.py")

    # ---- 3. regenerate snapshots (best-effort) ----
    os.environ["R6E8A_SNAP_CUTOFF"] = cutoff_et.strftime("%Y-%m-%dT%H:%M")
    os.system(f"python3 {ROOT}/tools/make_snapshot.py")

    # ---- 4. daily report metadata ----
    report = {
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "report_window_et": {
            "start": win_start_et.strftime("%Y-%m-%d 07:00 %Z"),
            "end": cutoff_et.strftime("%Y-%m-%d 07:00 %Z")},
        "cutoff_rule": "Fixed 07:00 AM America/Detroit to 07:00 AM the next day.",
        "data_through_et": data_through,
        "retrieved_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "provenance_urls": prov_urls,
        "small_print": ("This archived 24-hour report uses a fixed 7:00 AM ET cutoff and "
                        "is generated after the Raspberry Shake archive delay; it is not a "
                        "real-time feed. The official DataView panel below provides the "
                        "closest available live view."),
        "attribution": ("Data powered by Raspberry Shake, S.A., a citizen-science project. "
                        "Please visit raspberryshake.org and join the Citizen Science "
                        "Community today! DOI: https://doi.org/10.7914/SN/AM"),
    }
    with open(f"{ROOT}/data/daily_report.json", "w") as f:
        json.dump(report, f, indent=1)
    print("daily_refresh done; report_date", report_date, "through", data_through)


if __name__ == "__main__":
    main()

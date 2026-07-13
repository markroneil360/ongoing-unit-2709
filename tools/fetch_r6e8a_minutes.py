#!/usr/bin/env python3
"""Build a derived per-minute RMS cache for AM.R6E8A.00 for every documented day,
both channels (HDF pressure Pa, EHZ velocity um/s), at one-minute resolution.

Requirement #3: process every available historical R6E8A day at one-minute RMS
resolution for BOTH channels. Uploaded MiniSEED is used when present; missing days
are fetched from FDSN one day/channel/request (rate-limited, chunked, memory-safe).
No interpolation; explicit gaps. Raw MiniSEED is NEVER written to the repo — it is
streamed/processed into derived summaries and discarded.

Output: data/minute_cache.json
  {
    "generated_utc": ...,
    "metric": "per-minute 60 s demeaned RMS, response-corrected, band 0.1-8 Hz",
    "hdf_units": "Pa", "ehz_units": "um/s",
    "tz": "America/Detroit",
    "days": [ {doy,date,status,source,provenance,
               hdf:{coverage_pct,minutes:[{utc,et,v}...]},
               ehz:{...}} ... ],
    "gap_doys": [...],
  }
"""
import io, json, time, datetime, hashlib, urllib.request
from zoneinfo import ZoneInfo
import numpy as np
from obspy import read, read_inventory, UTCDateTime

ROOT = "/home/user/workspace/tremorlens-r6e8a-restored"
WS = "/home/user/workspace"
UNIFIED = f"{ROOT}/data/unified_embed.js"
INV_PATH = f"{WS}/R6E8A_stationxml.xml"
UP = f"{WS}/uploaded_attachments/aa8aa6fbb2e246dd8383886d5f55ea59"
OUT = f"{ROOT}/data/minute_cache.json"
LOG = f"{ROOT}/peer_cache/minute_run.log"
BASE = "https://data.raspberryshake.org/fdsnws"

TZ = ZoneInfo("America/Detroit")
PREFILT = (0.05, 0.1, 8, 9)
SELF = "R6E8A"

INV = read_inventory(INV_PATH)


def log(msg):
    line = f"[{datetime.datetime.now(datetime.timezone.utc).strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def http(url, timeout=180, tries=4):
    last = None
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "r6e8a-minutes/1.0"})
            return urllib.request.urlopen(req, timeout=timeout).read()
        except Exception as e:
            last = e
            if getattr(e, "code", None) == 404:
                raise
            time.sleep(4 * (k + 1))
    raise last


def unified_days():
    s = open(UNIFIED).read()
    d = json.loads(s[s.find("{"):s.rfind("}") + 1])
    return d["days"]


def process_stream(st, chan):
    """Return {minute_utc_epoch: rms_value} for a stream. Units: Pa (HDF) or um/s (EHZ)."""
    st.merge(method=0)
    st = st.split()
    st.detrend("demean")
    for tr in st:
        sr = tr.stats.sampling_rate
        factor = int(round(sr / 20.0))
        if factor >= 2:
            tr.decimate(factor, no_filter=False)
    output = "VEL" if chan == "EHZ" else "DEF"
    st.remove_response(inventory=INV, output=output, pre_filt=PREFILT, water_level=60)
    scale = 1e6 if chan == "EHZ" else 1.0  # m/s -> um/s ; HDF already Pa
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
    return mins


def minutes_to_records(mins):
    recs = []
    for epoch in sorted(mins):
        dt = datetime.datetime.fromtimestamp(epoch, tz=datetime.timezone.utc)
        et = dt.astimezone(TZ)
        recs.append({
            "utc": dt.strftime("%Y-%m-%dT%H:%M"),
            "et": et.strftime("%Y-%m-%d %H:%M"),
            "v": round(mins[epoch], 6 if True else 6),
        })
    return recs


def uploaded_stream(chan, doy):
    path = f"{UP}/AM.{SELF}.00.{chan}.D.2026.{doy:03d}"
    raw = open(path, "rb").read()
    sha = hashlib.sha256(raw).hexdigest()
    st = read(io.BytesIO(raw))
    return st, {"source": "uploaded_miniseed", "file": path.split("/")[-1],
                "sha256": sha, "bytes": len(raw)}


def fdsn_stream(chan, date):
    url = (f"{BASE}/dataselect/1/query?net=AM&sta={SELF}&loc=00&cha={chan}"
           f"&start={date}T00:00:00&end={date}T23:59:59&format=miniseed&nodata=404")
    raw = http(url)
    if not raw:
        return None, None
    st = read(io.BytesIO(raw))
    return st, {"source": "fdsn_dataselect", "url": url,
                "retrieved_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "bytes": len(raw)}


def day_channel(status, chan, doy, date):
    """Return (records, coverage_pct, provenance) or (None,0,prov) on failure."""
    try:
        if status == "local":
            st, prov = uploaded_stream(chan, doy)
        else:
            st, prov = fdsn_stream(chan, date)
            if st is None:
                return None, 0.0, {"source": "fdsn_dataselect", "note": "no data"}
    except Exception as e:
        return None, 0.0, {"source": status, "note": f"retrieval failed: {e}"}
    try:
        mins = process_stream(st, chan)
    except Exception as e:
        return None, 0.0, {**prov, "note": f"process failed: {e}"}
    del st
    if not mins:
        return None, 0.0, {**prov, "note": "no minutes"}
    recs = minutes_to_records(mins)
    coverage = round(100.0 * len(recs) / 1440.0, 1)
    return recs, coverage, prov


def main():
    open(LOG, "w").close()
    t0 = time.time()
    days = unified_days()
    out_days = []
    gap_doys = []
    for x in days:
        doy, date, status = x["doy"], x["date"], x["status"]
        if status not in ("local", "source"):
            gap_doys.append(doy)
            out_days.append({"doy": doy, "date": date, "status": "gap",
                             "hdf": None, "ehz": None})
            log(f"DOY{doy} {date} GAP")
            continue
        entry = {"doy": doy, "date": date, "status": status}
        for chan in ("HDF", "EHZ"):
            ts = time.time()
            recs, cov, prov = day_channel(status, chan, doy, date)
            key = chan.lower()
            if recs is None:
                entry[key] = {"coverage_pct": 0.0, "minutes": [], "provenance": prov}
                log(f"DOY{doy} {chan} FAIL/none cov=0 ({time.time()-ts:.0f}s) {prov.get('note','')}")
            else:
                entry[key] = {"coverage_pct": cov, "minutes": recs, "provenance": prov}
                log(f"DOY{doy} {chan} n={len(recs)} cov={cov}% ({time.time()-ts:.0f}s)")
            if status == "source":
                time.sleep(1.5)  # be polite to FDSN
        out_days.append(entry)

    result = {
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "metric": "per-minute 60 s demeaned RMS, response-corrected, band 0.1-8 Hz, decimated 20 Hz",
        "hdf_units": "Pa", "ehz_units": "um/s", "tz": "America/Detroit",
        "prefilt_hz": list(PREFILT), "water_level": 60,
        "days": out_days, "gap_doys": gap_doys,
        "counts": {
            "documented": sum(1 for d in out_days if d["status"] in ("local", "source")),
            "gaps": len(gap_doys),
            "hdf_days_with_data": sum(1 for d in out_days if d.get("hdf") and d["hdf"]["minutes"]),
            "ehz_days_with_data": sum(1 for d in out_days if d.get("ehz") and d["ehz"]["minutes"]),
        },
    }
    with open(OUT, "w") as f:
        json.dump(result, f, separators=(",", ":"))
    log(f"WROTE {OUT}  counts={result['counts']}")
    log(f"total elapsed {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()

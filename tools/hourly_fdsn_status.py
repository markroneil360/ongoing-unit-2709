#!/usr/bin/env python3
"""Hourly public FDSN status for AM.R6E8A.

Fetches a short window ending 35 minutes before runtime, which is inside the
Raspberry Shake public FDSN archive. Raw MiniSEED is processed in memory only.
Writes data/current-status.json with channel continuity and latest sample time.
"""
import io, json, datetime, urllib.request
from zoneinfo import ZoneInfo
from obspy import read, UTCDateTime

BASE = "https://data.raspberryshake.org/fdsnws"
TZ = ZoneInfo("America/Detroit")
OUT = "data/current-status.json"


def fetch(chan, start, end):
    url = (f"{BASE}/dataselect/1/query?net=AM&sta=R6E8A&loc=00&cha={chan}"
           f"&start={start.isoformat()}&end={end.isoformat()}&format=miniseed&nodata=404")
    req = urllib.request.Request(url, headers={"User-Agent": "r6e8a-hourly-status/1.0"})
    try:
        raw = urllib.request.urlopen(req, timeout=120).read()
    except Exception as exc:
        return {"channel": chan, "ok": False, "error": str(exc), "url": url}
    st = read(io.BytesIO(raw))
    st.merge(method=0)
    traces = st.split()
    if not traces:
        return {"channel": chan, "ok": False, "error": "no traces", "url": url}
    starts = [tr.stats.starttime for tr in traces]
    ends = [tr.stats.endtime for tr in traces]
    observed = sum((tr.stats.endtime - tr.stats.starttime) + (1.0 / tr.stats.sampling_rate) for tr in traces)
    expected = float(end - start)
    coverage = min(100.0, 100.0 * observed / expected) if expected > 0 else 0.0
    latest = max(ends).datetime.replace(tzinfo=datetime.timezone.utc)
    return {
        "channel": chan,
        "ok": True,
        "coverage_pct": round(coverage, 3),
        "segments": len(traces),
        "latest_sample_utc": latest.isoformat(),
        "latest_sample_et": latest.astimezone(TZ).strftime("%Y-%m-%d %I:%M:%S %p %Z"),
        "url": url,
    }


def main():
    now = datetime.datetime.now(datetime.timezone.utc)
    end_dt = now - datetime.timedelta(minutes=35)
    start_dt = end_dt - datetime.timedelta(minutes=20)
    start = UTCDateTime(start_dt)
    end = UTCDateTime(end_dt)
    channels = {c: fetch(c, start, end) for c in ("HDF", "EHZ")}
    payload = {
        "station": "AM.R6E8A.00",
        "generated_utc": now.isoformat(),
        "generated_et": now.astimezone(TZ).strftime("%Y-%m-%d %I:%M:%S %p %Z"),
        "window_start_utc": start_dt.isoformat(),
        "window_end_utc": end_dt.isoformat(),
        "channels": channels,
        "source": "Raspberry Shake public FDSN DataSelect",
        "display_note": "*This Data may lag. Missing acquisition time is not scored as zero, quiet, normal, compliant, or below benchmark."
    }
    with open(OUT, "w") as f:
        json.dump(payload, f, indent=2)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

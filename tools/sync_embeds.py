#!/usr/bin/env python3
"""Enforce a single synchronized source.

1. Parse data/unified_embed.js (the canonical model).
2. Inject the analysis RMS passband (frequency band) into the worst-event
   objects so the UI can display it transparently.
3. Regenerate data/historical_embed.js and data/historical_daily.json as a
   faithful HDF projection of the unified `days` array, eliminating the stale
   contradictory local numbers (DOY102=1270 / DOY109=1440) that were left over.
"""
import json, re, io, datetime

ROOT = "/home/user/workspace/tremorlens-r6e8a-restored"
UEMBED = f"{ROOT}/data/unified_embed.js"
HEMBED = f"{ROOT}/data/historical_embed.js"
HJSON = f"{ROOT}/data/historical_daily.json"
BAND = "0.1–8 Hz"

raw = open(UEMBED).read()
m = re.match(r"\s*window\.__TREMORLENS_UNIFIED__\s*=\s*(\{.*\});\s*$", raw, re.S)
assert m, "could not parse unified_embed.js"
U = json.loads(m.group(1))

# 1) inject analysis frequency band into worst-event objects (idempotent)
for key in ("worst_hdf_instant", "worst_hdf_sustained",
            "worst_ehz_instant", "worst_ehz_sustained"):
    if isinstance(U.get(key), dict):
        U[key]["analysis_band"] = BAND

with open(UEMBED, "w") as f:
    f.write("window.__TREMORLENS_UNIFIED__ = " + json.dumps(U, separators=(", ", ": ")) + ";")

# 2) project unified days -> HDF historical schema
def status_map(s):
    return "source" if s in ("local", "source") else s  # local counts as observed

hist_days = []
for d in U["days"]:
    hist_days.append({
        "doy": d["doy"], "date": d["date"], "status": status_map(d["status"]),
        "provenance": d.get("provenance_source"),
        "obs": d["obs"], "coverage": d["coverage"],
        "mean": d["mean"], "median": d["median"],
        "peak": d["peak"], "p95": d["p95"],
    })

src = [d for d in hist_days if d["status"] == "source"]
gap = [d for d in hist_days if d["status"] == "gap"]
hist = {
    "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "synchronized_from": "unified_embed.js",
    "counts": {"days": len(hist_days), "source": len(src), "gap": len(gap)},
    "note": U.get("provenance_note") or (
        "<strong>Provenance.</strong> DOY 102–109 are computed directly from the "
        "uploaded full-rate MiniSEED (both HDF and EHZ; DOY109 is a partial day and its "
        "duplicate copy was SHA-256 de-duplicated). Remaining documented days are FDSN "
        "daily reconstructions. Gap days returned no source data and are never interpolated."),
    "method": ("Per-minute 60 s demeaned RMS of HDF pressure after StationXML response "
               "removal (uploaded full-rate decimated to 25 Hz, FDSN days to 20 Hz; "
               f"RMS passband {BAND}). No interpolation."),
    "band": BAND,
    "days": hist_days,
}
with open(HJSON, "w") as f:
    json.dump(hist, f, indent=1)
with open(HEMBED, "w") as f:
    f.write("window.__TREMORLENS_HIST__ = " + json.dumps(hist, separators=(", ", ": ")) + ";")

print("unified worst-event bands injected:",
      {k: U[k].get("analysis_band") for k in ("worst_hdf_instant", "worst_hdf_sustained")})
print("historical projection days:", len(hist_days),
      "source:", len(src), "gap:", len(gap))
print("local DOY102-109 in projection:")
for d in hist_days[:8]:
    print(" ", d["doy"], d["status"], d["obs"], d["coverage"], d["mean"], d["peak"])

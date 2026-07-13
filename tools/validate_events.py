#!/usr/bin/env python3
"""Data-integrity validation for the event build (requirement #8).

Checks, per channel:
  * no overlapping events within a list (top runs disjoint; bottom runs disjoint);
  * event durations match the start/end ET timestamps (duration_min == minutes span);
  * every TOP event's peak strictly ABOVE the channel aggregate mean;
  * every BOTTOM event's minimum strictly BELOW the channel aggregate mean;
  * percent_diff == ((extreme - mean)/mean)*100 (within rounding);
  * channel units kept separate (HDF Pa, EHZ um/s);
  * all documented days processed / gaps explicit (cache vs unified).

Exits non-zero on any failure.
"""
import json, sys, datetime

ROOT = "/home/user/workspace/tremorlens-r6e8a-restored"
EVENTS = f"{ROOT}/data/events_embed.js"
CACHE = f"{ROOT}/data/minute_cache.json"


def load_events():
    s = open(EVENTS).read()
    return json.loads(s[s.find("{"):s.rfind("}") + 1])


def et_to_min(et):
    return int(datetime.datetime.strptime(et, "%Y-%m-%d %H:%M").timestamp() // 60)


def main():
    ev = load_events()
    cache = json.load(open(CACHE))
    fails = []

    for ch, unit in (("hdf", "Pa"), ("ehz", "um/s")):
        b = ev[ch]
        mean = b["peer_mean"]
        if b["units"] != unit:
            fails.append(f"{ch}: units {b['units']} != {unit}")
        for kind in ("top", "bottom"):
            evs = b[kind]
            # duration vs timestamps
            for e in evs:
                span = et_to_min(e["end_et"]) - et_to_min(e["start_et"]) + 1
                if span != e["duration_min"]:
                    fails.append(f"{ch}/{kind} #{e['rank']}: duration {e['duration_min']} != span {span}")
                # formula
                calc = round((e["extreme"] - mean) / mean * 100.0, 2)
                if abs(calc - e["percent_diff"]) > 0.05:
                    fails.append(f"{ch}/{kind} #{e['rank']}: pct {e['percent_diff']} != calc {calc}")
                # direction
                if kind == "top" and not (e["extreme"] > mean):
                    fails.append(f"{ch}/top #{e['rank']}: peak {e['extreme']} not > mean {mean}")
                if kind == "bottom" and not (e["extreme"] < mean):
                    fails.append(f"{ch}/bottom #{e['rank']}: min {e['extreme']} not < mean {mean}")
            # non-overlap within list (by minute ranges)
            ranges = sorted((et_to_min(e["start_et"]), et_to_min(e["end_et"])) for e in evs)
            for i in range(1, len(ranges)):
                if ranges[i][0] <= ranges[i - 1][1]:
                    fails.append(f"{ch}/{kind}: overlap {ranges[i-1]} & {ranges[i]}")
            # ranking monotonic
            pcts = [e["percent_diff"] for e in evs]
            if kind == "top" and pcts != sorted(pcts, reverse=True):
                fails.append(f"{ch}/top: not ranked by % desc")
            if kind == "bottom" and pcts != sorted(pcts):
                fails.append(f"{ch}/bottom: not ranked by % asc")

    # ---- averages / segments / no-spike (requirement #4, #5) ----
    SEG_MIN = 360
    for ch, unit in (("hdf", "Pa"), ("ehz", "um/s")):
        b = ev[ch]
        mean = b["peer_mean"]
        a = b.get("averages")
        if not a:
            fails.append(f"{ch}: missing averages block")
            continue
        if a["units"] != unit:
            fails.append(f"{ch}/avg: units {a['units']} != {unit}")
        if abs(round(a["peer_mean"], 6) - round(mean, 6)) > 1e-6:
            fails.append(f"{ch}/avg: peer_mean {a['peer_mean']} != {mean}")
        no_spike_seen = []
        for d in a["days"]:
            dm = d["daily_mean"]
            # daily pct formula
            calc = round((dm - mean) / mean * 100.0, 2)
            if abs(calc - d["pct_vs_peer"]) > 0.05:
                fails.append(f"{ch}/avg {d['date']}: pct {d['pct_vs_peer']} != calc {calc}")
            # coverage_pct formula
            cov = round(d["minutes"] / 1440 * 100.0, 1)
            if abs(cov - d["coverage_pct"]) > 0.1:
                fails.append(f"{ch}/avg {d['date']}: coverage {d['coverage_pct']} != {cov}")
            # partial flag consistency
            if d["partial"] != (d["minutes"] < 1440):
                fails.append(f"{ch}/avg {d['date']}: partial flag inconsistent")
            # no_spike consistency
            if d["no_spike"] != (d["samples_above_mean"] == 0):
                fails.append(f"{ch}/avg {d['date']}: no_spike != (samples_above==0)")
            if d["no_spike"]:
                no_spike_seen.append(d["date"])
            # segment formulas + minute sums
            seg_minutes = 0
            for s in d["segments"]:
                seg_minutes += s["minutes"]
                if s["status"] == "gap":
                    if s["minutes"] != 0 or s["mean"] is not None:
                        fails.append(f"{ch}/avg {d['date']}/{s['name']}: gap seg not empty")
                    continue
                scalc = round((s["mean"] - mean) / mean * 100.0, 2)
                if abs(scalc - s["pct_vs_peer"]) > 0.05:
                    fails.append(f"{ch}/avg {d['date']}/{s['name']}: seg pct {s['pct_vs_peer']} != {scalc}")
                scov = round(s["minutes"] / SEG_MIN * 100.0, 1)
                if abs(scov - s["coverage_pct"]) > 0.1:
                    fails.append(f"{ch}/avg {d['date']}/{s['name']}: seg cov {s['coverage_pct']} != {scov}")
                exp_status = "full" if s["minutes"] >= SEG_MIN else "partial"
                if s["status"] != exp_status:
                    fails.append(f"{ch}/avg {d['date']}/{s['name']}: seg status {s['status']} != {exp_status}")
            if seg_minutes != d["minutes"]:
                fails.append(f"{ch}/avg {d['date']}: seg minute sum {seg_minutes} != day {d['minutes']}")
        # no_spike_count / dates consistency
        if a["no_spike_count"] != len(no_spike_seen):
            fails.append(f"{ch}/avg: no_spike_count {a['no_spike_count']} != {len(no_spike_seen)}")
        if sorted(a["no_spike_dates"]) != sorted(no_spike_seen):
            fails.append(f"{ch}/avg: no_spike_dates mismatch")
        if a["day_count"] != len(a["days"]):
            fails.append(f"{ch}/avg: day_count {a['day_count']} != {len(a['days'])}")
        # overall daily mean = arithmetic mean of daily means
        if a["days"]:
            om = round(sum(x["daily_mean"] for x in a["days"]) / len(a["days"]), 6)
            if abs(om - a["overall_daily_mean"]) > 1e-5:
                fails.append(f"{ch}/avg: overall_daily_mean {a['overall_daily_mean']} != {om}")

    # coverage: documented days & gaps explicit
    doc = [d for d in cache["days"] if d["status"] in ("local", "source")]
    gap = [d for d in cache["days"] if d["status"] == "gap"]
    if ev["coverage"]["documented_days"] != len(doc):
        fails.append(f"documented days {ev['coverage']['documented_days']} != cache {len(doc)}")
    if ev["coverage"]["gap_days"] != len(gap):
        fails.append(f"gap days {ev['coverage']['gap_days']} != cache {len(gap)}")

    print("HDF mean Pa:", ev["hdf"]["peer_mean"], "| EHZ mean um/s:", ev["ehz"]["peer_mean"])
    print("documented:", len(doc), "gaps:", len(gap))
    for ch in ("hdf", "ehz"):
        b = ev[ch]
        a = b["averages"]
        print(f"[{ch}] top={len(b['top'])} bottom={len(b['bottom'])} "
              f"minutes={b['counts']['minutes_total']} "
              f"avg_days={a['day_count']} overall_%={a['overall_pct_vs_peer']} "
              f"no_spike={a['no_spike_count']} {a['no_spike_dates']}")
    if fails:
        print("\nVALIDATION FAILS:")
        for f in fails:
            print("  -", f)
        sys.exit(1)
    print("\nVALIDATION: ALL CHECKS PASSED")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Detect Top/Bottom contiguous-minute events per channel vs the channel-specific
peer ARITHMETIC MEAN, and emit data/events_embed.js (window.__TREMORLENS_EVENTS__).

Event definition (requirement #4):
  * Metric: one-minute 60 s demeaned RMS, response-corrected, channel units, 0.1-8 Hz
    (from data/minute_cache.json).
  * TOP event  = maximal contiguous run of minutes strictly ABOVE the channel peer
    arithmetic mean. Ranked by max % above (event peak). No overlap/double-count.
  * BOTTOM event = maximal contiguous run of minutes strictly BELOW the channel peer
    arithmetic mean. Ranked by greatest % below (event minimum). No overlap.
  * "Contiguous" = consecutive one-minute samples with no missing minute between them
    (runs never span a data gap; they may span midnight between two fully-documented
    consecutive days).
  * percent_difference = ((value - peer_mean) / peer_mean) * 100.

Peer means: HDF from data/peer_baseline.json (arithmetic mean of 27 daily means, Pa);
EHZ from data/ehz_peer_baseline.json (peer_arithmetic_mean_umps, um/s).
"""
import json, datetime

ROOT = "/home/user/workspace/tremorlens-r6e8a-restored"
CACHE = f"{ROOT}/data/minute_cache.json"
HDF_PEER = f"{ROOT}/data/peer_baseline.json"
EHZ_PEER = f"{ROOT}/data/ehz_peer_baseline.json"
OUT = f"{ROOT}/data/events_embed.js"
TOPN = 20


def hdf_peer_mean():
    p = json.load(open(HDF_PEER))
    vals = [x["daily_mean_pa"] for x in p["peers"]]
    return round(sum(vals) / len(vals), 6), len(vals), p


def ehz_peer_mean():
    p = json.load(open(EHZ_PEER))
    return p["peer_arithmetic_mean_umps"], p["peer_daily_mean_umps"]["n"], p


def collect_minutes(days, chan):
    """Ordered list of (utc_epoch_min, et_label, date, status, value) across all days."""
    key = chan.lower()
    seq = []
    for d in days:
        ch = d.get(key)
        if not ch or not ch.get("minutes"):
            continue
        for m in ch["minutes"]:
            dt = datetime.datetime.strptime(m["utc"], "%Y-%m-%dT%H:%M").replace(
                tzinfo=datetime.timezone.utc)
            seq.append((int(dt.timestamp() // 60), m["et"], d["date"], d["status"],
                        m["v"], ch["provenance"].get("source", "")))
    seq.sort(key=lambda r: r[0])
    return seq


def find_runs(seq, peer_mean, direction):
    """direction 'above' or 'below'. Return list of event dicts (unranked)."""
    events = []
    i, n = 0, len(seq)
    while i < n:
        epoch, et, date, status, v, src = seq[i]
        cond = (v > peer_mean) if direction == "above" else (v < peer_mean)
        if not cond:
            i += 1
            continue
        # start a run; extend while consecutive minute AND condition holds
        run = [seq[i]]
        j = i + 1
        while j < n:
            pe = seq[j - 1][0]
            ce, cet, cdate, cstatus, cv, csrc = seq[j]
            if ce != pe + 1:  # gap in minutes -> break contiguity
                break
            cc = (cv > peer_mean) if direction == "above" else (cv < peer_mean)
            if not cc:
                break
            run.append(seq[j])
            j += 1
        vals = [r[4] for r in run]
        srcs = sorted(set(r[5] for r in run))
        ev_mean = sum(vals) / len(vals)
        if direction == "above":
            ext = max(vals)  # event peak
            pct = (ext - peer_mean) / peer_mean * 100.0
        else:
            ext = min(vals)  # event minimum
            pct = (ext - peer_mean) / peer_mean * 100.0  # negative
        events.append({
            "start_et": run[0][1], "end_et": run[-1][1],
            "date": run[0][2], "end_date": run[-1][2],
            "duration_min": len(run),
            "extreme": round(ext, 6),
            "event_mean": round(ev_mean, 6),
            "percent_diff": round(pct, 2),
            "status": run[0][3],
            "sources": srcs,
        })
        i = j
    return events


def rank(events, direction):
    if direction == "above":
        events.sort(key=lambda e: e["percent_diff"], reverse=True)  # most above first
    else:
        events.sort(key=lambda e: e["percent_diff"])  # most below (most negative) first
    for k, e in enumerate(events, 1):
        e["rank"] = k
    return events[:TOPN]


SEG_NAMES = ["00:00-06:00", "06:00-12:00", "12:00-18:00", "18:00-24:00"]
SEG_MINUTES = 360  # 6 h at one-minute resolution


def seg_index(et):
    """Quarter-day segment index from a local America/Detroit 'YYYY-MM-DD HH:MM' label."""
    hh = int(et.split(" ")[1].split(":")[0])
    return 0 if hh < 6 else 1 if hh < 12 else 2 if hh < 18 else 3


def channel_averages(seq, peer_mean, units):
    """Per LOCAL (America/Detroit) day + fixed quarter-day segment averages and
    objective no-spike classification. A 'no-spike day' = a documented local day with
    ZERO one-minute samples strictly above the channel peer arithmetic mean.
    Segments use the local ET label so DST is handled by the timestamps themselves."""
    days = {}
    for epoch, et, udate, status, v, src in seq:
        etd = et.split(" ")[0]
        rec = days.get(etd)
        if rec is None:
            rec = {"vals": [], "segs": [[], [], [], []], "srcs": set(), "status": set()}
            days[etd] = rec
        rec["vals"].append(v)
        rec["segs"][seg_index(et)].append(v)
        rec["srcs"].add(src)
        rec["status"].add(status)

    out_days, no_spike_dates = [], []
    for etd in sorted(days):
        rec = days[etd]
        vals = rec["vals"]
        n = len(vals)
        dmean = sum(vals) / n
        above = sum(1 for x in vals if x > peer_mean)
        no_spike = (above == 0)
        if no_spike:
            no_spike_dates.append(etd)
        segs = []
        for si, name in enumerate(SEG_NAMES):
            sv = rec["segs"][si]
            sn = len(sv)
            if sn:
                smean = sum(sv) / sn
                segs.append({"name": name, "mean": round(smean, 6),
                             "pct_vs_peer": round((smean - peer_mean) / peer_mean * 100.0, 2),
                             "minutes": sn, "coverage_pct": round(sn / SEG_MINUTES * 100.0, 1),
                             "status": "full" if sn >= SEG_MINUTES else "partial"})
            else:
                segs.append({"name": name, "mean": None, "pct_vs_peer": None,
                             "minutes": 0, "coverage_pct": 0.0, "status": "gap"})
        out_days.append({
            "date": etd, "minutes": n, "coverage_pct": round(n / 1440 * 100.0, 1),
            "partial": n < 1440,
            "daily_mean": round(dmean, 6),
            "pct_vs_peer": round((dmean - peer_mean) / peer_mean * 100.0, 2),
            "samples_above_mean": above, "no_spike": no_spike,
            "sources": sorted(rec["srcs"]),
            "segments": segs,
        })
    dmeans = [d["daily_mean"] for d in out_days]
    overall = sum(dmeans) / len(dmeans) if dmeans else None
    return {
        "peer_mean": round(peer_mean, 6), "units": units,
        "segment_names": SEG_NAMES,
        "day_count": len(out_days),
        "overall_daily_mean": round(overall, 6) if overall is not None else None,
        "overall_pct_vs_peer": round((overall - peer_mean) / peer_mean * 100.0, 2) if overall is not None else None,
        "no_spike_count": len(no_spike_dates),
        "no_spike_dates": no_spike_dates,
        "days": out_days,
    }


def channel_block(seq, peer_mean, units):
    top = rank(find_runs(seq, peer_mean, "above"), "above")
    bot = rank(find_runs(seq, peer_mean, "below"), "below")
    all_top = find_runs(seq, peer_mean, "above")
    all_bot = find_runs(seq, peer_mean, "below")
    return {
        "peer_mean": round(peer_mean, 6),
        "units": units,
        "top": top, "bottom": bot,
        "averages": channel_averages(seq, peer_mean, units),
        "counts": {
            "minutes_total": len(seq),
            "minutes_above": sum(1 for r in seq if r[4] > peer_mean),
            "minutes_below": sum(1 for r in seq if r[4] < peer_mean),
            "runs_above_total": len(all_top),
            "runs_below_total": len(all_bot),
        },
        "headline": {
            "highest_pct_above": top[0]["percent_diff"] if top else None,
            "lowest_pct_below": bot[0]["percent_diff"] if bot else None,
            "longest_top_min": max((e["duration_min"] for e in all_top), default=0),
            "longest_bottom_min": max((e["duration_min"] for e in all_bot), default=0),
        },
    }


def main():
    cache = json.load(open(CACHE))
    days = cache["days"]
    hmean, hN, _ = hdf_peer_mean()
    emean, eN, _ = ehz_peer_mean()

    hdf_seq = collect_minutes(days, "HDF")
    ehz_seq = collect_minutes(days, "EHZ")

    documented = [d for d in days if d["status"] in ("local", "source")]
    gaps = [d["doy"] for d in days if d["status"] == "gap"]
    doc_dates = sorted(d["date"] for d in documented)
    first_date = doc_dates[0] if doc_dates else None
    last_date = doc_dates[-1] if doc_dates else None

    result = {
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "definition": ("Contiguous one-minute intervals above/below the channel peer "
                       "arithmetic mean. TOP=above (ranked by max % above), "
                       "BOTTOM=below (ranked by greatest % below). No overlap; runs "
                       "never span a data gap. percent = ((value-mean)/mean)*100."),
        "metric": cache["metric"],
        "tz": cache["tz"],
        "peer_means": {"hdf_pa": hmean, "hdf_n": hN, "ehz_umps": emean, "ehz_n": eN},
        "coverage": {
            "documented_days": len(documented),
            "gap_days": len(gaps), "gap_doys": gaps,
            "first_documented_date": first_date,
            "last_documented_date": last_date,
            "hdf_days_with_minutes": sum(1 for d in documented if d.get("hdf") and d["hdf"]["minutes"]),
            "ehz_days_with_minutes": sum(1 for d in documented if d.get("ehz") and d["ehz"]["minutes"]),
        },
        "hdf": channel_block(hdf_seq, hmean, "Pa"),
        "ehz": channel_block(ehz_seq, emean, "um/s"),
    }
    with open(OUT, "w") as f:
        f.write("// Auto-generated by tools/build_events.py — do not edit by hand.\n")
        f.write("window.__TREMORLENS_EVENTS__ = ")
        json.dump(result, f, separators=(",", ":"))
        f.write(";\n")
    # console summary
    print("HDF peer mean Pa:", hmean, "N", hN)
    print("EHZ peer mean um/s:", emean, "N", eN)
    for ch in ("hdf", "ehz"):
        b = result[ch]
        a = b["averages"]
        print(f"[{ch}] top1 %={b['top'][0]['percent_diff'] if b['top'] else None} "
              f"minutes={b['counts']['minutes_total']} "
              f"longest_top={b['headline']['longest_top_min']} "
              f"avg_days={a['day_count']} overall_%={a['overall_pct_vs_peer']} "
              f"no_spike={a['no_spike_count']} {a['no_spike_dates']}")
    print("WROTE", OUT)


if __name__ == "__main__":
    main()

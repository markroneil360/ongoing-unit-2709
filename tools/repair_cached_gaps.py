#!/usr/bin/env python3
"""Repair two confirmed historical gaps without restarting archive acquisition."""
from __future__ import annotations

import hashlib
import inspect
import io
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import fdsn_tail_cache as cache

EXPECTED_PAYLOAD = "056850623a17341a2bc2dfdbf9282d11684ce7e4e5b9486bc1d68d8da95daa8b"
PREFIX_END = datetime(2026, 9, 22, 23, 29, tzinfo=timezone.utc)
GAPS = (("2026-09-09T21:52:00+00:00", "2026-09-10T01:13:00+00:00"),
        ("2026-09-10T01:47:00+00:00", "2026-09-10T07:13:00+00:00"))
EXPECTED_RECOVERY = 527
PENDING = "targeted_repair_pending"
ROOT = Path(__file__).resolve().parents[1]


def _hash_minutes(minutes):
    return hashlib.sha256(cache._bytes([[t, minutes[t]] for t in sorted(minutes)])).hexdigest()


def _targets():
    return {t for a, b in GAPS for t in range(int(cache._bound(a).timestamp()),
                                             int(cache._bound(b).timestamp()), 60)}


def repair(cache_path, base_path, prefix_path, report_path, *, calc):
    """Patch only the named missing keys; return only after full prefix equality.

    Progress is saved on failure, but a pending-conflict marker prevents the
    ordinary acquisition helper from using it for publication until this exact
    repair verifies successfully. Existing accepted minutes are never replaced.
    """
    cache_path, base_path, prefix_path, report_path = map(
        Path, (cache_path, base_path, prefix_path, report_path))
    doc = json.loads(cache_path.read_bytes())
    base_raw = base_path.read_bytes()
    bdoc = json.loads(base_raw)
    old = json.loads(prefix_path.read_bytes())
    start = cache._bound(bdoc["end_exclusive_utc"])
    through = cache._bound(doc["processed_through_utc"])
    target = _targets()
    if len(target) != EXPECTED_RECOVERY:
        raise cache.CacheError("Confirmed repair plan does not contain exactly 527 minutes")
    fingerprint = {"method": bdoc["method"], "bands": [list(b) for b in calc.BANDS],
                   "complete_sha256": hashlib.sha256(inspect.getsource(calc.complete).encode()).hexdigest(),
                   "classify_sha256": hashlib.sha256(inspect.getsource(calc.classify).encode()).hexdigest(),
                   "versions": cache._versions(), "base_sha256": hashlib.sha256(base_raw).hexdigest()}
    if (doc.get("payload_sha256") != cache.payload_hash(doc)
            or doc.get("schema_version") != cache.SCHEMA or doc.get("station") != cache.STATION
            or doc.get("endpoint") != cache.ENDPOINT or cache._bound(doc["start_utc"]) != start
            or doc.get("method") != fingerprint
            or doc.get("method_fingerprint") != hashlib.sha256(cache._bytes(fingerprint)).hexdigest()):
        raise cache.CacheError("Initial cache identity, method, base, bounds, or hash mismatch")
    minutes = cache._minute_map(doc["minutes"], start, through, {b[0] for b in calc.BANDS})
    if doc.get("minute_count") != len(minutes) or through <= PREFIX_END:
        raise cache.CacheError("Initial cache count or retained-prefix scope mismatch")
    if (old.get("station") != "AM.R6E8A.00" or old.get("channel") != "HDF"
            or old.get("all_five_checks_pass") is not True
            or len(old.get("checks", [])) != 5
            or not all(c.get("pass") is True for c in old["checks"])
            or cache._bound(old["requested_through_utc"]) != PREFIX_END
            or cache._bound(old["latest_complete_analyzed_minute_utc"]) + timedelta(minutes=1) != PREFIX_END):
        raise cache.CacheError("Retained September 22 prefix checkpoint is not the required verified record")
    prior = {t: band for t, band in minutes.items() if t not in target}
    state = doc.get("targeted_gap_repair")
    if state is None:
        if doc["payload_sha256"] != EXPECTED_PAYLOAD or target & minutes.keys() or doc.get("conflicts"):
            raise cache.CacheError("Repair must start from the exact confirmed cache with all 527 keys absent")
        state = {"input_payload_sha256": EXPECTED_PAYLOAD,
                 "gaps_utc": [list(g) for g in GAPS], "original_minute_count": len(minutes),
                 "original_minutes_sha256": _hash_minutes(prior),
                 "original_processed_through_utc": cache._iso(through), "verified": False}
        doc["targeted_gap_repair"] = state
    else:
        if (state.get("input_payload_sha256") != EXPECTED_PAYLOAD
                or state.get("gaps_utc") != [list(g) for g in GAPS]
                or state.get("original_minutes_sha256") != _hash_minutes(prior)
                or state.get("original_processed_through_utc") != cache._iso(through)
                or len(prior) != state.get("original_minute_count")):
            raise cache.CacheError("Partial repair no longer preserves the original evidence")
    if any(c.get("kind") != PENDING for c in doc.get("conflicts", [])):
        raise cache.CacheConflict("An unresolved source-band conflict prevents targeted repair")
    doc["conflicts"] = [{"kind": PENDING,
                         "reason": "Publication blocked until 527 minutes and the retained prefix reconcile"}]
    report = {"purpose": "Targeted recovery of two confirmed cached-data omissions",
              "publication_allowed": False, "input_payload_sha256": EXPECTED_PAYLOAD,
              "gaps_utc": [list(g) for g in GAPS], "expected_recovered_minutes": EXPECTED_RECOVERY,
              "original_processed_through_utc": cache._iso(through), "requests": [], "all_checks_pass": False}

    def save():
        cache._atomic_save(cache_path, doc, minutes)
        report["current_payload_sha256"] = doc["payload_sha256"]
        report["recovered_target_minutes"] = len(target & minutes.keys())
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2) + "\n")

    save()
    queries = []
    for lo, hi in GAPS:
        a, b = cache._bound(lo), cache._bound(hi)
        if not any(t not in minutes for t in range(int(a.timestamp()), int(b.timestamp()), 60)):
            continue
        q0, q1 = a - timedelta(minutes=1), b + timedelta(minutes=1)
        if (q1 - q0).total_seconds() > cache.CHUNK_SECONDS:
            raise cache.CacheError("Targeted request exceeds six hours")
        if int(q0.timestamp()) not in prior or int(b.timestamp()) not in prior:
            raise cache.CacheError("A confirmed good minute must bound both sides of each repaired gap")
        queries.append((a, b, q0, q1, cache._url(q0, q1)))
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending = [pool.submit(calc.http, q[4]) for q in queries]
            for query, future in zip(queries, pending):
                a, b, q0, q1, url = query
                raw = future.result()
                receipt = {"start_utc": cache._iso(q0), "end_exclusive_utc": cache._iso(q1),
                           "owned_gap_start_utc": cache._iso(a), "owned_gap_end_utc": cache._iso(b),
                           "url": url, "raw_sha256": hashlib.sha256(raw).hexdigest() if raw else None,
                           "raw_bytes": len(raw or b""), "retrieved_utc": datetime.now(timezone.utc).isoformat(),
                           "targeted_gap_repair": True, "status": "processing"}
                report["requests"].append(receipt)
                if not raw:
                    raise cache.CacheError("Targeted FDSN query returned no data")
                stream = calc.read(io.BytesIO(raw))
                receipt["identities"] = sorted({tr.id for tr in stream})
                if receipt["identities"] != [cache.STATION]:
                    raise cache.CacheError("Targeted response has an unexpected station or channel")
                stream.merge(method=0, fill_value=None)
                fresh = {}
                m = q0
                while m < q1:
                    got = calc.complete(stream, m)
                    if got is not None:
                        band = calc.classify(*got)
                        if band not in {x[0] for x in calc.BANDS}:
                            raise cache.CacheError("Targeted classification returned an unknown band")
                        fresh[int(m.timestamp())] = band
                    m += timedelta(minutes=1)
                conflicts = [{"kind": "source_band_conflict", "epoch": t,
                              "cached_band": minutes[t], "returned_band": band}
                             for t, band in fresh.items() if t in minutes and minutes[t] != band]
                if conflicts:
                    doc["conflicts"].extend(conflicts)
                    receipt["status"] = "conflict_rejected"
                    doc["chunks"].append(dict(receipt))
                    raise cache.CacheConflict("Targeted response conflicts with retained accepted minutes")
                if any(t not in fresh for t in (int(q0.timestamp()), int(b.timestamp()))):
                    raise cache.CacheError("Targeted response did not reproduce both good overlap minutes")
                added = {t: band for t, band in fresh.items() if t not in minutes}
                if not added.keys() <= target:
                    raise cache.CacheError("Targeted response would add a minute outside the approved gaps")
                omitted = [t for t in minutes if q0.timestamp() <= t < q1.timestamp() and t not in fresh]
                minutes.update(added)
                receipt.update({"status": "processed", "accepted_minutes": len(fresh),
                                "added_minutes": len(added), "omitted_cached_minutes": sorted(omitted),
                                "excluded_minutes": [t for t in range(int(q0.timestamp()), int(q1.timestamp()), 60)
                                                     if t not in minutes]})
                doc["chunks"].append(dict(receipt))
                save()
                print(json.dumps({"targeted_gap_end_utc": cache._iso(b), "added_minutes": len(added),
                                  "total_recovered_target_minutes": len(target & minutes.keys())}), flush=True)
        if len(target & minutes.keys()) != EXPECTED_RECOVERY:
            raise cache.CacheError("All 527 confirmed missing minutes were not recovered")
        if (_hash_minutes({t: v for t, v in minutes.items() if t not in target}) != state["original_minutes_sha256"]
                or len(minutes) != state["original_minute_count"] + EXPECTED_RECOVERY
                or cache._bound(doc["processed_through_utc"]) != through):
            raise cache.CacheError("Repair changed pre-existing evidence or its saved cutoff")
        prefix = {t: band for t, band in minutes.items() if t < int(PREFIX_END.timestamp())}
        observed, _ = calc.combine(bdoc["base"], prefix)
        report["prefix_expected"] = old["current"]
        report["prefix_recomputed"] = observed
        report["prefix_exact_match"] = observed == old["current"]
        if observed != old["current"]:
            raise cache.CacheError("Repaired September 22 prefix does not exactly reproduce every retained field")
        state["verified"] = True
        state["recovered_minutes"] = EXPECTED_RECOVERY
        doc["conflicts"] = []
        report["all_checks_pass"] = True
        save()
        return report
    except Exception as exc:
        report["error"] = str(exc)
        save()
        raise


def main():
    import refresh_4_8_10min_current as calc
    report = repair(ROOT / "data/r6e8a_4_8_tail_minutes.json",
                    ROOT / "data/r6e8a_4_8_base_10min_2026-08-12.json",
                    ROOT / "data/r6e8a-sep22-prefix-checkpoint.json",
                    ROOT / "data/r6e8a-targeted-gap-repair.json", calc=calc)
    print(json.dumps({"gap_repair_pass": report["all_checks_pass"],
                      "recovered_minutes": report["recovered_target_minutes"],
                      "retained_prefix_exact_match": report["prefix_exact_match"]}), flush=True)
    # Only the trailing cached grid chunk and new current edge are fetched here.
    # All original complete/classify/statistics functions and five gates remain.
    calc.main()


if __name__ == "__main__":
    main()

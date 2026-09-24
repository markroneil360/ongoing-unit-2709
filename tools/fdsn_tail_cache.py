#!/usr/bin/env python3
"""Resumable FDSN minute acquisition; publication still requires the caller's gates.

``fetch`` retains the original (minutes, latest_sample, URLs) return shape. Pass
the existing complete/classify callbacks unchanged. ``metadata`` reports the
effective requested cutoff when an optional, one-time catch-up is requested.
The cache contains derived minute classifications and response receipts, never
raw MiniSEED. A cache checkpoint is not a publishable calculation candidate.
"""
from __future__ import annotations

import hashlib
import inspect
import io
import json
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

STATION = "AM.R6E8A.00.HDF"
ENDPOINT = "https://data.raspberryshake.org/fdsnws/dataselect/1/query"
SCHEMA = 1
CHUNK_SECONDS = 6 * 3600
ROOT = Path(__file__).resolve().parents[1]


class CacheError(RuntimeError):
    """Cache or source evidence cannot be safely reused."""


class CacheConflict(CacheError):
    """An accepted minute disagrees with previously retained evidence."""


def _bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def payload_hash(doc):
    return hashlib.sha256(_bytes({k: v for k, v in doc.items()
                                 if k != "payload_sha256"})).hexdigest()


def _utc(value):
    if not isinstance(value, datetime):
        value = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if value.tzinfo is None or value.utcoffset() is None:
        raise CacheError("UTC bounds must be timezone-aware")
    return value.astimezone(timezone.utc)


def _iso(value):
    return _utc(value).isoformat()


def _bound(value):
    value = _utc(value)
    if value.second or value.microsecond:
        raise CacheError("Request bounds must be complete clock-minute boundaries")
    return value


def _versions():
    out = {}
    for package in ("obspy", "numpy", "scipy"):
        try:
            out[package] = version(package)
        except PackageNotFoundError:
            out[package] = None
    return out


def _atomic_save(path, doc, minutes):
    doc["minutes"] = [[t, minutes[t]] for t in sorted(minutes)]
    doc["minute_count"] = len(minutes)
    doc["saved_utc"] = datetime.now(timezone.utc).isoformat()
    doc["payload_sha256"] = payload_hash(doc)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=path.parent,
                                         prefix=path.name + ".", delete=False) as f:
            temporary = f.name
            f.write(_bytes(doc) + b"\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def _minute_map(rows, start, end, allowed):
    if not isinstance(rows, list):
        raise CacheError("Minute payload must be a list")
    out = {}
    previous = None
    lo, hi = int(start.timestamp()), int(end.timestamp())
    for row in rows:
        if not isinstance(row, list) or len(row) != 2:
            raise CacheError("Malformed minute row")
        t, band = row
        if type(t) is not int or t % 60 or not lo <= t < hi:
            raise CacheError("Minute timestamp outside the declared clock-minute scope")
        if previous is not None and t <= previous:
            raise CacheError("Minute rows must be strictly ordered and unique")
        if band not in allowed:
            raise CacheError("Unknown frequency band")
        out[t] = band
        previous = t
    return out


def _url(start, end):
    stamp = lambda d: d.strftime("%Y-%m-%dT%H:%M:%SZ")
    return (f"{ENDPOINT}?net=AM&sta=R6E8A&loc=00&cha=HDF"
            f"&start={stamp(start)}&end={stamp(end)}&format=miniseed&nodata=404")


def _seed(doc, *, report_path, minute_path, start, end, method, allowed,
          versions, verify):
    raw = minute_path.read_bytes()
    report = json.loads(report_path.read_bytes())
    seed = json.loads(raw)
    digest = hashlib.sha256(raw).hexdigest()
    if (report.get("diagnostic_complete") is not True
            or report.get("all_preview_fields_match") is not True
            or report.get("error")
            or report.get("minute_file_sha256") != digest):
        raise CacheError("Diagnostic seed is incomplete, failed, or hash-mismatched")
    if report.get("station") != STATION or seed.get("station") != STATION:
        raise CacheError("Diagnostic seed station mismatch")
    stop = _bound(seed["end_exclusive_utc"])
    if (_bound(seed["start_utc"]) != start or stop > end or stop <= start
            or _bound(report["start_utc"]) != start
            or _bound(report["end_exclusive_utc"]) != stop
            or seed.get("method") != method):
        raise CacheError("Diagnostic seed method or bounds mismatch")
    if any(report.get("versions", {}).get(k) != v for k, v in versions.items()):
        raise CacheError("Diagnostic seed numerical-library versions mismatch")
    minutes = _minute_map(seed.get("minutes"), start, stop, allowed)
    if len(minutes) != int((stop - start).total_seconds() / 60):
        raise CacheError("The verified checkpoint seed must cover every complete minute")
    if verify is None or verify(dict(minutes)) is not True:
        raise CacheError("Independent checkpoint recomputation did not validate the seed")
    cursor = start
    receipts = []
    for item in report.get("chunks", []):
        a, b = _bound(item["start_utc"]), _bound(item["end_utc"])
        digest_raw = item.get("sha256", "")
        if (a != cursor or not a < b <= stop
                or (b - a).total_seconds() > CHUNK_SECONDS
                or item.get("identities") != [STATION]
                or item.get("url") != _url(a, b)
                or len(digest_raw) != 64
                or any(c not in "0123456789abcdef" for c in digest_raw)):
            raise CacheError("Diagnostic seed source receipts do not cover the exact scope")
        receipts.append({"start_utc": _iso(a), "end_exclusive_utc": _iso(b),
                         "url": item["url"], "raw_sha256": digest_raw,
                         "raw_bytes": item["bytes"], "identities": [STATION],
                         "accepted_minutes": item["classified_minutes"],
                         "status": "verified_diagnostic_seed"})
        cursor = b
    if cursor != stop:
        raise CacheError("Diagnostic seed is missing retrieval receipts")
    doc["seed"] = {"minute_file_sha256": digest,
                   "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
                   "independent_checkpoint_recomputed": True}
    doc["chunks"] = receipts
    doc["processed_through_utc"] = _iso(stop)
    return minutes


def fetch(start, end, *, complete, classify, http, read, method, bands,
          cache_path=ROOT / "data/r6e8a_4_8_tail_minutes.json",
          seed_report=None, seed_minutes=None, seed_verify=None, metadata=None,
          catch_up_end=None, versions=None, base_sha256=None):
    """Fetch, checkpoint, and return a full tail for the unchanged five gates.

    The optional seed verifier must independently recompute the retained preview
    statistics from the supplied minute map. ``catch_up_end`` is called at most
    once after the initial target is processed; set it to a current minus lag
    clock-minute function. Read the resulting cutoff from ``metadata``.

    Successful no-data/partial responses are explicit excluded acquisition time.
    Resume refetches the final grid chunk, making recent gaps retryable. Older
    exclusions remain documented; this function does not invent their samples.
    """
    start, end = _bound(start), _bound(end)
    if end <= start:
        raise CacheError("Requested end must be after the fixed tail start")
    path = Path(cache_path)
    allowed = {b[0] for b in bands}
    versions = _versions() if versions is None else dict(versions)
    fingerprint = {"method": method, "bands": [list(b) for b in bands],
                   "complete_sha256": hashlib.sha256(inspect.getsource(complete).encode()).hexdigest(),
                   "classify_sha256": hashlib.sha256(inspect.getsource(classify).encode()).hexdigest(),
                   "versions": versions, "base_sha256": base_sha256}
    fingerprint_hash = hashlib.sha256(_bytes(fingerprint)).hexdigest()
    if path.exists():
        doc = json.loads(path.read_bytes())
        if (doc.get("payload_sha256") != payload_hash(doc)
                or doc.get("schema_version") != SCHEMA or doc.get("station") != STATION
                or doc.get("endpoint") != ENDPOINT or doc.get("method") != fingerprint
                or doc.get("method_fingerprint") != fingerprint_hash
                or _bound(doc["start_utc"]) != start):
            raise CacheError("Cache schema, identity, method, start, or payload hash mismatch")
        through = _bound(doc["processed_through_utc"])
        if not start <= through <= end:
            raise CacheError("Cache cutoff is outside this monotonic refresh request")
        minutes = _minute_map(doc.get("minutes"), start, through, allowed)
        if doc.get("minute_count") != len(minutes):
            raise CacheError("Cache minute count mismatch")
        if doc.get("conflicts"):
            raise CacheConflict("Cache contains an unresolved source-band conflict")
    else:
        doc = {"schema_version": SCHEMA, "station": STATION, "endpoint": ENDPOINT,
               "start_utc": _iso(start), "processed_through_utc": _iso(start),
               "method": fingerprint, "method_fingerprint": fingerprint_hash,
               "publication_allowed": False, "chunks": [], "conflicts": []}
        minutes = {}
        if seed_report is not None or seed_minutes is not None:
            if seed_report is None or seed_minutes is None:
                raise CacheError("Both diagnostic seed files are required")
            minutes = _seed(doc, report_path=Path(seed_report), minute_path=Path(seed_minutes),
                            start=start, end=end, method=method, allowed=allowed,
                            versions=versions, verify=seed_verify)
        _atomic_save(path, doc, minutes)

    def schedule(target):
        through = _bound(doc["processed_through_utc"])
        # Refetch the last owned grid chunk, including a partially completed edge.
        offset = max(0, int((through - start).total_seconds()) - 60)
        cur = start + timedelta(seconds=(offset // CHUNK_SECONDS) * CHUNK_SECONDS)
        result = []
        while cur < target:
            stop = min(cur + timedelta(seconds=CHUNK_SECONDS), target)
            result.append((cur, stop, _url(cur, stop)))
            cur = stop
        return result

    def process(a, b, url, raw):
        receipt = {"start_utc": _iso(a), "end_exclusive_utc": _iso(b), "url": url,
                   "raw_bytes": len(raw or b""),
                   "raw_sha256": hashlib.sha256(raw).hexdigest() if raw else None,
                   "retrieved_utc": datetime.now(timezone.utc).isoformat()}
        fresh = {}
        if raw:
            stream = read(io.BytesIO(raw))
            identities = sorted({tr.id for tr in stream})
            receipt["identities"] = identities
            if identities != [STATION]:
                raise CacheError(f"Unexpected MiniSEED identities: {identities}")
            # Identity validation precedes merge and all spectral work.
            stream.merge(method=0, fill_value=None)
            if stream:
                latest = max(_utc(tr.stats.endtime.datetime.replace(tzinfo=timezone.utc))
                             for tr in stream)
                receipt["latest_returned_sample_utc"] = _iso(latest)
            m = a
            while m < b:
                got = complete(stream, m)
                if got is not None:
                    band = classify(*got)
                    if band not in allowed:
                        raise CacheError("Classifier returned an unknown band")
                    fresh[int(m.timestamp())] = band
                m += timedelta(minutes=1)
        else:
            receipt["identities"] = []
        old_scope = {t: v for t, v in minutes.items() if a.timestamp() <= t < b.timestamp()}
        conflicts = [{"minute_utc": _iso(datetime.fromtimestamp(t, timezone.utc)),
                      "cached_band": minutes[t], "returned_band": band}
                     for t, band in fresh.items() if t in minutes and minutes[t] != band]
        receipt["accepted_minutes"] = len(fresh)
        receipt["omitted_cached_minutes"] = sorted(set(old_scope) - set(fresh))
        if conflicts:
            receipt["status"] = "conflict_rejected"
            doc["chunks"].append(receipt)
            doc["conflicts"].extend(conflicts)
            _atomic_save(path, doc, minutes)
            raise CacheConflict(f"{len(conflicts)} returned bands conflict with retained minutes")
        minutes.update(fresh)  # Equal duplicates are idempotent; cached omissions survive.
        receipt["status"] = "processed" if raw else "no_data"
        receipt["excluded_minutes"] = [t for t in range(int(a.timestamp()), int(b.timestamp()), 60)
                                       if t not in minutes]
        doc["chunks"].append(receipt)
        doc["processed_through_utc"] = _iso(max(_bound(doc["processed_through_utc"]), b))
        _atomic_save(path, doc, minutes)
        print(json.dumps({"cache_through_utc": doc["processed_through_utc"],
                          "total_complete_minutes": len(minutes),
                          "returned_complete_minutes": len(fresh),
                          "retained_omissions": len(receipt["omitted_cached_minutes"]),
                          "excluded_minutes": len(receipt["excluded_minutes"]),
                          "status": receipt["status"]}), flush=True)

    def acquire(target):
        requests = schedule(target)
        # Only HTTP requests run concurrently. ObsPy parsing/classification and
        # all cache writes execute sequentially in request order.
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending = {}
            for i in range(min(2, len(requests))):
                pending[i] = pool.submit(http, requests[i][2])
            for i, (a, b, url) in enumerate(requests):
                raw = None
                received = False
                prior_receipts = len(doc["chunks"])
                try:
                    raw = pending.pop(i).result()
                    received = True
                    process(a, b, url, raw)
                except Exception as exc:
                    if not isinstance(exc, CacheConflict):
                        if len(doc["chunks"]) == prior_receipts:
                            doc["chunks"].append({
                                "start_utc": _iso(a), "end_exclusive_utc": _iso(b),
                                "url": url, "status": "processing_error" if received else "request_error",
                                "raw_bytes": len(raw or b""),
                                "raw_sha256": hashlib.sha256(raw).hexdigest() if raw else None,
                                "error": str(exc)})
                        doc["last_error"] = {"start_utc": _iso(a), "end_exclusive_utc": _iso(b),
                                             "url": url, "error": str(exc)}
                        _atomic_save(path, doc, minutes)
                    for future in pending.values():
                        future.cancel()
                    raise
                if i + 2 < len(requests):
                    pending[i + 2] = pool.submit(http, requests[i + 2][2])

    acquire(end)
    if catch_up_end is not None:
        later = _bound(catch_up_end())
        if later > end:
            end = later
            acquire(end)
    doc.pop("last_error", None)
    _atomic_save(path, doc, minutes)
    latest_values = [_utc(c["latest_returned_sample_utc"]) for c in doc["chunks"]
                     if c.get("latest_returned_sample_utc") and c.get("status") == "processed"]
    latest = max(latest_values) if latest_values else None
    urls = list(dict.fromkeys(c["url"] for c in doc["chunks"]))
    if metadata is not None:
        metadata.update({"requested_through_utc": _iso(end),
                         "cache_payload_sha256": doc["payload_sha256"],
                         "cache_minute_count": len(minutes),
                         "source_request_count": len(doc["chunks"]),
                         "cached_omissions_recorded": sum(len(c.get("omitted_cached_minutes", []))
                                                          for c in doc["chunks"]),
                         "method_fingerprint": fingerprint_hash})
    return dict(minutes), latest, urls

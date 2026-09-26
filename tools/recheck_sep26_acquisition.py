#!/usr/bin/env python3
"""One-time, bounded recheck of the newly excluded September 26 acquisition interval.

Uses existing complete-minute and classification functions unchanged. Accepted
minutes cannot be overwritten; the usual five calculation gates still follow.
"""
import hashlib, inspect, io, json, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fdsn_tail_cache as cache
import refresh_4_8_10min_current as calc

path = calc.ROOT / 'data/r6e8a_4_8_tail_minutes.json'
report_path = calc.ROOT / 'data/r6e8a-sep26-acquisition-recheck.json'
if report_path.exists():
    print('September 26 targeted recheck already recorded; no historical refetch.')
    raise SystemExit(0)
doc = json.loads(path.read_bytes())
assert doc.get('payload_sha256') == cache.payload_hash(doc), 'Cache hash mismatch'
assert doc.get('station') == cache.STATION and not doc.get('conflicts'), 'Cache identity or conflict'
base_raw = calc.BASE_FILE.read_bytes()
bdoc = json.loads(base_raw)
fingerprint = {'method': bdoc['method'], 'bands': [list(b) for b in calc.BANDS],
               'complete_sha256': hashlib.sha256(inspect.getsource(calc.complete).encode()).hexdigest(),
               'classify_sha256': hashlib.sha256(inspect.getsource(calc.classify).encode()).hexdigest(),
               'versions': cache._versions(), 'base_sha256': hashlib.sha256(base_raw).hexdigest()}
assert doc['method'] == fingerprint, 'Classification method changed'
assert doc['method_fingerprint'] == hashlib.sha256(cache._bytes(fingerprint)).hexdigest()
start = cache._bound(doc['start_utc'])
through = cache._bound(doc['processed_through_utc'])
minutes = cache._minute_map(doc['minutes'], start, through, {b[0] for b in calc.BANDS})
assert len(minutes) == doc['minute_count']
a = cache._bound('2026-09-26T05:09:00+00:00')
b = cache._bound('2026-09-26T07:13:00+00:00')
q0, q1 = a - timedelta(minutes=1), b + timedelta(minutes=1)
assert start <= q0 < q1 <= through
original = dict(minutes)
target = set(range(int(a.timestamp()), int(b.timestamp()), 60)) - minutes.keys()
if not target:
    print('All 124 target minutes already available; no reclassification.')
    raise SystemExit(0)
url = cache._url(q0, q1)
raw = calc.http(url, tries=2, timeout=90)
receipt = {'start_utc': cache._iso(q0), 'end_exclusive_utc': cache._iso(q1),
           'url': url, 'raw_sha256': hashlib.sha256(raw).hexdigest() if raw else None,
           'raw_bytes': len(raw or b''), 'retrieved_utc': datetime.now(timezone.utc).isoformat(),
           'targeted_acquisition_recheck': True}
fresh = {}
if raw:
    stream = calc.read(io.BytesIO(raw))
    receipt['identities'] = sorted({tr.id for tr in stream})
    assert receipt['identities'] == [cache.STATION], 'Unexpected FDSN identity'
    stream.merge(method=0, fill_value=None)
    cursor = q0
    while cursor < q1:
        got = calc.complete(stream, cursor)
        if got is not None:
            fresh[int(cursor.timestamp())] = calc.classify(*got)
        cursor += timedelta(minutes=1)
conflicts = [t for t, band in fresh.items() if t in original and original[t] != band]
assert not conflicts, 'Source classification conflicts with an accepted minute'
added = {t: band for t, band in fresh.items() if t in target}
if added:
    assert all(t in fresh for t in (int(q0.timestamp()), int(b.timestamp()))), 'Missing overlap boundary'
minutes.update(added)
assert all(minutes.get(t) == band for t, band in original.items()), 'Accepted evidence changed'
assert len(minutes) == len(original) + len(added)
remaining = sorted(target - minutes.keys())
receipt.update({'status': 'processed' if raw else 'no_data', 'accepted_minutes': len(fresh),
                'added_minutes': len(added), 'excluded_minutes': remaining,
                'omitted_cached_minutes': sorted(t for t in original if q0.timestamp() <= t < q1.timestamp() and t not in fresh)})
input_hash = doc['payload_sha256']
doc['chunks'].append(receipt)
cache._atomic_save(path, doc, minutes)
report = {'station': cache.STATION, 'scope_start_utc': cache._iso(a),
          'scope_end_exclusive_utc': cache._iso(b), 'input_payload_sha256': input_hash,
          'output_payload_sha256': doc['payload_sha256'], 'original_accepted_minutes': len(original),
          'original_classifications_preserved': True, 'same_classification_method': True,
          'target_missing_minutes': len(target), 'recovered_minutes': len(added),
          'remaining_excluded_minutes': remaining, 'receipt': receipt,
          'note': 'Only the new September 26 acquisition gap was rechecked. Missing time is not zero-filled. Existing five calculation gates remain required before publication.'}
report_path.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))

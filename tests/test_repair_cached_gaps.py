#!/usr/bin/env python3
"""Offline safety checks for the two explicitly scoped historical gap repairs."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import fdsn_tail_cache as cache
import repair_cached_gaps as repair_module
from test_fdsn_tail_cache import BANDS, METHOD, VERSIONS, Source, complete, classify


START = datetime(2026, 9, 9, 20, tzinfo=timezone.utc)
END = datetime(2026, 9, 10, 8, tzinfo=timezone.utc)
GAPS = ((datetime(2026, 9, 9, 21, 52, tzinfo=timezone.utc),
         datetime(2026, 9, 10, 1, 13, tzinfo=timezone.utc)),
        (datetime(2026, 9, 10, 1, 47, tzinfo=timezone.utc),
         datetime(2026, 9, 10, 7, 13, tzinfo=timezone.utc)))


def combine_fixture(base, minutes):
    """A deterministic checkpoint callback; the repair must compare every field."""
    counts = Counter(minutes.values())
    return ({"analyzed_minutes": len(minutes), "dom48_minutes": counts["4-8"],
             "band_counts": {band[0]: counts[band[0]] for band in BANDS},
             "independent_extra_field": sum(t // 60 for t in minutes)}, [])


class GapRepairTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.cache_path = self.directory / "minutes.json"
        self.base_path = self.directory / "base.json"
        self.prefix_path = self.directory / "prefix.json"
        self.report_path = self.directory / "repair-report.json"
        self.full = {t: ("4-8" if i % 7 < 4 else "1-4")
                     for i, t in enumerate(range(int(START.timestamp()),
                                                  int(END.timestamp()), 60))}
        self.gap_keys = {t for a, b in GAPS
                         for t in range(int(a.timestamp()), int(b.timestamp()), 60)}
        self.original = {t: band for t, band in self.full.items() if t not in self.gap_keys}
        self.assertEqual(len(self.gap_keys), 527)
        self.base_path.write_text(json.dumps({"base": {}, "method": METHOD,
                                              "end_exclusive_utc": START.isoformat()}))
        self.base_hash = hashlib.sha256(self.base_path.read_bytes()).hexdigest()
        initial = Source(self.original)
        cache.fetch(START, END, complete=complete, classify=classify,
                    http=initial.http, read=initial.read, method=METHOD, bands=BANDS,
                    cache_path=self.cache_path, versions=VERSIONS,
                    base_sha256=self.base_hash)
        self.original_document = json.loads(self.cache_path.read_text())
        self.original_hash = self.original_document["payload_sha256"]
        self.original_cutoff = self.original_document["processed_through_utc"]
        self.prefix_cutoff = END - timedelta(minutes=5)
        old_prefix = {t: b for t, b in self.full.items() if t < self.prefix_cutoff.timestamp()}
        self.prefix = {"station": "AM.R6E8A.00", "channel": "HDF",
                       "all_five_checks_pass": True, "checks": [{"pass": True}] * 5,
                       "requested_through_utc": self.prefix_cutoff.isoformat(),
                       "latest_complete_analyzed_minute_utc":
                       (self.prefix_cutoff - timedelta(minutes=1)).isoformat(),
                       "current": combine_fixture({}, old_prefix)[0]}
        self.prefix_path.write_text(json.dumps(self.prefix))
        self.source = Source(self.full)
        self.calc = SimpleNamespace(complete=complete, classify=classify,
                                    http=self.source.http, read=self.source.read,
                                    combine=combine_fixture, BANDS=BANDS)

    def tearDown(self):
        self.temporary.cleanup()

    def run_repair(self):
        with patch.object(repair_module, "EXPECTED_PAYLOAD", self.original_hash), \
                patch.object(repair_module, "PREFIX_END", self.prefix_cutoff), \
                patch.object(cache, "_versions", return_value=VERSIONS):
            return repair_module.repair(self.cache_path, self.base_path,
                                        self.prefix_path, self.report_path, calc=self.calc)

    def assert_original_evidence_preserved(self):
        document = json.loads(self.cache_path.read_text())
        current = dict(document["minutes"])
        self.assertEqual({t: current[t] for t in self.original}, self.original)
        self.assertEqual(document["processed_through_utc"], self.original_cutoff)
        self.assertEqual(document["payload_sha256"], cache.payload_hash(document))
        return document, current

    def assert_ordinary_refresh_blocked(self):
        self.source.requests.clear()
        with self.assertRaises(cache.CacheConflict):
            cache.fetch(START, END, complete=complete, classify=classify,
                        http=self.source.http, read=self.source.read,
                        method=METHOD, bands=BANDS, cache_path=self.cache_path,
                        versions=VERSIONS, base_sha256=self.base_hash)
        self.assertEqual(self.source.requests, [])

    def test_exact_527_recovery_uses_good_overlap_preserves_cursor_and_old_bands(self):
        self.run_repair()
        document, current = self.assert_original_evidence_preserved()
        self.assertEqual(current, self.full)
        self.assertEqual(set(current) - set(self.original), self.gap_keys)
        self.assertEqual(len(current) - len(self.original), 527)
        self.assertFalse(document.get("conflicts"))
        self.assertEqual([(a, b) for a, b, _ in self.source.requests],
                         [(a - timedelta(minutes=1), b + timedelta(minutes=1))
                          for a, b in GAPS])
        self.assertTrue(self.report_path.exists())

    def test_transport_interruption_retains_partial_progress_and_resumes_safely(self):
        self.source.fail_after = GAPS[0][1] + timedelta(minutes=1)
        with self.assertRaisesRegex(Exception, "synthetic transport interruption"):
            self.run_repair()
        document, current = self.assert_original_evidence_preserved()
        self.assertEqual(len(current) - len(self.original), 201)
        self.assertTrue(any(x.get("kind") == "targeted_repair_pending"
                            for x in document["conflicts"]))
        self.assert_ordinary_refresh_blocked()

        self.source.fail_after = None
        self.run_repair()
        document, current = self.assert_original_evidence_preserved()
        self.assertEqual(current, self.full)
        self.assertFalse(document.get("conflicts"))

    def test_changed_good_overlap_is_rejected_without_rewriting_old_minute(self):
        key = int(GAPS[0][0].timestamp()) - 60
        self.source.minutes[key] = "8-16"
        with self.assertRaises(cache.CacheConflict):
            self.run_repair()
        document, _ = self.assert_original_evidence_preserved()
        self.assertTrue(document.get("conflicts"))
        self.assert_ordinary_refresh_blocked()

    def test_wrong_identity_is_rejected_before_merge(self):
        self.source.identities = ["AM.R6E8A.00.EHZ"]
        with self.assertRaises(cache.CacheError):
            self.run_repair()
        self.assert_original_evidence_preserved()
        self.assertTrue(self.source.streams)
        self.assertTrue(all(not stream.merged for stream in self.source.streams))
        self.assert_ordinary_refresh_blocked()

    def test_incomplete_recovery_cannot_clear_pending_publication_guard(self):
        missing_key = int(GAPS[0][0].timestamp())
        del self.source.minutes[missing_key]
        with self.assertRaises(cache.CacheError):
            self.run_repair()
        document, current = self.assert_original_evidence_preserved()
        self.assertNotIn(missing_key, current)
        self.assertTrue(any(x.get("kind") == "targeted_repair_pending"
                            for x in document["conflicts"]))
        self.assert_ordinary_refresh_blocked()

    def test_any_old_prefix_field_mismatch_keeps_repaired_cache_unpublishable(self):
        # This extra field prevents an implementation from checking only the
        # two headline totals while silently accepting other prefix differences.
        self.prefix["current"]["independent_extra_field"] += 1
        self.prefix_path.write_text(json.dumps(self.prefix))
        with self.assertRaises(cache.CacheError):
            self.run_repair()
        document, current = self.assert_original_evidence_preserved()
        self.assertEqual(current, self.full)
        self.assertTrue(any(x.get("kind") == "targeted_repair_pending"
                            for x in document["conflicts"]))
        self.assert_ordinary_refresh_blocked()

    def test_unapproved_input_payload_is_rejected_before_http(self):
        before = self.cache_path.read_bytes()
        with patch.object(repair_module, "EXPECTED_PAYLOAD", "0" * 64), \
                patch.object(repair_module, "PREFIX_END", self.prefix_cutoff), \
                patch.object(cache, "_versions", return_value=VERSIONS):
            with self.assertRaises(cache.CacheError):
                repair_module.repair(self.cache_path, self.base_path,
                                     self.prefix_path, self.report_path, calc=self.calc)
        self.assertEqual(self.source.requests, [])
        self.assertEqual(self.cache_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()

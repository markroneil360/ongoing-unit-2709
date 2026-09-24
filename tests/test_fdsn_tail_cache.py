#!/usr/bin/env python3
"""Offline behavioral tests for resumable R6E8A minute retrieval.

The fixtures stand in for transport and ObsPy only.  They deliberately exercise
the cache's interval, identity, persistence, and conflict behavior without
retesting Welch or relying on live FDSN availability.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import fdsn_tail_cache as cache


START = datetime(2026, 8, 12, 19, 13, tzinfo=timezone.utc)
STATION = "AM.R6E8A.00.HDF"
BANDS = (("1-4", 1., 4.), ("4-8", 4., 8.),
         ("8-16", 8., 16.), ("16-20", 16., 20.))
METHOD = {
    "window": "60 s, clock-aligned, complete windows only",
    "welch": "Hann; 8 s segments; 50% overlap",
    "dominance": "highest mean PSD among 1-4, 4-8, 8-16, 16-20 Hz",
    "missing": "excluded; never zero-filled or interpolated",
}
VERSIONS = {"python": "test", "numpy": "test", "scipy": "test", "obspy": "test"}
BASE_SHA256 = "a" * 64


def parse_utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def complete(stream, minute):
    """Inspectable deterministic replacement for the existing completeness test."""
    band = stream.minutes.get(int(minute.timestamp()))
    return (band, 100.) if band is not None else None


def classify(band, sampling_rate):
    """The fixture has already assigned each accepted minute its band."""
    assert sampling_rate == 100.
    return band


class FakeTrace:
    def __init__(self, identity, first, last):
        self.id = identity
        self.stats = SimpleNamespace(
            starttime=SimpleNamespace(datetime=first.replace(tzinfo=None)),
            endtime=SimpleNamespace(datetime=last.replace(tzinfo=None)),
            sampling_rate=100.,
        )


class FakeStream:
    def __init__(self, payload):
        self.minutes = {int(t): b for t, b in payload["minutes"]}
        self.merged = False
        first = parse_utc(payload["start"])
        last = (datetime.fromtimestamp(max(self.minutes), timezone.utc)
                + timedelta(seconds=59.99)) if self.minutes else first
        self.traces = [FakeTrace(identity, first, last)
                       for identity in payload["identities"]]

    def __iter__(self):
        return iter(self.traces)

    def merge(self, method=0, fill_value=None, **kwargs):
        if method != 0 or fill_value is not None:
            raise AssertionError("The cache must not interpolate or fill gaps")
        self.merged = True
        return self


class Source:
    """Thread-safe fake FDSN returning JSON encoded as response bytes."""
    def __init__(self, minutes):
        self.minutes = dict(minutes)
        self.identities = [STATION]
        self.requests = []
        self.streams = []
        self.fail_after = None
        self.lock = threading.Lock()

    def http(self, url, **kwargs):
        query = parse_qs(urlparse(url).query)
        start = parse_utc((query.get("start") or query["starttime"])[0])
        end = parse_utc((query.get("end") or query["endtime"])[0])
        with self.lock:
            self.requests.append((start, end, url))
        if self.fail_after is not None and end > self.fail_after:
            raise RuntimeError("synthetic transport interruption")
        selected = [[t, b] for t, b in sorted(self.minutes.items())
                    if start.timestamp() <= t < end.timestamp()]
        return json.dumps({"start": start.isoformat(), "end": end.isoformat(),
                           "identities": self.identities,
                           "minutes": selected}).encode("utf-8")

    def read(self, source, **kwargs):
        stream = FakeStream(json.loads(source.read()))
        with self.lock:
            self.streams.append(stream)
        return stream


def fixture_minutes(count=725):
    data = {int(START.timestamp()) + 60 * i: "1-4" for i in range(count)}
    # A run crosses the first six-hour boundary.  An absent minute must break it.
    for i in range(350, 385):
        if i < count:
            data[int(START.timestamp()) + 60 * i] = "4-8"
    if count > 363:
        del data[int(START.timestamp()) + 60 * 363]
    return data


def run_lengths(minutes):
    lengths = []
    previous = None
    length = 0
    for timestamp, band in sorted(minutes.items()):
        if band == "4-8":
            if length and timestamp == previous + 60:
                length += 1
            else:
                if length:
                    lengths.append(length)
                length = 1
        elif length:
            lengths.append(length)
            length = 0
        previous = timestamp
    if length:
        lengths.append(length)
    return lengths


class TailCacheTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.cache_path = self.directory / "tail-cache.json"

    def tearDown(self):
        self.temporary.cleanup()

    def fetch(self, source, end, path=None, **kwargs):
        options = dict(complete=complete, classify=classify,
                       http=source.http, read=source.read, method=METHOD,
                       bands=BANDS, cache_path=path or self.cache_path,
                       versions=VERSIONS, base_sha256=BASE_SHA256)
        options.update(kwargs)
        return cache.fetch(START, end, **options)

    def test_interruption_resume_equals_uninterrupted_with_boundary_run_and_gap(self):
        expected = fixture_minutes()
        end = START + timedelta(minutes=725)
        uninterrupted = Source(expected)
        direct, direct_latest, _ = self.fetch(
            uninterrupted, end, self.directory / "uninterrupted.json")
        self.assertEqual(direct, expected)
        self.assertEqual(run_lengths(direct), [13, 21])

        interrupted = Source(expected)
        interrupted.fail_after = START + timedelta(hours=6)
        with self.assertRaisesRegex(Exception, "synthetic transport interruption"):
            self.fetch(interrupted, end)

        saved = json.loads(self.cache_path.read_text())
        self.assertEqual(parse_utc(saved["processed_through_utc"]),
                         START + timedelta(hours=6))
        self.assertEqual(dict(saved["minutes"]),
                         {t: b for t, b in expected.items()
                          if t < (START + timedelta(hours=6)).timestamp()})

        interrupted.fail_after = None
        resumed, resumed_latest, urls = self.fetch(interrupted, end)
        self.assertEqual(resumed, direct)
        self.assertEqual(resumed_latest, direct_latest)
        self.assertIsNotNone(resumed_latest.tzinfo)
        self.assertTrue(urls)
        self.assertEqual(run_lengths(resumed), [13, 21])
        self.assertNotIn(int(START.timestamp()) + 363 * 60, resumed)

    def test_omitted_overlap_retains_verified_minute(self):
        expected = fixture_minutes(365)
        source = Source(expected)
        self.fetch(source, START + timedelta(hours=6))
        retained_key = int(START.timestamp()) + 355 * 60
        del source.minutes[retained_key]

        metadata = {}
        result, _, _ = self.fetch(source, START + timedelta(minutes=365),
                                   metadata=metadata)
        self.assertEqual(result, expected)
        self.assertEqual(result[retained_key], "4-8")
        self.assertNotIn(int(START.timestamp()) + 363 * 60, result)
        self.assertEqual(metadata["cached_omissions_recorded"], 1)

    def test_conflicting_overlap_aborts_and_preserves_cache(self):
        source = Source(fixture_minutes(365))
        self.fetch(source, START + timedelta(hours=6))
        before = json.loads(self.cache_path.read_text())
        key = int(START.timestamp()) + 355 * 60
        source.minutes[key] = "8-16"

        with self.assertRaises(cache.CacheConflict):
            self.fetch(source, START + timedelta(minutes=365))
        after = json.loads(self.cache_path.read_text())
        self.assertEqual(after["minutes"], before["minutes"])
        self.assertEqual(after["processed_through_utc"], before["processed_through_utc"])
        self.assertEqual(after["conflicts"][0]["cached_band"], "4-8")
        self.assertEqual(after["conflicts"][0]["returned_band"], "8-16")
        source.requests.clear()
        with self.assertRaises(cache.CacheConflict):
            self.fetch(source, START + timedelta(minutes=365))
        self.assertEqual(source.requests, [])

    def test_wrong_or_mixed_identity_is_rejected_before_merge(self):
        for identities in (["AM.OTHER.00.HDF"],
                           [STATION, "AM.R6E8A.00.EHZ"]):
            with self.subTest(identities=identities):
                source = Source(fixture_minutes(2))
                source.identities = identities
                with self.assertRaises(cache.CacheError):
                    self.fetch(source, START + timedelta(minutes=2))
                self.assertTrue(source.streams)
                self.assertTrue(all(not stream.merged for stream in source.streams))
                document = json.loads(self.cache_path.read_text())
                self.assertEqual(document["minutes"], [])
                self.assertEqual(parse_utc(document["processed_through_utc"]), START)

    def test_cache_tamper_is_rejected_before_retrieval(self):
        source = Source(fixture_minutes(5))
        end = START + timedelta(minutes=5)
        self.fetch(source, end)
        document = json.loads(self.cache_path.read_text())
        document["minutes"][0][1] = "16-20"
        self.cache_path.write_text(json.dumps(document))
        source.requests.clear()
        with self.assertRaises(cache.CacheError):
            self.fetch(source, end)
        self.assertEqual(source.requests, [])

    def test_structurally_invalid_rows_fail_even_with_recomputed_hash(self):
        source = Source(fixture_minutes(5))
        end = START + timedelta(minutes=5)
        self.fetch(source, end)
        original = json.loads(self.cache_path.read_text())

        def duplicate(document):
            document["minutes"].append(list(document["minutes"][-1]))

        def unaligned(document):
            document["minutes"][0][0] += 1

        def unsupported_band(document):
            document["minutes"][0][1] = "EHZ"

        for mutate in (duplicate, unaligned, unsupported_band):
            with self.subTest(mutation=mutate.__name__):
                document = json.loads(json.dumps(original))
                mutate(document)
                document["payload_sha256"] = cache.payload_hash(document)
                self.cache_path.write_text(json.dumps(document))
                source.requests.clear()
                with self.assertRaises(cache.CacheError):
                    self.fetch(source, end)
                self.assertEqual(source.requests, [])

    def test_changed_base_or_method_refuses_cache_before_retrieval(self):
        source = Source(fixture_minutes(5))
        end = START + timedelta(minutes=5)
        self.fetch(source, end)
        for altered in ({"base_sha256": "b" * 64},
                        {"method": {**METHOD, "welch": "changed algorithm"}}):
            with self.subTest(altered=altered):
                source.requests.clear()
                with self.assertRaises(cache.CacheError):
                    self.fetch(source, end, **altered)
                self.assertEqual(source.requests, [])

    def test_catchup_runs_once_and_metadata_reports_effective_cutoff(self):
        expected = fixture_minutes(365)
        source = Source(expected)
        first_end = START + timedelta(hours=6)
        later = START + timedelta(minutes=365)
        calls = []

        def catch_up():
            # The initial target must already be durable when catch-up is asked.
            saved = json.loads(self.cache_path.read_text())
            self.assertEqual(parse_utc(saved["processed_through_utc"]), first_end)
            calls.append(True)
            return later

        metadata = {}
        actual, latest, _ = self.fetch(source, first_end, catch_up_end=catch_up,
                                       metadata=metadata)
        self.assertEqual(calls, [True])
        self.assertEqual(actual, expected)
        self.assertEqual(parse_utc(metadata["requested_through_utc"]), later)
        self.assertEqual(metadata["cache_minute_count"], len(expected))
        saved = json.loads(self.cache_path.read_text())
        self.assertEqual(metadata["cache_payload_sha256"], cache.payload_hash(saved))
        self.assertEqual(metadata["source_request_count"], len(source.requests))
        self.assertEqual(len(metadata["method_fingerprint"]), 64)
        self.assertLess(latest, later)

    def make_seed(self):
        seed_end = START + timedelta(minutes=5)
        rows = sorted(fixture_minutes(5).items())
        seed = {"station": STATION, "start_utc": START.isoformat(),
                "end_exclusive_utc": seed_end.isoformat(), "method": METHOD,
                "publication_allowed": False, "minutes": rows}
        seed_path = self.directory / "seed-minutes.json"
        seed_path.write_text(json.dumps(seed))
        stamp = lambda value: value.strftime("%Y-%m-%dT%H:%M:%SZ")
        url = ("https://data.raspberryshake.org/fdsnws/dataselect/1/query"
               "?net=AM&sta=R6E8A&loc=00&cha=HDF"
               f"&start={stamp(START)}&end={stamp(seed_end)}&format=miniseed&nodata=404")
        report = {"station": STATION, "start_utc": START.isoformat(),
                  "end_exclusive_utc": seed_end.isoformat(), "versions": VERSIONS,
                  "diagnostic_complete": True, "all_preview_fields_match": True,
                  "minute_file_sha256": hashlib.sha256(seed_path.read_bytes()).hexdigest(),
                  "chunks": [{"start_utc": START.isoformat(),
                              "end_utc": seed_end.isoformat(), "url": url,
                              "sha256": "b" * 64, "bytes": 100,
                              "identities": [STATION], "classified_minutes": 5}]}
        report_path = self.directory / "seed-report.json"
        report_path.write_text(json.dumps(report))
        return report_path, seed_path

    def test_seed_requires_independent_verifier_and_rejects_partial_or_tampered(self):
        report_path, seed_path = self.make_seed()
        original = json.loads(report_path.read_text())
        source = Source(fixture_minutes(8))
        end = START + timedelta(minutes=8)
        variants = [("no_verifier", {}, None),
                    ("partial", {"diagnostic_complete": False}, lambda _: True),
                    ("hash_mismatch", {"minute_file_sha256": "c" * 64}, lambda _: True),
                    ("failed_recomputation", {}, lambda _: False)]
        for name, changes, verifier in variants:
            with self.subTest(case=name):
                report_path.write_text(json.dumps({**original, **changes}))
                with self.assertRaises(cache.CacheError):
                    self.fetch(source, end, self.directory / f"{name}.json",
                               seed_report=report_path, seed_minutes=seed_path,
                               seed_verify=verifier)
                self.assertEqual(source.requests, [])

    def test_verified_seed_preserves_provenance_and_recomputes_checkpoint(self):
        report_path, seed_path = self.make_seed()
        expected = fixture_minutes(8)
        source = Source(expected)
        verified_maps = []

        def verify(minutes):
            verified_maps.append(dict(minutes))
            return minutes == fixture_minutes(5)

        actual, _, _ = self.fetch(source, START + timedelta(minutes=8),
                                  seed_report=report_path, seed_minutes=seed_path,
                                  seed_verify=verify)
        self.assertEqual(actual, expected)
        self.assertEqual(verified_maps, [fixture_minutes(5)])
        saved = json.loads(self.cache_path.read_text())
        self.assertTrue(saved["seed"]["independent_checkpoint_recomputed"])
        self.assertEqual(saved["seed"]["minute_file_sha256"],
                         hashlib.sha256(seed_path.read_bytes()).hexdigest())
        self.assertFalse(saved["publication_allowed"])


if __name__ == "__main__":
    unittest.main()

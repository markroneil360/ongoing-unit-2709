#!/usr/bin/env python3
"""Build the two R6E8A download reports from verified, cached minute data only.

This module never fetches or classifies waveform data. The publication candidate
must have passed its five existing gates and bind to the exact cache payload.
Every report metric is calculated from the requested trailing window, including
complete-minute gaps and run segments clipped to that window.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("America/Detroit")
BANDS = ("1-4", "4-8", "8-16", "16-20")
CANDIDATE_PATH = "data/r6e8a_4_8_10min_full.json"
CACHE_PATH = "data/r6e8a_4_8_tail_minutes.json"
STATUS_PATH = "data/current-status.json"
MANIFEST_PATH = "data/r6e8a-report-manifest.json"
REPO_URL = "https://github.com/markroneil360/ongoing-unit-2709/blob/main/"
CHECK_NAMES = (
    "1_apr12_scope_and_preview_totals",
    "2_corrected_legacy_threshold_checkpoint",
    "3_checkpoint_six_minute_edge",
    "4_tail_minute_integrity",
    "5_10min_reconciliation_ordinance_and_longest_date",
)
W, H = letter
BG = HexColor("#001b14")
PANEL = HexColor("#003126")
DARK = HexColor("#011f18")
LINE = HexColor("#286151")
INK = HexColor("#f8fffb")
MUTED = HexColor("#b8d0c6")
GREEN = HexColor("#66e47a")
BLUE = HexColor("#65c6ef")


class ReportInputError(ValueError):
    """Report inputs do not form one verified calculation snapshot."""


def require(condition, message):
    if not condition:
        raise ReportInputError(message)


def utc(value):
    if not isinstance(value, datetime):
        value = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    require(value.tzinfo is not None and value.utcoffset() is not None,
            "All input timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


def iso(value):
    return utc(value).isoformat()


def et(value, seconds=False):
    value = utc(value).astimezone(TZ)
    return value.strftime("%b %d, %Y  %I:%M:%S %p %Z" if seconds
                          else "%b %d, %Y  %I:%M %p %Z")


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical_hash(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                            ensure_ascii=True, allow_nan=False).encode("utf-8"))


def percentage(numerator, denominator):
    return round(100 * numerator / denominator, 4) if denominator else None


def pct(value, digits=2):
    return f"{value:,.{digits}f}%" if value is not None else "No complete data"


def duration(minutes):
    return f"{minutes // 60:,} h {minutes % 60:02d} min"


def runs48(minutes):
    """Return maximal complete 4-8 minute segments; every gap breaks a run."""
    runs, current = [], []
    for timestamp, band in sorted(minutes.items()):
        if current and (band != "4-8" or timestamp != current[-1] + 60):
            runs.append(current)
            current = []
        if band == "4-8":
            current.append(timestamp)
    if current:
        runs.append(current)
    return runs


def night(timestamp):
    value = datetime.fromtimestamp(timestamp, timezone.utc).astimezone(TZ)
    return value.hour < 7 or value.hour >= (23 if value.weekday() in (4, 5) else 22)


def tail_stats(minutes):
    counts, runs = Counter(minutes.values()), runs48(minutes)
    result = {"analyzed_minutes": len(minutes), "dom48_minutes": counts["4-8"],
              "band_counts": {band: counts[band] for band in BANDS},
              "runs_total": len(runs)}
    for threshold in (10, 15, 30, 60):
        selected = [run for run in runs if len(run) >= threshold]
        result[f"count{threshold}"] = len(selected)
        result[f"mins{threshold}"] = sum(map(len, selected))
    result["ordinance_events"] = sum(len(run) >= 30 and sum(map(night, run)) >= 30
                                      for run in runs)
    return result


def load_inputs(root=ROOT):
    """Load one hash-bound snapshot; fail before writing any report on mismatch."""
    root = Path(root)
    paths = {"candidate": CANDIDATE_PATH, "cache": CACHE_PATH, "status": STATUS_PATH}
    raw = {key: (root / path).read_bytes() for key, path in paths.items()}
    candidate, cache, status = (json.loads(raw[key]) for key in paths)
    checks = candidate.get("checks", [])
    require(candidate.get("station") == "AM.R6E8A.00" and candidate.get("channel") == "HDF",
            "Candidate must be the R6E8A HDF pressure channel")
    require(candidate.get("all_five_checks_pass") is True and len(checks) == 5
            and tuple(check.get("name") for check in checks) == CHECK_NAMES
            and all(check.get("pass") is True for check in checks),
            "The calculation candidate has not passed all five required gates")
    require(cache.get("schema_version") == 1 and cache.get("station") == "AM.R6E8A.00.HDF",
            "Cached minute schema or station is wrong")
    require(not cache.get("conflicts") and not cache.get("last_error"),
            "The cache has an unresolved acquisition conflict or error")
    digest = canonical_hash({key: value for key, value in cache.items()
                             if key != "payload_sha256"})
    require(cache.get("payload_sha256") == digest, "The cached minute payload hash is invalid")
    provenance = candidate.get("cache_provenance", {})
    require(provenance.get("cache_payload_sha256") == digest,
            "The candidate does not bind to this cached minute payload")
    require(cache.get("method_fingerprint") == canonical_hash(cache.get("method"))
            and provenance.get("method_fingerprint") == cache.get("method_fingerprint")
            and cache.get("method", {}).get("method") == candidate.get("method"),
            "Candidate and cache calculation methods differ")
    start, end = utc(cache["start_utc"]), utc(cache["processed_through_utc"])
    require(start == utc(candidate["base_end_exclusive_utc"])
            and end == utc(candidate["requested_through_utc"])
            and end == utc(provenance["requested_through_utc"])
            and end > start and not any((start.second, start.microsecond, end.second, end.microsecond)),
            "Cache and candidate bounds differ or are not clock-minute aligned")
    require(start <= end - timedelta(hours=168), "Cache does not cover the seven-day report scope")
    rows = cache.get("minutes")
    require(isinstance(rows, list), "Cached minute payload is not a list")
    minutes, previous = {}, None
    for row in rows:
        require(isinstance(row, list) and len(row) == 2, "Malformed cached minute row")
        timestamp, band = row
        require(type(timestamp) is int and timestamp % 60 == 0
                and int(start.timestamp()) <= timestamp < int(end.timestamp())
                and (previous is None or timestamp > previous) and band in BANDS,
                "Cached minutes must be ordered, unique, in scope, and classified in known bands")
        minutes[timestamp] = band
        previous = timestamp
    require(len(minutes) == cache.get("minute_count") == provenance.get("cache_minute_count"),
            "Cached minute count does not reconcile")
    expected_post = candidate.get("current", {}).get("post", {})
    observed_post = tail_stats(minutes)
    require(all(observed_post[key] == expected_post.get(key) for key in observed_post),
            "Cached minute recount does not reproduce the candidate tail statistics")
    require(minutes and utc(candidate["latest_complete_analyzed_minute_utc"])
            == datetime.fromtimestamp(max(minutes), timezone.utc),
            "Candidate latest complete minute differs from the cache")
    require(status.get("station") == "AM.R6E8A.00", "Channel status station is wrong")
    status_start, status_end = utc(status["window_start_utc"]), utc(status["window_end_utc"])
    require(status_end > status_start, "Channel status window is empty")
    for channel in ("HDF", "EHZ"):
        item = status.get("channels", {}).get(channel, {})
        require(item.get("channel") == channel and item.get("ok") is True
                and item.get("identity_verified") is True
                and item.get("window_clipped_before_coverage") is True,
                f"{channel} status is not an independently verified clipped window")
        coverage = item.get("coverage_pct")
        require(isinstance(coverage, (int, float)) and not isinstance(coverage, bool)
                and math.isfinite(coverage) and 0 <= coverage <= 100,
                f"{channel} status coverage is invalid")
        require(status_start <= utc(item["latest_sample_utc"]) <= status_end,
                f"{channel} latest sample falls outside the status window")
    return {"candidate": candidate, "cache": cache, "status": status,
            "minutes": minutes, "end": end, "candidate_sha256": sha256(raw["candidate"]),
            "cache_file_sha256": sha256(raw["cache"]), "cache_payload_sha256": digest,
            "status_sha256": sha256(raw["status"]),
            "status_window_minutes": (status_end - status_start).total_seconds() / 60}


def window_stats(minutes, end, hours):
    end, start = utc(end), utc(end) - timedelta(hours=hours)
    low, high = int(start.timestamp()), int(end.timestamp())
    selected = {timestamp: band for timestamp, band in minutes.items() if low <= timestamp < high}
    stats = tail_stats(selected)
    # The cached nighttime screening rule is not a PDF exposure/violation metric.
    stats.pop("ordinance_events")
    stats["expected_clock_minutes"] = hours * 60
    stats["excluded_minutes"] = hours * 60 - len(selected)
    stats["coverage_pct"] = percentage(len(selected), hours * 60)
    stats["dom48_percent_of_analyzed"] = percentage(stats["dom48_minutes"], len(selected))
    stats["band_percent_of_analyzed"] = {
        band: percentage(stats["band_counts"][band], len(selected)) for band in BANDS}
    stats["shorter10_minutes"] = stats["dom48_minutes"] - stats["mins10"]
    stats["latest_complete_minute_utc"] = (
        iso(datetime.fromtimestamp(max(selected), timezone.utc)) if selected else None)
    runs = runs48(selected)
    longest = max(runs, key=lambda run: (len(run), -run[0]), default=[])
    stats["longest_segment"] = None if not longest else {
        "duration_minutes": len(longest),
        "start_utc": iso(datetime.fromtimestamp(longest[0], timezone.utc)),
        "end_exclusive_utc": iso(datetime.fromtimestamp(longest[-1] + 60, timezone.utc)),
        "start_et": datetime.fromtimestamp(longest[0], timezone.utc).astimezone(TZ).isoformat(),
        "end_exclusive_et": datetime.fromtimestamp(longest[-1] + 60, timezone.utc).astimezone(TZ).isoformat(),
        "continues_before_window": longest[0] == low and minutes.get(low - 60) == "4-8",
        "reaches_report_cutoff": longest[-1] + 60 == high,
    }
    stats["run_scope"] = "Maximal consecutive complete 4-8-dominant segments clipped to this report window"
    bin_hours = 4 if hours == 24 else 24
    bins = []
    for offset in range(0, hours, bin_hours):
        a, b = start + timedelta(hours=offset), start + timedelta(hours=offset + bin_hours)
        subset = {timestamp: band for timestamp, band in selected.items()
                  if a.timestamp() <= timestamp < b.timestamp()}
        dom = sum(band == "4-8" for band in subset.values())
        bins.append({"start_utc": iso(a), "end_exclusive_utc": iso(b),
                     "analyzed_minutes": len(subset), "expected_clock_minutes": bin_hours * 60,
                     "excluded_minutes": bin_hours * 60 - len(subset), "dom48_minutes": dom,
                     "dom48_percent_of_analyzed": percentage(dom, len(subset))})
    stats["time_bins"] = bins
    require(sum(stats["band_counts"].values()) == stats["analyzed_minutes"]
            and stats["mins10"] + stats["shorter10_minutes"] == stats["dom48_minutes"]
            and stats["count10"] >= stats["count30"] >= stats["count60"]
            and sum(item["analyzed_minutes"] for item in bins) == stats["analyzed_minutes"]
            and sum(item["dom48_minutes"] for item in bins) == stats["dom48_minutes"],
            "Trailing report statistics do not reconcile")
    return {"start_utc": iso(start), "end_exclusive_utc": iso(end), "hours": hours, "stats": stats}


def text(c, value, x, y, size=10, color=INK, font="Helvetica", anchor="left"):
    c.setFillColor(color)
    c.setFont(font, size)
    if anchor == "right":
        c.drawRightString(x, y, str(value))
    elif anchor == "center":
        c.drawCentredString(x, y, str(value))
    else:
        c.drawString(x, y, str(value))


def paragraph(c, value, x, y, width, size=9, leading=12, color=MUTED):
    line, lines = "", []
    for word in value.split():
        candidate = word if not line else f"{line} {word}"
        if stringWidth(candidate, "Helvetica", size) > width and line:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    for offset, line in enumerate(lines):
        text(c, line, x, y - offset * leading, size, color)
    return y - len(lines) * leading


def panel(c, x, y, width, height, fill=PANEL):
    c.setFillColor(fill)
    c.setStrokeColor(LINE)
    c.setLineWidth(0.7)
    c.roundRect(x, y, width, height, 9, fill=1, stroke=1)


def label(c, value, x, y):
    text(c, value.upper(), x, y, 8, GREEN, "Helvetica-Bold")


def page_base(c, title, page, generated):
    c.setFillColor(BG)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    text(c, "UNIT 2709  /  AM.R6E8A.00", 34, 764, 8, GREEN, "Helvetica-Bold")
    text(c, "DPD Case# 2510170221", 578, 764, 8, MUTED, anchor="right")
    c.setStrokeColor(LINE)
    c.line(34, 29, 578, 29)
    text(c, f"Generated {et(generated)}", 34, 16, 7.2, MUTED)
    text(c, f"{title}  |  {page} / 2", 578, 16, 7.2, MUTED, anchor="right")


def table(c, headers, rows, positions, top, row_height=23, size=9):
    c.setFillColor(PANEL)
    c.roundRect(34, top - row_height * (len(rows) + 1), 544,
                row_height * (len(rows) + 1), 6, fill=1, stroke=0)
    for value, (x, anchor) in zip(headers, positions):
        text(c, value, x, top - 15, 8, MUTED, "Helvetica-Bold", anchor)
    for index, row in enumerate(rows):
        y = top - row_height * (index + 1)
        c.setStrokeColor(LINE)
        c.setLineWidth(0.4)
        c.line(44, y, 568, y)
        for value, (x, anchor) in zip(row, positions):
            text(c, value, x, y - 15, size, INK, "Helvetica", anchor)


def page_one(c, report, inputs, generated):
    stats, hours = report["stats"], report["hours"]
    short = "24-hour report" if hours == 24 else "7-day trailing report"
    page_base(c, short, 1, generated)
    text(c, "R6E8A Pressure Report", 34, 731, 24, INK, "Helvetica-Bold")
    text(c, "Trailing 24 hours" if hours == 24 else "Trailing 7 days (168 hours)", 34, 710, 12, GREEN)
    text(c, f"From:  {et(report['start_utc'])}", 34, 687, 9.5)
    text(c, f"To:       {et(report['end_exclusive_utc'])}  (end exclusive)", 34, 672, 9.5)
    latest = stats["latest_complete_minute_utc"]
    text(c, f"Latest complete HDF minute starts: {et(latest) if latest else 'none in this window'}",
         34, 653, 8.5, MUTED)
    gap, width = 11, (544 - 22) / 3
    cards = [
        ("4-8 HZ DOMINANCE", pct(stats["dom48_percent_of_analyzed"]),
         f"{stats['dom48_minutes']:,} of {stats['analyzed_minutes']:,} complete minutes", "Share of analyzed HDF minutes"),
        ("COMPLETE-MINUTE COVERAGE", pct(stats["coverage_pct"]),
         f"{stats['excluded_minutes']:,} minutes excluded", f"{stats['expected_clock_minutes']:,} clock minutes in window"),
        ("10+ MINUTE SEGMENTS", f"{stats['count10']:,}",
         duration(stats["mins10"]), "Consecutive 4-8-dominant minutes"),
    ]
    for index, (heading, number, line1, line2) in enumerate(cards):
        x = 34 + index * (width + gap)
        panel(c, x, 532, width, 107)
        text(c, heading, x + 12, 620, 7.1, GREEN, "Helvetica-Bold")
        text(c, number, x + 12, 587, 28 if len(number) < 14 else 13, INK, "Helvetica-Bold")
        text(c, line1, x + 12, 563, 8.2, INK)
        text(c, line2, x + 12, 547, 7.4, MUTED)
    label(c, "Dominant frequency band - complete HDF minutes", 34, 510)
    table(c, ["Band", "Complete minutes", "Share of analyzed time"],
          [(f"{band} Hz", f"{stats['band_counts'][band]:,}", pct(stats["band_percent_of_analyzed"][band]))
           for band in BANDS], [(48, "left"), (322, "right"), (564, "right")], 494, 23)
    label(c, "Consecutive 4-8 Hz segments within this window", 34, 356)
    text(c, "Each threshold includes longer segments; these rows are not additive.", 34, 340, 8.5, MUTED)
    table(c, ["Minimum segment length", "Segments", "Minutes in qualifying segments"],
          [(f"{threshold} minutes", f"{stats[f'count{threshold}']:,}", f"{stats[f'mins{threshold}']:,}")
           for threshold in (10, 30, 60)],
          [(48, "left"), (308, "right"), (564, "right")], 324, 23)
    text(c, f"Segments shorter than 10 minutes account for {stats['shorter10_minutes']:,} additional 4-8-dominant minutes.",
         34, 214, 8.4, MUTED)
    panel(c, 34, 101, 544, 97, DARK)
    label(c, "Longest 4-8 Hz segment in this report window", 48, 179)
    longest = stats["longest_segment"]
    if longest:
        text(c, duration(longest["duration_minutes"]), 48, 151, 21, GREEN, "Helvetica-Bold")
        text(c, f"Start: {et(longest['start_utc'])}", 264, 155, 8.8)
        text(c, f"End:   {et(longest['end_exclusive_utc'])}", 264, 140, 8.8)
        suffix = " End time is exclusive."
        if longest["continues_before_window"]:
            suffix += " The run began before this window."
        if longest["reaches_report_cutoff"]:
            suffix += " It reaches the report cutoff."
        text(c, f"{longest['duration_minutes']:,} complete minutes.{suffix}", 48, 118, 8.1, MUTED)
    else:
        text(c, "No complete 4-8-dominant segment in this window.", 48, 146, 11)
    paragraph(c, "All segments are clipped to the report window. A missing or incomplete minute breaks a segment and is excluded from the analyzed-time denominator. Dominance is the highest mean PSD among the four listed bands.",
              34, 81, 544, 8.2, 11)
    c.showPage()


def source_line(c, name, digest, y, link_path):
    text(c, name, 48, y, 8.3, INK, "Helvetica-Bold")
    c.linkURL(REPO_URL + link_path, (48, y - 2, 565, y + 10), relative=0)
    text(c, digest, 48, y - 13, 7.3, MUTED, "Courier")


def page_two(c, report, inputs, generated):
    stats, hours = report["stats"], report["hours"]
    short = "24-hour report" if hours == 24 else "7-day trailing report"
    page_base(c, short, 2, generated)
    text(c, "Time Detail and Source Record", 34, 731, 22, INK, "Helvetica-Bold")
    text(c, "HDF spectral record and independent HDF / EHZ channel continuity", 34, 710, 9.2, MUTED)
    label(c, "Four-hour bins" if hours == 24 else "24-hour bins", 34, 686)
    text(c, "Eastern start times; consecutive equal-duration bins end at the report cutoff.", 34, 671, 8.4, MUTED)
    rows = []
    for item in stats["time_bins"]:
        stamp = utc(item["start_utc"]).astimezone(TZ).strftime("%b %d  %I:%M %p %Z")
        rows.append((stamp, f"{item['analyzed_minutes']:,}", f"{item['excluded_minutes']:,}",
                     f"{item['dom48_minutes']:,}", pct(item["dom48_percent_of_analyzed"])))
    table(c, ["Bin starts", "Complete", "Excluded", "4-8 min", "4-8 share"], rows,
          [(48, "left"), (299, "right"), (380, "right"), (464, "right"), (564, "right")],
          658, 21, 8.3)
    y = 658 - 21 * (len(rows) + 1) - 24
    label(c, "Latest independent channel-status window", 34, y)
    status = inputs["status"]
    text(c, f"{et(status['window_start_utc'], True)}  to  {et(status['window_end_utc'], True)}",
         34, y - 16, 8.4, MUTED)
    status_rows = []
    for channel, title in (("HDF", "HDF - pressure"), ("EHZ", "EHZ - vertical motion")):
        item = status["channels"][channel]
        status_rows.append((title, pct(item["coverage_pct"], 3),
                            et(item["latest_sample_utc"], True)))
    table(c, ["Channel", "Window coverage", "Latest returned sample (Eastern)"], status_rows,
          [(48, "left"), (305, "right"), (564, "right")], y - 27, 22, 8.2)
    y -= 111
    y = paragraph(c, f"These continuity checks cover {inputs['status_window_minutes']:g} minutes only. HDF supplies the frequency statistics; EHZ remains a separate vertical-motion record. EHZ trailing 24-hour or seven-day spectral results are not present in this cache.",
                  34, y, 544, 8.4, 11)
    y -= 12
    label(c, "Method and five-check validation", 34, y)
    y = paragraph(c, "Complete 60-second clock-aligned HDF windows. Welch PSD: Hann window, 8-second segments, 50% overlap. The dominant band has the highest mean PSD among 1-4, 4-8, 8-16 and 16-20 Hz. This measures frequency dominance; no sound-pressure level, guidance index or exposure limit is inferred from band labels.",
                  34, y - 16, 544, 8.4, 11)
    y = paragraph(c, "All five calculation gates passed: April 12 scope and historical totals; legacy duration thresholds; six-minute checkpoint edge; unique complete minute integrity; and duration reconciliation with the dated longest event. This report additionally verifies the cache hash, candidate binding and full-tail recount before deriving each trailing window.",
                  34, y - 5, 544, 8.4, 11)
    y -= 12
    label(c, "Input fingerprints (SHA-256)", 34, y)
    panel(c, 34, y - 122, 544, 109, DARK)
    source_line(c, "Verified calculation candidate", inputs["candidate_sha256"], y - 30, CANDIDATE_PATH)
    source_line(c, "Minute cache - canonical payload", inputs["cache_payload_sha256"], y - 63, CACHE_PATH)
    source_line(c, "Independent channel status", inputs["status_sha256"], y - 96, STATUS_PATH)
    y -= 139
    y = paragraph(c, "Source: Raspberry Shake public FDSN DataSelect, station AM.R6E8A.00. Source-response identities, timestamps and hashes remain in the minute cache. Report statistics and PDF hashes are published in data/r6e8a-report-manifest.json.",
                  34, y, 544, 7.8, 10)
    text(c, "*Account for up to 30 minutes of lag.", 34, y - 6, 8, GREEN)
    require(y - 6 > 34, "Report page two content exceeds the footer safe area")
    c.showPage()


def build_report(target, report, inputs, generated):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(target), pagesize=letter, pageCompression=1)
    pdf.setDateFormatter(lambda *_: utc(generated).strftime("D:%Y%m%d%H%M%SZ"))
    name = "R6E8A 24-Hour Pressure Report" if report["hours"] == 24 else "R6E8A 7-Day Trailing Pressure Report"
    pdf.setTitle(name)
    pdf.setAuthor("R6E8A Unit 2709")
    pdf.setSubject("Verified cached HDF frequency dominance; separate HDF and EHZ continuity")
    page_one(pdf, report, inputs, generated)
    page_two(pdf, report, inputs, generated)
    pdf.save()
    return sha256(target.read_bytes())


def download_pattern(path):
    return re.compile(r'''(?P<prefix>\bhref\s*=\s*)(?P<quote>["'])(?:\./)?'''
                      + re.escape(path) + r'''(?:\?[^"']*)?(?P=quote)''', re.IGNORECASE)


def patch_download_links(root, reports):
    target = Path(root) / "index.html"
    original = updated = target.read_text(encoding="utf-8")
    for report in reports:
        pattern = download_pattern(report["path"])
        require(len(pattern.findall(updated)) == 1,
                f"Expected exactly one download link for {report['path']}")
        updated = pattern.sub(lambda match: match["prefix"] + match["quote"]
                              + report["download_url"] + match["quote"], updated)
    if updated != original:
        target.write_text(updated, encoding="utf-8")


def verify_reports(root=ROOT):
    """Verify current data, reports and links without generating or changing files."""
    root = Path(root)
    inputs = load_inputs(root)
    manifest = json.loads((root / MANIFEST_PATH).read_bytes())
    require(manifest.get("schema_version") == 1 and manifest.get("station") == "AM.R6E8A.00"
            and manifest.get("all_five_checks_pass") is True,
            "Report manifest schema or verification state is wrong")
    for key in ("candidate_sha256", "cache_payload_sha256", "cache_file_sha256", "status_sha256"):
        require(manifest.get(key) == inputs[key], f"Report manifest {key} is stale")
    require(utc(manifest["requested_through_utc"]) == inputs["end"],
            "Report manifest cutoff is stale")
    reports = manifest.get("reports", [])
    require(len(reports) == 2, "Manifest must contain exactly two PDF reports")
    html = (root / "index.html").read_text(encoding="utf-8")
    for item, (hours, path) in zip(reports, ((24, "downloads/R6E8A-24-hour-report.pdf"),
                                          (168, "downloads/R6E8A-7-day-trailing-report.pdf"))):
        expected = window_stats(inputs["minutes"], inputs["end"], hours)
        require(item.get("path") == path and item.get("pages") == 2
                and item.get("start_utc") == expected["start_utc"]
                and item.get("end_exclusive_utc") == expected["end_exclusive_utc"]
                and item.get("stats") == expected["stats"],
                f"Manifest statistics or bounds are stale for {path}")
        content = (root / path).read_bytes()
        require(content.startswith(b"%PDF-") and sha256(content) == item.get("pdf_sha256"),
                f"PDF file does not match its manifest hash: {path}")
        url = "./" + path + "?v=" + item["pdf_sha256"][:16]
        matches = list(download_pattern(path).finditer(html))
        require(item.get("download_url") == url and len(matches) == 1
                and matches[0][0] == matches[0]["prefix"] + matches[0]["quote"] + url + matches[0]["quote"],
                f"Dashboard download link does not use the current PDF hash: {path}")
    return manifest


def generate_reports(root=ROOT, generated_utc=None):
    root = Path(root)
    inputs = load_inputs(root)
    generated = utc(generated_utc) if generated_utc else datetime.now(timezone.utc)
    manifest = {"schema_version": 1, "station": "AM.R6E8A.00",
                "candidate_sha256": inputs["candidate_sha256"],
                "cache_payload_sha256": inputs["cache_payload_sha256"],
                "cache_file_sha256": inputs["cache_file_sha256"],
                "status_sha256": inputs["status_sha256"],
                "requested_through_utc": iso(inputs["end"]), "generated_utc": iso(generated),
                "all_five_checks_pass": True, "source_mode": "verified cached minute classifications only",
                "reports": []}
    for hours, path in ((24, "downloads/R6E8A-24-hour-report.pdf"),
                        (168, "downloads/R6E8A-7-day-trailing-report.pdf")):
        report = window_stats(inputs["minutes"], inputs["end"], hours)
        digest = build_report(root / path, report, inputs, generated)
        manifest["reports"].append({"path": path, "start_utc": report["start_utc"],
                                    "end_exclusive_utc": report["end_exclusive_utc"],
                                    "stats": report["stats"], "pdf_sha256": digest, "pages": 2,
                                    "download_url": "./" + path + "?v=" + digest[:16]})
    destination = root / MANIFEST_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    patch_download_links(root, manifest["reports"])
    verify_reports(root)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository root containing verified data")
    parser.add_argument("--generated-utc", help="Optional explicit report-generation timestamp")
    parser.add_argument("--verify-only", action="store_true", help="Verify current reports, input hashes and links without writing")
    args = parser.parse_args()
    manifest = verify_reports(args.root) if args.verify_only else generate_reports(args.root, args.generated_utc)
    print(json.dumps({"manifest": MANIFEST_PATH, "requested_through_utc": manifest["requested_through_utc"],
                      "reports": [{"path": item["path"], "sha256": item["pdf_sha256"],
                                   "analyzed_minutes": item["stats"]["analyzed_minutes"],
                                   "dom48_minutes": item["stats"]["dom48_minutes"]}
                                  for item in manifest["reports"]]}, indent=2))


if __name__ == "__main__":
    main()

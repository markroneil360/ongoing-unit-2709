#!/usr/bin/env python3
"""Five fail-closed checks for the public, plain-language dashboard layout."""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
CANDIDATE = ROOT / "data" / "r6e8a_4_8_10min_full.json"
STATUS = ROOT / "data" / "current-status.json"
BENCHMARK = ROOT / "data" / "benchmark-index.json"
PUBLISHER = ROOT / "tools" / "publish_4_8_10min.py"
EDGE_SYNC = ROOT / "tools" / "sync_dashboard_current_edge.py"


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.suppressed = 0

    def handle_starttag(self, tag: str, attrs):
        if tag in {"style", "script"}:
            self.suppressed += 1

    def handle_endtag(self, tag: str):
        if tag in {"style", "script"} and self.suppressed:
            self.suppressed -= 1

    def handle_data(self, data: str):
        if not self.suppressed:
            self.parts.append(data)


def require(condition: bool, message: str):
    if not condition:
        raise AssertionError(message)


source = INDEX.read_text(encoding="utf-8")
candidate = json.loads(CANDIDATE.read_text(encoding="utf-8"))
status = json.loads(STATUS.read_text(encoding="utf-8"))
benchmark = json.loads(BENCHMARK.read_text(encoding="utf-8"))
parser = VisibleText()
parser.feed(source)
visible = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()
cur = candidate["current"]


# PASS 1 — source identity, arithmetic, and current values.
require(candidate["station"] == "AM.R6E8A.00" and candidate["channel"] == "HDF", "candidate identity mismatch")
require(status["station"] == "AM.R6E8A.00", "status identity mismatch")
require(status["channels"]["HDF"]["ok"] and status["channels"]["EHZ"]["ok"], "current channel check failed")
require(len(candidate["checks"]) == 5 and all(x["pass"] for x in candidate["checks"]), "source five-check gate failed")
require(cur["mins10"] + cur["shorter10_minutes"] == cur["dom48_minutes"], "minute reconciliation failed")
require(cur["count10"] >= cur["count30"] >= cur["count60"] >= cur["ordinance_events"], "event nesting failed")
for value in (cur["ordinance_events"], cur["count10"], cur["count30"], cur["count60"]):
    require(f"{int(value):,}" in visible, f"missing current count {value}")
print("PASS 1/5 — source identity, five-check data, arithmetic, and displayed counts")


# PASS 2 — opening hierarchy and layperson wording.
hero = source.index('id="repeated-noise-violations"')
stats = source.index('class="section panel stats-panel"')
benchmarks = source.index("Benchmark comparisons in plain language")
require(hero < stats < benchmarks, "required reading order is not preserved")
require("Repeated Noise Violations" in visible, "required 107 title missing")
require(source.count('class="stat-card"') == 6, "expected six compact statistic cards")
require(source.count('class="why-title">Why this count matters') == 6, "every statistic needs a why explanation")
require(visible.count("April 12, 2026") >= 3 and "Ongoing" in visible, "ongoing archive scope is not prominent")
print("PASS 2/5 — violation-first hierarchy, six-stat row, explanations, and ongoing date")


# PASS 3 — public verification path and channel separation.
require("https://data.raspberryshake.org/fdsnws/dataselect/1/" in source, "FDSN DataSelect link missing")
require("All Figures On This Dashboard Can Be Self-Verified By Any Visitor" in visible, "verification statement missing")
require("AM.R6E8A.00" in visible and "HDF And EHZ" in visible, "station/channel verification instructions missing")
require("HDF pressure/infrasound and EHZ vertical/seismic motion remain separate channels" in visible, "channel-separation guard missing")
print("PASS 3/5 — self-verification link, station identity, and HDF/EHZ separation")


# PASS 4 — benchmark values, color semantics, and method boundaries.
indices = benchmark["external_indices_pct"]
require(round(indices["ansi_asa_ashrae_rc30_supported_band_max"]) == 172, "RC-30 index mismatch")
require(round(indices["iso_7196_method_band_energy_share"]) == 90, "ISO energy-share mismatch")
require(round(indices["defra_nanr45_supported_band_max"]) == 46, "NANR45 index mismatch")
for text in ("65 dB", "68.003 dB", "100%", "172%", "1–20 Hz", "90%", "46%", "85 dBA / 8 hr", "30 dB LAeq"):
    require(text in visible, f"benchmark value missing: {text}")
require(source.count('class="comparison-side recorded"') == 2, "red comparison styling must be limited to two supported exceedances")
require(visible.count("Not method-matched") == 2, "NIOSH and WHO method boundaries must both be explicit")
require("no red number is invented" in visible, "NIOSH non-conversion safeguard missing")
print("PASS 4/5 — benchmark values, red/green meaning, and non-comparable methods")


# PASS 5 — copy and responsive-format regression guard.
combined = "\n".join((source, PUBLISHER.read_text(encoding="utf-8"), EDGE_SYNC.read_text(encoding="utf-8"))).lower()
prohibited_terms = ("fun" + "nel", "market" + "ing", "red " + "button", "one-" + "hour", "one " + "hour")
for prohibited in prohibited_terms:
    require(prohibited not in combined, f"prohibited term remains: {prohibited}")
require("@media(max-width:760px)" in source and ".stats-grid,.benchmark-grid{grid-template-columns:1fr}" in source, "mobile stacking rule missing")
require(source.count("<!-- EVIDENCE SUMMARY START -->") == 1 and source.count("<!-- EVIDENCE SUMMARY END -->") == 1, "publisher markers invalid")
require("Conservative Count" not in visible, "replaced title remains visible")
require("1:12:22 AM ET" not in source, "stale public cutoff remains")
print("PASS 5/5 — prohibited-copy, responsive-layout, marker, and stale-cutoff guards")
print("R6E8A layman dashboard: ALL FIVE CHECKS PASSED")

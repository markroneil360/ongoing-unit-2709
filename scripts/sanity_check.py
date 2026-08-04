#!/usr/bin/env python3
"""Fail closed when public R6E8A output violates the locked display rules."""

from __future__ import annotations

import re
import json
from html.parser import HTMLParser
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
WORKFLOW = ROOT / ".github" / "workflows" / "update-daily-highest.yml"
BENCHMARK = ROOT / "data" / "benchmark-index.json"
PDFS = [
    ROOT / "downloads" / "R6E8A-24-hour-report.pdf",
    ROOT / "downloads" / "R6E8A-7-day-trailing-report.pdf",
]


class PublicHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text: list[str] = []
        self.attrs: list[str] = []
        self.hrefs: list[str] = []
        self.suppressed = 0

    def handle_data(self, data: str):
        if not self.suppressed:
            self.text.append(data)

    def handle_starttag(self, tag: str, attrs):
        if tag in {"style", "script"}:
            self.suppressed += 1
            return
        if self.suppressed:
            return
        for key, value in attrs:
            if value is None:
                continue
            if key in {"aria-label", "alt", "title"}:
                self.attrs.append(value)
            if key == "href":
                self.hrefs.append(value)

    def handle_endtag(self, tag: str):
        if tag in {"style", "script"} and self.suppressed:
            self.suppressed -= 1


def require(condition: bool, message: str):
    if not condition:
        raise AssertionError(message)


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def assert_public_text(value: str, label: str):
    lowered = value.lower()
    banned_phrases = [
        "n/a",
        "not yet",
        "pending",
        "unavailable",
        "not determined",
        "not gradeable",
        "source not retained",
        "not applicable",
        "same-day median",
        "trailing median",
        "percentile",
        "peer station",
        "other station",
        "z score",
        "z-score",
    ]
    for phrase in banned_phrases:
        require(phrase not in lowered, f"{label}: prohibited phrase {phrase!r}")

    banned_measure_patterns = {
        "pressure units": r"(?i)\b(?:pa|pascal|pascals)\b",
        "frequency units": r"(?i)\b(?:hz|hertz)\b",
        "level units": r"(?i)\bdb(?:a|c|g)?\b",
        "raw counts": r"(?i)\bcounts?\b",
        "raw durations": r"(?i)\b\d+(?:\.\d+)?\s*(?:sec(?:ond)?s?|min(?:ute)?s?)\b",
    }
    for name, pattern in banned_measure_patterns.items():
        require(re.search(pattern, value) is None, f"{label}: visible {name}")

    for family in ("ISO 7196", "ANSI/ASA", "ASHRAE", "NANR45", "WHO", "ISO 1996"):
        require(family.lower() in lowered, f"{label}: missing {family}")
    for tier in ("Tier 1", "Tier 2", "Tier 3", "Tier 4"):
        require(tier.lower() in lowered, f"{label}: missing {tier}")
    for pct in ("90%", "172%", "46%", "12%", "36%", "100%"):
        require(pct in value, f"{label}: missing {pct}")


def check_html():
    source = INDEX.read_text(encoding="utf-8")
    parser = PublicHTML()
    parser.feed(source)
    visible = normalize(" ".join(parser.text + parser.attrs))
    assert_public_text(visible, "index.html")
    require(visible.lower().find("hdf file integrity") < visible.lower().find("ehz file integrity"), "HDF must appear before EHZ")
    require(visible.lower().count("fdsn") == 1, "FDSN must appear exactly once")
    require("Infrasound Detected" in visible, "static infrasound finding missing")
    require("Current recommendation Tier 2" in visible, "current Tier 2 recommendation missing")
    require("April 12, 2026 - Ongoing" in visible, "archive scope missing")

    lower_source = source.lower()
    for token in ("animation:", "@keyframes", "signal-light", "signal-beacon", "traffic-blink", "signal-sway"):
        require(token not in lower_source, f"movement token remains: {token}")
    require("<script" not in lower_source, "public dashboard must be pre-rendered without JavaScript")
    require("<iframe" not in lower_source, "public dashboard must be complete without network frames")
    require("fetch(" not in lower_source, "public dashboard must be complete without fetch")

    for href in parser.hrefs:
        if href.startswith(("http://", "https://", "#", "mailto:")):
            continue
        target = (ROOT / href.split("#", 1)[0].split("?", 1)[0]).resolve()
        require(target.exists(), f"broken local link: {href}")


def check_workflow():
    value = WORKFLOW.read_text(encoding="utf-8").lower()
    require("workflow_dispatch" in value, "manual workflow trigger missing")
    require("schedule:" not in value, "scheduled feed remains")
    require("push:" not in value, "push-triggered feed remains")
    require("contents: write" not in value, "workflow write permission remains")
    require("update_daily_highest" not in value, "network updater remains wired into workflow")


def check_pdfs():
    for path in PDFS:
        require(path.exists() and path.stat().st_size > 5000, f"invalid PDF file: {path.name}")
        reader = PdfReader(str(path))
        require(len(reader.pages) == 2, f"{path.name}: expected two pages")
        text_value = normalize(" ".join(page.extract_text() or "" for page in reader.pages))
        assert_public_text(text_value, path.name)
        require(text_value.lower().count("fdsn") == 1, f"{path.name}: FDSN must appear once")
        require("Current recommendation" in text_value, f"{path.name}: recommendation missing")


def check_benchmark_data():
    payload = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    values = payload["external_indices_pct"]
    require(round(values["iso_7196_method_band_energy_share"]) == 90, "ISO rounded value mismatch")
    require(round(values["ansi_asa_ashrae_rc30_supported_band_max"]) == 172, "ASHRAE rounded value mismatch")
    require(round(values["defra_nanr45_supported_band_max"]) == 46, "Defra rounded value mismatch")
    require(round(values["who_iso1996_supported_band_contribution_max"]) == 12, "WHO rounded value mismatch")
    require(round(values["sensitivity_tolerant_above_guide_window_share"]) == 36, "Tier share mismatch")
    require(payload["tier_recommendation"]["tier"] == "Tier 2", "Tier recommendation mismatch")
    require(payload["current_direct_upload"]["hdf_file_integrity_pct"] == 100, "HDF integrity mismatch")
    require(payload["current_direct_upload"]["ehz_file_integrity_pct"] == 100, "EHZ integrity mismatch")
    series = payload["rc30_supported_band_series_pct"]
    require(len(series) == 77 and max(series) == 172, "trend series mismatch")


if __name__ == "__main__":
    check_html()
    check_workflow()
    check_pdfs()
    check_benchmark_data()
    print("R6E8A percentage-only public output: PASS")

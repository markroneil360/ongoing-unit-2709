#!/usr/bin/env python3
"""Publish the five-check-verified full >=10-minute R6E8A recalculation.

Reads:
  data/r6e8a_4_8_10min_full.json
  data/current-status.json
Writes:
  index.html

The script performs five additional publication-integrity checks and refuses to
write if the threshold definition, arithmetic, channel separation, current-edge
status, or duplicate dashboard values are inconsistent.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
CANDIDATE = ROOT / "data" / "r6e8a_4_8_10min_full.json"
STATUS = ROOT / "data" / "current-status.json"
TZ = ZoneInfo("America/Detroit")

cand = json.loads(CANDIDATE.read_text(encoding="utf-8"))
status = json.loads(STATUS.read_text(encoding="utf-8"))
s = INDEX.read_text(encoding="utf-8")

if not cand.get("all_five_checks_pass") or len(cand.get("checks", [])) != 5:
    raise SystemExit("Candidate has not passed all five calculation checks; refusing publication.")
if not all(x.get("pass") for x in cand["checks"]):
    raise SystemExit("At least one calculation check failed; refusing publication.")
if cand.get("station") != "AM.R6E8A.00" or cand.get("channel") != "HDF":
    raise SystemExit("Candidate station/channel identity mismatch.")
if not str(cand.get("analysis_start_et", "")).startswith("2026-04-12T00:00:00"):
    raise SystemExit("Candidate does not start at Apr 12, 2026 midnight Detroit time.")

chs = status.get("channels", {})
hdf = chs.get("HDF", {})
ehz = chs.get("EHZ", {})
if not (hdf.get("ok") and ehz.get("ok")):
    raise SystemExit("Current HDF/EHZ continuity check is not OK; refusing publication.")
if min(float(hdf.get("coverage_pct", 0)), float(ehz.get("coverage_pct", 0))) < 99.0:
    raise SystemExit("Current HDF/EHZ coverage below 99%; refusing publication.")

c = cand["current"]

def dt_et(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(TZ)

def time_et(iso: str, seconds=True) -> str:
    d = dt_et(iso)
    fmt = "%I:%M:%S %p" if seconds else "%I:%M %p"
    return d.strftime(fmt).lstrip("0") + " ET"

def date_time_et(iso: str, seconds=True) -> str:
    d = dt_et(iso)
    fmt = "%B %-d, %Y · %-I:%M:%S %p" if seconds else "%B %-d, %Y · %-I:%M %p"
    return d.strftime(fmt) + " ET"

def short_date_time_et(iso: str) -> str:
    d = dt_et(iso)
    return d.strftime("%b. %-d, %Y, %-I:%M %p") + " ET"

def duration_label(minutes: int) -> str:
    h, m = divmod(int(minutes), 60)
    if h and m:
        return f"{h} Hours {m} Minutes"
    if h:
        return f"{h} Hours"
    return f"{m} Minutes"

def event_date_label(start_iso: str, end_iso: str) -> str:
    start = dt_et(start_iso)
    end = dt_et(end_iso) - timedelta(seconds=1)
    if start.date() == end.date():
        return start.strftime("%B %-d, %Y")
    if start.year == end.year and start.month == end.month:
        return f'{start.strftime("%B %-d")}–{end.strftime("%-d, %Y")}'
    if start.year == end.year:
        return f'{start.strftime("%B %-d")}–{end.strftime("%B %-d, %Y")}'
    return f'{start.strftime("%B %-d, %Y")}–{end.strftime("%B %-d, %Y")}'

def pct(part, whole):
    return round(100.0 * part / whole, 2) if whole else 0.0

def replace_one(pattern: str, repl: str, label: str):
    global s
    s2, n = re.subn(pattern, repl, s, count=1, flags=re.S)
    if n != 1:
        raise SystemExit(f"Publication patch failed for {label}: expected 1 match, found {n}")
    s = s2

latest_cum = cand["latest_returned_sample_utc"]
latest_complete = cand["latest_complete_analyzed_minute_utc"]
hdf_latest = hdf["latest_sample_utc"]
ehz_latest = ehz["latest_sample_utc"]
latest_day = dt_et(latest_cum).strftime("%B %-d, %Y").upper()
exact_hours = float(c["dom48_hours"])
rounded_hours = int(round(exact_hours))
longest_run = c["longest_runs"][0] if c.get("longest_runs") else {}
if not (longest_run.get("start_et") and longest_run.get("end_et")):
    raise SystemExit("Longest continuous run has no verified occurrence date; refusing publication.")
longest_minutes = int(longest_run["duration_minutes"])
longest_label = duration_label(longest_minutes)
longest_date_label = event_date_label(longest_run["start_et"], longest_run["end_et"])

status_html = (
    '<div class="status"><strong>LIVE CHANNEL CHECK — '
    f'HDF {date_time_et(hdf_latest)} / EHZ {date_time_et(ehz_latest)}</strong><br>'
    f'Both channels verified separately at <b>{float(hdf["coverage_pct"]):.1f}% HDF</b> and '
    f'<b>{float(ehz["coverage_pct"]):.1f}% EHZ acquisition coverage</b> in the current status window. '
    f'The cumulative HDF 4–8 Hz spectral calculation starts <b>April 12, 2026</b> and is five-check verified through '
    f'<b>{date_time_et(latest_cum)}</b> returned HDF sample / <b>{date_time_et(latest_complete, seconds=False)}</b> complete analyzed minute.'
    '<div class="small">*Account for up to 30 minutes of lag. Missing acquisition time is never scored as zero, quiet, normal, compliant, or below benchmark.</div></div>'
)
replace_one(r'<div class="status">.*?</div><div class="download-actions">',
            status_html + '<div class="download-actions">', 'live status')

evidence_summary = f'''<!-- EVIDENCE SUMMARY START -->
<section class="section panel violation-hero" id="repeated-noise-violations"><div class="date-scope">April 12, 2026 — Ongoing</div><h2>Repeated Noise Violations</h2><div class="violation-number">{c["ordinance_events"]:,}</div><div class="events-caption">Documented Events</div><p class="hero-copy">Event timing was verified from the public Raspberry Shake FDSN record for station <b>AM.R6E8A.00</b>. The count uses a conservative nighttime screening rule: each distinct event lasted at least 30 minutes and contained at least 30 actual minutes inside the applicable nighttime window. The local ordinance screen and Michigan regulatory references are kept separate, and this reproducible dashboard count is not an agency adjudication or a source-identification finding.</p><p class="verify-callout"><strong>All Figures On This Dashboard Can Be Self-Verified By Any Visitor Through The <a href="https://data.raspberryshake.org/fdsnws/dataselect/1/">Raspberry Shake FDSN DataSelect Service</a> For Station AM.R6E8A.00 Using HDF And EHZ.</strong></p></section>
<section class="section panel stats-panel"><div class="date-scope">Evidence summary · April 12, 2026 — Ongoing</div><h2>What the documented counts show</h2><div class="stats-grid"><article class="stat-card"><div class="stat-title">Repeated Noise Violations</div><div class="stat-number">{c["ordinance_events"]:,}<span>Events</span></div><div class="why-title">Why this count matters</div><p class="why-copy">Only sustained events with at least 30 actual nighttime minutes are included; each distinct event is counted once.</p></article><article class="stat-card"><div class="stat-title">Documented 4–8 Hz Activity</div><div class="stat-number">{exact_hours:,.2f}<span>Hours</span></div><div class="why-title">Why this count matters</div><p class="why-copy">This is the cumulative time in which 4–8 Hz was the dominant HDF band, not a total elapsed-time estimate.</p></article><article class="stat-card"><div class="stat-title">Repeated ≥10-Minute Events</div><div class="stat-number">{c["count10"]:,}<span>Events</span></div><div class="why-title">Why this count matters</div><p class="why-copy">Repeated runs show recurrence rather than isolated peaks; the threshold is a reporting definition, not a legal or medical limit.</p></article><article class="stat-card"><div class="stat-title">Sustained ≥30-Minute Events</div><div class="stat-number">{c["count30"]:,}<span>Events</span></div><div class="why-title">Why this count matters</div><p class="why-copy">These longer events form the pool from which the conservative nighttime count is derived.</p></article><article class="stat-card"><div class="stat-title">Sustained ≥60-Minute Events</div><div class="stat-number">{c["count60"]:,}<span>Events</span></div><div class="why-title">Why this count matters</div><p class="why-copy">An hour or more of uninterrupted 4–8 Hz dominance documents persistence beyond short disturbances.</p></article><article class="stat-card"><div class="stat-title">Longest Continuous Run</div><div class="stat-number">{longest_label}<span>4–8 Hz Dominant</span></div><div class="stat-date">Occurred: {longest_date_label}</div><div class="why-title">Why this count matters</div><p class="why-copy">The date identifies when this record-setting continuous run occurred. It updates automatically only when a longer verified run replaces it.</p></article></div></section>
<section class="section panel count-method"><h2>How the {c["ordinance_events"]:,} events were counted</h2><p class="method-rule"><b>Required for every counted event:</b> a sustained 30+ minute 4–8 Hz-dominant run, with at least 30 actual minutes inside the applicable nighttime window. Missing acquisition time is excluded. Overlapping criteria never multiply one event.</p><div class="clock"><div class="label">Nighttime-window screen</div><div class="clockbar"><div class="night">12 AM–7 AM</div><div class="day">7 AM–10 PM</div><div class="late">10 PM–12 AM</div></div><div class="legend"><span>General nighttime window: 10 PM–7 AM</span><span>Friday/Saturday conservative downtown start: 11 PM</span></div></div><p class="small">The 10-minute event threshold elsewhere on this page is a reporting/event-definition choice, not a medical or legal exposure limit. It does not lower this separate 30-minute nighttime rule.</p></section>
<!-- EVIDENCE SUMMARY END -->'''
replace_one(r'<!-- EVIDENCE SUMMARY START -->.*?<!-- EVIDENCE SUMMARY END -->', evidence_summary, 'layman evidence summary')

boundary = f'''<section class="section context-note"><b>Evidence boundary for legal review:</b> the station documents environmental pressure/infrasound timing, frequency-band dominance, recurrence and duration. The {exact_hours:,.2f}-hour environmental record and the ≥10-minute repeated-low-frequency event definition are environmental signal metrics, not automatically a personal medical dose or a health threshold. Source attribution and individual medical causation require independent investigation/onsite validation.</section>'''
replace_one(r'<section class="section context-note"><b>Evidence boundary for legal review:</b>.*?</section>', boundary, 'evidence boundary')


# Reconcile every remaining date, cutoff, total, and ordinance reference.
s = re.sub(
    r'the <b>[\d,]+-Event ordinance subset</b> is displayed separately',
    f'the <b>{c["ordinance_events"]:,}-Event ordinance subset</b> is displayed separately',
    s,
    count=1,
)

current_edge = (
    '<section class="section note"><b>Current-edge check:</b> '
    f'public FDSN data is verified through HDF {date_time_et(hdf_latest)} and EHZ {date_time_et(ehz_latest)}. '
    f'The cumulative 4–8 Hz calculation includes complete HDF minutes through {date_time_et(latest_complete, seconds=False)}. '
    'HDF pressure/infrasound and EHZ vertical/seismic motion remain separate channels; incomplete or missing acquisition time is excluded rather than treated as zero, quiet, normal, compliant, or below benchmark.</section>'
)
replace_one(r'<section class="section note"><b>Current-edge check:</b>.*?</section>', current_edge, 'current-edge note')

verification_note = (
    '<section class="section note"><b>Independent verification:</b> source of record is Raspberry Shake public FDSN for '
    '<b>AM.R6E8A.00.HDF</b> and <b>AM.R6E8A.00.EHZ</b>. '
    f'The displayed channel cutoffs are HDF {date_time_et(hdf_latest)} and EHZ {date_time_et(ehz_latest)}; '
    f'the five-check spectral calculation cutoff is {date_time_et(latest_complete, seconds=False)} for complete HDF minutes.</section>'
)
replace_one(r'<section class="section note"><b>Independent verification:</b>.*?</section>', verification_note, 'verification note')

publication_integrity = f'''<section class="section panel"><h2>Publication integrity</h2><div class="approval"><div class="check"><span class="dot"></span><div><b>Current cutoff is explicit.</b><div class="small">HDF live status through {date_time_et(hdf_latest)} · EHZ live status through {date_time_et(ehz_latest)} · five-check 4–8 Hz totals through {date_time_et(latest_complete, seconds=False)} complete HDF minute.</div></div></div><div class="check"><span class="dot"></span><div><b>Current cumulative values are updated.</b><div class="small">{exact_hours:,.2f} Hours · {c["count10"]:,} Events ≥10 · {c["count30"]:,} Events ≥30 · {c["count60"]:,} Events ≥60 · {c["ordinance_events"]:,} Repeated Noise Violations.</div></div></div><div class="check"><span class="dot"></span><div><b>Every event count says Events.</b><div class="small">Hours remain labeled Hours; event counts remain unmistakably event counts.</div></div></div><div class="check"><span class="dot"></span><div><b>Counting rule is visible.</b><div class="small">The nighttime-window graphic and plain-language rule explain exactly how the conservative subset is derived.</div></div></div><div class="check"><span class="dot"></span><div><b>Five calculation checks and five publication checks passed.</b><div class="small">HDF and EHZ remain separate, gaps are excluded, UTC processing cutoffs map to Eastern display times, arithmetic reconciles, and stale values are rejected.</div></div></div></div></section>'''
replace_one(r'<section class="section panel"><h2>Publication integrity</h2>.*?</section>', publication_integrity, 'publication integrity panel')

footer = (
    '<footer><div class="wrap">R6E8A public dashboard · HDF live status through '
    f'{date_time_et(hdf_latest)} · EHZ live status through {date_time_et(ehz_latest)} · '
    f'five-check 4–8 Hz totals through {date_time_et(latest_complete, seconds=False)} complete HDF minute.</div></footer>'
)
replace_one(r'<footer><div class="wrap">.*?</div></footer>', footer, 'footer')

# Update primary-threshold wording anywhere else without altering the independent 30-minute ordinance rule.
s = s.replace('≥15-minute', '≥10-minute').replace('≥15 minutes', '≥10 minutes')
s = s.replace('15+ minute', '10+ minute').replace('at least 15 minutes', 'at least 10 minutes')

# Five publication-integrity checks.
publish_checks = []
publish_checks.append((
    '1_candidate_identity_scope_and_fresh_edge',
    cand['station'] == 'AM.R6E8A.00' and cand['channel'] == 'HDF' and cand['all_five_checks_pass']
    and str(cand['analysis_start_et']).startswith('2026-04-12T00:00:00')
    and dt_et(latest_complete) <= dt_et(latest_cum)
    and abs((dt_et(cand['requested_through_utc']) - dt_et(latest_cum)).total_seconds()) <= 120
    and timedelta(0) <= dt_et(latest_cum) - dt_et(latest_complete) <= timedelta(minutes=2)
))
publish_checks.append((
    '2_current_channels_separate_and_covered',
    hdf.get('ok') and ehz.get('ok') and float(hdf['coverage_pct']) >= 99.0 and float(ehz['coverage_pct']) >= 99.0
    and hdf.get('channel') == 'HDF' and ehz.get('channel') == 'EHZ'
    and timedelta(0) <= dt_et(status['generated_utc']) - dt_et(hdf_latest) <= timedelta(minutes=50)
    and timedelta(0) <= dt_et(status['generated_utc']) - dt_et(ehz_latest) <= timedelta(minutes=50)
))
publish_checks.append((
    '3_arithmetic_nested_thresholds_and_percent',
    c['mins10'] + c['shorter10_minutes'] == c['dom48_minutes']
    and c['count10'] >= c['count15'] >= c['count30'] >= c['count60']
    and c['mins10'] >= c['mins15'] >= c['mins30'] >= c['mins60']
    and abs(c['dom48_hours'] - c['dom48_minutes'] / 60.0) <= 0.0051
    and abs(c['dom48_percent_of_analyzed'] - 100.0 * c['dom48_minutes'] / c['analyzed_minutes']) <= 0.0051
))
publish_checks.append((
    '4_dashboard_values_dates_and_cutoffs_reconciled',
    f'<div class="stat-number">{c["count10"]:,}<span>Events</span></div>' in s
    and f'<div class="stat-number">{c["count30"]:,}<span>Events</span></div>' in s
    and f'<div class="violation-number">{c["ordinance_events"]:,}</div>' in s
    and 'Repeated Noise Violations' in s
    and date_time_et(hdf_latest) in s and date_time_et(ehz_latest) in s
    and date_time_et(latest_complete, seconds=False) in s
    and 'Aug. 25, 2026' not in s and 'data through Aug. 25, 2026' not in s
))
publish_checks.append((
    '5_wording_gap_and_channel_guard',
    '≥15 minutes' not in s and '≥15-minute' not in s and 'at least 15 minutes' not in s
    and 'reporting/event-definition choice, not a medical or legal exposure limit' in s
    and 'All Figures On This Dashboard Can Be Self-Verified By Any Visitor' in s
    and f'<div class="stat-date">Occurred: {longest_date_label}</div>' in s
    and '*Account for up to 30 minutes of lag.' in s
    and 'Missing acquisition time is never scored as zero' in s
    and 'HDF pressure/infrasound and EHZ vertical/seismic motion remain separate channels' in s
))

for name, passed in publish_checks:
    print(f'{name}: {"PASS" if passed else "FAIL"}')
if not all(p for _n, p in publish_checks):
    raise SystemExit('Five publication-integrity checks did not all pass; dashboard not written.')

INDEX.write_text(s, encoding='utf-8')
print(json.dumps({
    'published_candidate_generated_utc': cand['generated_utc'],
    'analysis_start_et': cand['analysis_start_et'],
    'latest_hdf_sample_et': time_et(latest_cum),
    'dom48_minutes': c['dom48_minutes'],
    'dom48_hours': c['dom48_hours'],
    'count10': c['count10'], 'hours10': c['hours10'],
    'count30': c['count30'], 'hours30': c['hours30'],
    'count60': c['count60'], 'hours60': c['hours60'],
    'ordinance_events': c['ordinance_events'],
    'longest_run_minutes': longest_minutes,
    'calculation_checks': cand['checks'],
    'publication_checks': [{'name': n, 'pass': p} for n, p in publish_checks],
}, indent=2))

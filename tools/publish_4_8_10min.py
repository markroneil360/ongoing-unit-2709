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
from datetime import datetime
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
longest_minutes = int(c["longest_runs"][0]["duration_minutes"]) if c.get("longest_runs") else 0
longest_label = duration_label(longest_minutes)

status_html = (
    '<div class="status"><strong>LIVE CHANNEL CHECK: '
    f'HDF {time_et(hdf_latest)} / EHZ {time_et(ehz_latest)}</strong><br>'
    f'Both channels verified separately at <b>{float(hdf["coverage_pct"]):.1f}% HDF</b> and '
    f'<b>{float(ehz["coverage_pct"]):.1f}% EHZ acquisition coverage</b> in the current status window. '
    f'The cumulative HDF 4–8 Hz spectral calculation starts <b>April 12, 2026</b> and is five-check verified through '
    f'<b>{time_et(latest_cum)}</b> returned HDF sample / <b>{time_et(latest_complete, seconds=False)}</b> complete analyzed minute.'
    '<div class="small">*Account for up to 30 minutes of lag. Missing acquisition time is never scored as zero, quiet, normal, compliant, or below benchmark.</div></div>'
)
replace_one(r'<div class="status">.*?</div><div class="download-actions">',
            status_html + '<div class="download-actions">', 'live status')

main_cards = f'''<section class="section grid g3"><article class="card primary"><div class="label">Total documented 4–8 Hz dominant activity</div><div class="value">{rounded_hours:,} Hours</div><div class="detail">Exact current total: <b>{exact_hours:,.2f} Hours</b> · {c["dom48_minutes"]:,} valid 4–8 Hz-dominant minutes · {c["dom48_percent_of_analyzed"]:.2f}% of analyzed HDF time</div></article><article class="card alert"><div class="label">Conservative nighttime ordinance subset</div><div class="value">{c["ordinance_events"]:,}<span class="events-word">Events</span></div><div class="detail">Requires ≥30-minute sustained event and ≥30 actual minutes inside the applicable nighttime window</div></article><article class="card blue"><div class="label">Repeated low-frequency activity · sustained 4–8 Hz ≥10 minutes</div><div class="value">{c["count10"]:,}<span class="events-word">Events</span></div><div class="detail">{c["hours10"]:,.2f} cumulative Hours in consecutive 10+ minute 4–8 Hz-dominant runs</div></article></section>'''
replace_one(r'<section class="section grid g3"><article class="card primary">.*?</section>', main_cards, 'headline cards')

w10 = pct(c["hours10"], exact_hours)
w30 = pct(c["hours30"], exact_hours)
w60 = pct(c["hours60"], exact_hours)
recon = f'''<section class="section panel"><h2>How the {exact_hours:,.2f} Hours reconciles</h2><div class="recon"><div class="rr"><div><b>All documented 4–8 Hz dominant activity</b></div><div><b>{exact_hours:,.2f} Hours</b></div><div class="track"><div class="fill" style="width:100%"></div></div></div><div class="rr"><div><b>Repeated low-frequency runs ≥10 minutes</b><div class="small">{c["count10"]:,} Events</div></div><div><b>{c["hours10"]:,.2f} Hours</b></div><div class="track"><div class="fill blue" style="width:{w10:.2f}%"></div></div></div><div class="rr"><div><b>Sustained runs ≥30 minutes</b><div class="small">{c["count30"]:,} Events</div></div><div><b>{c["hours30"]:,.2f} Hours</b></div><div class="track"><div class="fill red" style="width:{w30:.2f}%"></div></div></div><div class="rr"><div><b>Sustained runs ≥60 minutes</b><div class="small">{c["count60"]:,} Events</div></div><div><b>{c["hours60"]:,.2f} Hours</b></div><div class="track"><div class="fill amber" style="width:{w60:.2f}%"></div></div></div></div><div class="math"><b>{c["mins10"]:,} minutes</b> in consecutive ≥10-minute 4–8 Hz runs + <b>{c["shorter10_minutes"]:,} minutes</b> in shorter 4–8 Hz segments = <b>{c["dom48_minutes"]:,} minutes = {exact_hours:,.2f} Hours total.</b> Hour subtotals shown above are independently rounded to two decimals.</div></section>'''
replace_one(r'<section class="section panel"><h2>How the .*?</section>', recon, 'reconciliation')

ordinance = f'''<section class="section panel ordinance"><div class="label">Most important legal-facing benchmark</div><div class="value">{c["ordinance_events"]:,}<span class="events-word">Events</span></div><h2>Potential Sustained Noise-Ordinance Events</h2><div class="source-pill">SOURCE ATTRIBUTION: UNKNOWN — PENDING INVESTIGATION</div><p>This figure is intentionally conservative. It does not count every 4–8 Hz minute and it does not count every 10+ minute repeated low-frequency event. It counts only the subset of sustained 30+ minute events that also contains at least 30 actual minutes inside the applicable nighttime ordinance window. One distinct event is counted once; overlapping criteria do not multiply the total.</p><div class="clock"><div class="label">Nighttime-window visual</div><div class="clockbar"><div class="night">12 AM–7 AM</div><div class="day">7 AM–10 PM</div><div class="late">10 PM–12 AM</div></div><div class="legend"><span>General nighttime window: 10 PM–7 AM</span><span>Friday/Saturday conservative downtown start: 11 PM</span></div></div></section>'''
replace_one(r'<section class="section panel ordinance">.*?</section>', ordinance, 'ordinance panel')

ord_pct = pct(c["ordinance_events"], c["count30"])
funnel = f'''<section class="section panel"><h2>Conservative ordinance qualification funnel</h2><div class="funnel"><div class="rr"><div><b>1 · Total documented 4–8 Hz activity</b><div class="small">{c["dom48_minutes"]:,} minutes</div></div><div><b>{exact_hours:,.2f} Hours</b></div><div class="track"><div class="fill" style="width:100%"></div></div></div><div class="rr"><div><b>2 · Repeated low-frequency runs ≥10 minutes</b><div class="small">{c["count10"]:,} Events</div></div><div><b>{c["hours10"]:,.2f} Hours</b></div><div class="track"><div class="fill blue" style="width:{w10:.2f}%"></div></div></div><div class="rr"><div><b>3 · Sustained ≥30 minutes</b><div class="small">{c["count30"]:,} Events</div></div><div><b>{c["hours30"]:,.2f} Hours</b></div><div class="track"><div class="fill red" style="width:{w30:.2f}%"></div></div></div><div class="rr"><div><b>4 · Nighttime ordinance-window subset</b><div class="small">{c["ordinance_events"]:,} Events · {ord_pct:.2f}% of the 30+ minute event pool</div></div><div><b>{c["ordinance_events"]:,} Events</b></div><div class="track"><div class="fill amber" style="width:{ord_pct:.2f}%"></div></div></div></div><div class="math"><b>Why {c["ordinance_events"]:,} is conservative:</b> the legal-facing calculation still requires a 30+ minute run and then applies a second filter requiring at least 30 actual minutes during the nighttime ordinance window. The new 10-minute threshold defines repeated low-frequency activity; it does not lower the separate ordinance qualification rule. Missing time is excluded, not treated as compliant.</div></section>'''
replace_one(r'<section class="section panel"><h2>Conservative ordinance qualification funnel</h2>.*?</section>', funnel, 'ordinance funnel')

# Replace the first explanatory card while retaining the two externally sourced context cards.
why = f'''<article class="info-box"><div class="label">Why {rounded_hours:,} Hours matters</div><p><b>{exact_hours:,.2f} Hours</b> is cumulative documented environmental time in which 4–8 Hz was the dominant HDF band. Under the revised reporting definition, it includes <b>{c["count10"]:,} Events</b> lasting at least 10 consecutive complete minutes, <b>{c["count30"]:,} Events</b> lasting at least 30 minutes, and a longest documented continuous 4–8 Hz-dominant run of <b>{longest_label}</b>. This makes duration and recurrence central facts for a reviewer rather than treating the record as isolated peaks.</p><div class="src">R6E8A HDF archive calculation from Apr. 12, 2026 through {short_date_time_et(latest_cum)}. The ≥10-minute threshold is a reporting/event-definition choice, not a medical or legal exposure limit.</div></article>'''
replace_one(r'<article class="info-box"><div class="label">Why .*?</article>', why, 'duration context card')

boundary = f'''<section class="section context-note"><b>Evidence boundary for legal review:</b> the station documents environmental pressure/infrasound timing, frequency-band dominance, recurrence and duration. The {exact_hours:,.2f}-hour environmental record and the ≥10-minute repeated-low-frequency event definition are environmental signal metrics, not automatically a personal medical dose or a health threshold. Source attribution and individual medical causation require independent investigation/onsite validation.</section>'''
replace_one(r'<section class="section context-note"><b>Evidence boundary for legal review:</b>.*?</section>', boundary, 'evidence boundary')

# Update primary-threshold wording anywhere else without altering the independent 30-minute ordinance rule.
s = s.replace('≥15-minute', '≥10-minute').replace('≥15 minutes', '≥10 minutes')
s = s.replace('15+ minute', '10+ minute').replace('at least 15 minutes', 'at least 10 minutes')

# Five publication-integrity checks.
publish_checks = []
publish_checks.append((
    '1_candidate_identity_and_scope',
    cand['station'] == 'AM.R6E8A.00' and cand['channel'] == 'HDF' and cand['all_five_checks_pass']
    and str(cand['analysis_start_et']).startswith('2026-04-12T00:00:00')
))
publish_checks.append((
    '2_current_channel_continuity_separate',
    hdf.get('ok') and ehz.get('ok') and float(hdf['coverage_pct']) >= 99.0 and float(ehz['coverage_pct']) >= 99.0
))
publish_checks.append((
    '3_10min_arithmetic',
    c['mins10'] + c['shorter10_minutes'] == c['dom48_minutes']
    and c['count10'] >= c['count30'] >= c['count60']
    and c['mins10'] >= c['mins30'] >= c['mins60']
))
publish_checks.append((
    '4_dashboard_duplicate_consistency',
    s.count(f'{c["count10"]:,}<span class="events-word">Events</span>') >= 1
    and f'{c["count10"]:,} Events</div></div><div><b>{c["hours10"]:,.2f} Hours</b>' in s
    and f'{c["count30"]:,} Events</div></div><div><b>{c["hours30"]:,.2f} Hours</b>' in s
    and f'{c["ordinance_events"]:,}<span class="events-word">Events</span>' in s
))
publish_checks.append((
    '5_threshold_wording_and_evidence_boundary',
    '≥15 minutes' not in s and '≥15-minute' not in s and 'at least 15 minutes' not in s
    and 'reporting/event-definition choice, not a medical or legal exposure limit' in s
    and '*Account for up to 30 minutes of lag.' in s
    and 'Missing acquisition time is never scored as zero' in s
    and 'HDF pressure/infrasound' in s
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

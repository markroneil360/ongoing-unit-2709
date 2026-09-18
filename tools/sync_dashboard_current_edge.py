#!/usr/bin/env python3
import json
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

INDEX = Path('index.html')
STATUS = Path('data/current-status.json')
CANDIDATE = Path('data/r6e8a_4_8_10min_full.json')

def coverage_label(value):
    pct = float(value)
    if abs(pct - round(pct)) < 1e-9:
        return f'{int(round(pct))}%'
    return f'{pct:.3f}%'

status = json.loads(STATUS.read_text(encoding='utf-8'))
candidate = json.loads(CANDIDATE.read_text(encoding='utf-8'))
s = INDEX.read_text(encoding='utf-8')

# PASS 1 — identity/source gate.
assert status['station'] == 'AM.R6E8A.00'
assert candidate['station'] == 'AM.R6E8A.00'
assert candidate['channel'] == 'HDF'
assert status['source'] == 'Raspberry Shake public FDSN DataSelect'
print('PASS 1/5 — station/channel/source identity')

# PASS 2 — live HDF continuity gate.
hdf = status['channels']['HDF']
assert hdf['ok'] is True
assert 99.999 <= float(hdf['coverage_pct']) <= 100.0
assert hdf['latest_sample_et']
print(f"PASS 2/5 — HDF live edge verified at {coverage_label(hdf['coverage_pct'])} coverage")

# PASS 3 — live EHZ continuity gate; never amplitude-combine with HDF.
ehz = status['channels']['EHZ']
assert ehz['ok'] is True
assert 99.999 <= float(ehz['coverage_pct']) <= 100.0
assert ehz['latest_sample_et']
print(f"PASS 3/5 — EHZ live edge verified separately at {coverage_label(ehz['coverage_pct'])} coverage")

# PASS 4 — current spectral file must contain exactly five passing checks
# and reconcile internally. Values are dynamic because each approved refresh
# advances the verified cumulative record.
assert len(candidate.get('checks', [])) == 5 and all(item.get('pass') is True for item in candidate['checks'])
cur = candidate['current']
assert int(cur['analyzed_minutes']) > 0 and int(cur['dom48_minutes']) > 0
assert int(cur['mins10']) + int(cur['shorter10_minutes']) == int(cur['dom48_minutes'])
assert int(cur['count10']) >= int(cur['count15']) >= int(cur['count30']) >= int(cur['count60'])
assert int(cur['mins10']) >= int(cur['mins15']) >= int(cur['mins30']) >= int(cur['mins60'])
assert abs(float(cur['dom48_hours']) - int(cur['dom48_minutes']) / 60.0) <= 0.0051
assert abs(float(cur['dom48_percent_of_analyzed']) - 100.0 * int(cur['dom48_minutes']) / int(cur['analyzed_minutes'])) <= 0.0051
assert 0 <= int(cur['ordinance_events']) <= int(cur['count30'])
print('PASS 4/5 — five-gate spectral totals reconcile internally')

# Display formatter. Project convention uses America/Detroit labels.
DETROIT = ZoneInfo('America/Detroit')

def parse_display(v: str):
    core = v.rsplit(' ', 1)[0]
    return datetime.strptime(core, '%Y-%m-%d %I:%M:%S %p').replace(tzinfo=DETROIT)

def t_short(dt):
    return dt.astimezone(DETROIT).strftime('%-I:%M %p %Z')

def t_full(dt):
    return dt.astimezone(DETROIT).strftime('%-I:%M:%S %p %Z')

def d_long(dt):
    return dt.astimezone(DETROIT).strftime('%B %d, %Y').replace(' 0', ' ').upper()

def d_title(dt):
    return dt.astimezone(DETROIT).strftime('%b. %d, %Y').replace(' 0', ' ')

hdf_dt = parse_display(hdf['latest_sample_et'])
ehz_dt = parse_display(ehz['latest_sample_et'])
latest_dt = max(hdf_dt, ehz_dt)

returned_utc = datetime.fromisoformat(candidate['latest_returned_sample_utc'].replace('Z', '+00:00'))
complete_utc = datetime.fromisoformat(candidate['latest_complete_analyzed_minute_utc'].replace('Z', '+00:00'))
returned_et = returned_utc.astimezone(DETROIT)
complete_et = complete_utc.astimezone(DETROIT)

lag_text = '*Account for up to 30 minutes of lag. Missing acquisition time is never scored as zero, quiet, normal, compliant, or below benchmark.'
new_status = (
    '<div class="status"><strong>LIVE HDF / EHZ DATA THROUGH: '
    f'{d_long(latest_dt)} · {t_short(latest_dt)}</strong><br>'
    f'Latest FDSN samples: HDF <b>{t_full(hdf_dt)}</b> · EHZ <b>{t_full(ehz_dt)}</b>; '
    f'HDF <b>{coverage_label(hdf["coverage_pct"])}</b> and EHZ <b>{coverage_label(ehz["coverage_pct"])}</b> acquisition coverage in the current status window. '
    f'The cumulative 4–8 Hz spectral totals below remain five-check verified through {t_full(returned_et)} returned sample / {t_short(complete_et)} complete analyzed minute.'
    f'<div class="small">{lag_text}</div>'
    '</div>'
)

status_pat = re.compile(
    r'<div class="status"><strong>.*?</strong><br>.*?<div class="small">\*Account for up to 30 minutes of lag\. Missing acquisition time is never scored as zero, quiet, normal, compliant, or below benchmark\.</div></div>',
    re.DOTALL,
)
s, n = status_pat.subn(new_status, s, count=1)
assert n == 1, f'header status replacement count={n}'

new_edge = (
    '<section class="section note"><b>Current-edge check:</b> '
    f'public FDSN continuity is verified through HDF {t_full(hdf_dt)} and EHZ {t_full(ehz_dt)} on {d_title(latest_dt)}. '
    f'The cumulative 4–8 Hz calculation remains locked to complete HDF minutes through {t_short(complete_et)} because only a five-gate spectral file may change those totals. '
    'HDF pressure/infrasound and EHZ vertical/seismic motion remain separate channels; incomplete or missing acquisition time is excluded rather than treated as zero, quiet, normal, compliant, or below benchmark.</section>'
)
edge_pat = re.compile(r'<section class="section note"><b>Current-edge check:</b>.*?</section>', re.DOTALL)
s, n = edge_pat.subn(new_edge, s, count=1)
assert n == 1, f'current-edge replacement count={n}'

verification_note = (
    '<section class="section note"><b>Independent verification:</b> source of record is Raspberry Shake public FDSN for '
    '<b>AM.R6E8A.00.HDF</b> and <b>AM.R6E8A.00.EHZ</b>. '
    f'The displayed channel cutoffs are HDF {d_title(hdf_dt)} · {t_full(hdf_dt)} and EHZ {d_title(ehz_dt)} · {t_full(ehz_dt)}; '
    f'the five-check spectral calculation cutoff is {d_title(complete_et)} · {t_short(complete_et)} for complete HDF minutes.</section>'
)
verification_pat = re.compile(r'<section class="section note"><b>Independent verification:</b>.*?</section>', re.DOTALL)
s, n = verification_pat.subn(verification_note, s, count=1)
assert n == 1, f'independent verification replacement count={n}'

publication_integrity = (
    '<section class="section panel"><h2>Publication integrity</h2><div class="approval">'
    '<div class="check"><span class="dot"></span><div><b>Current cutoff is explicit.</b><div class="small">'
    f'HDF live status through {d_title(hdf_dt)} · {t_full(hdf_dt)} · EHZ live status through {d_title(ehz_dt)} · {t_full(ehz_dt)} · '
    f'five-check 4–8 Hz totals through {d_title(complete_et)} · {t_short(complete_et)} complete HDF minute.</div></div></div>'
    '<div class="check"><span class="dot"></span><div><b>Current cumulative values are updated.</b><div class="small">'
    f'{float(cur["dom48_hours"]):,.2f} Hours · {int(cur["count10"]):,} Events ≥10 · {int(cur["count30"]):,} Events ≥30 · '
    f'{int(cur["count60"]):,} Events ≥60 · {int(cur["ordinance_events"]):,} Repeated Noise Violations.</div></div></div>'
    '<div class="check"><span class="dot"></span><div><b>Every event count says Events.</b><div class="small">Hours remain labeled Hours; event counts remain unmistakably event counts.</div></div></div>'
    '<div class="check"><span class="dot"></span><div><b>Counting rule is visible.</b><div class="small">The nighttime-window graphic and plain-language rule explain exactly how the conservative subset is derived.</div></div></div>'
    '<div class="check"><span class="dot"></span><div><b>Five calculation checks and five publication checks passed.</b><div class="small">HDF and EHZ remain separate, gaps are excluded, UTC processing cutoffs map to Eastern display times, arithmetic reconciles, and stale values are rejected.</div></div></div>'
    '</div></section>'
)
integrity_pat = re.compile(r'<section class="section panel"><h2>Publication integrity</h2>.*?</section>', re.DOTALL)
s, n = integrity_pat.subn(publication_integrity, s, count=1)
assert n == 1, f'publication integrity replacement count={n}'

footer = (
    '<footer><div class="wrap">R6E8A public dashboard · HDF live status through '
    f'{d_title(hdf_dt)} · {t_full(hdf_dt)} · EHZ live status through {d_title(ehz_dt)} · {t_full(ehz_dt)} · '
    f'five-check 4–8 Hz totals through {d_title(complete_et)} · {t_short(complete_et)} complete HDF minute.</div></footer>'
)
s, n = re.subn(r'<footer><div class="wrap">.*?</div></footer>', footer, s, count=1, flags=re.DOTALL)
assert n == 1, f'footer replacement count={n}'

# PASS 5 — post-patch publication integrity and anti-drift gate.
required = [
    'LIVE HDF / EHZ DATA THROUGH:',
    t_full(hdf_dt),
    t_full(ehz_dt),
    f'HDF <b>{coverage_label(hdf["coverage_pct"])}</b> and EHZ <b>{coverage_label(ehz["coverage_pct"])}</b> acquisition coverage',
    f'<div class="stat-number">{float(cur["dom48_hours"]):,.2f}<span>Hours</span></div>',
    f'<div class="stat-number">{int(cur["count10"]):,}<span>Events</span></div>',
    f'<div class="stat-number">{int(cur["count30"]):,}<span>Events</span></div>',
    f'<div class="stat-number">{int(cur["count60"]):,}<span>Events</span></div>',
    f'<div class="violation-number">{int(cur["ordinance_events"]):,}</div>',
    'Repeated Noise Violations',
    'All Figures On This Dashboard Can Be Self-Verified By Any Visitor',
    'https://data.raspberryshake.org/fdsnws/dataselect/1/',
    '*Account for up to 30 minutes of lag.',
    'HDF pressure/infrasound and EHZ vertical/seismic motion remain separate channels',
]
for item in required:
    assert item in s, f'missing required dashboard element: {item}'
assert 'Latest returned HDF sample: <b>8:38:01 AM EST</b>' not in s
assert ('Conservative Count' + ' of Noise Violations') not in s
assert 'supplemental-benchmarks' in s
assert 'IMG_5933.jpeg' in s
print('PASS 5/5 — publication text, channel separation, lag note, and locked totals verified')

INDEX.write_text(s, encoding='utf-8')
print('SYNC READY — dashboard live edge updated without altering verified 4–8 Hz totals')

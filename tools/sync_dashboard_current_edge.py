#!/usr/bin/env python3
import json
import re
from datetime import datetime
from pathlib import Path

INDEX = Path('index.html')
STATUS = Path('data/current-status.json')
CANDIDATE = Path('data/r6e8a_4_8_refresh_candidate.json')

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
assert float(hdf['coverage_pct']) == 100.0
assert hdf['latest_sample_et']
print('PASS 2/5 — HDF live edge verified at 100% coverage')

# PASS 3 — live EHZ continuity gate; never amplitude-combine with HDF.
ehz = status['channels']['EHZ']
assert ehz['ok'] is True
assert float(ehz['coverage_pct']) == 100.0
assert ehz['latest_sample_et']
print('PASS 3/5 — EHZ live edge verified separately at 100% coverage')

# PASS 4 — spectral candidate must still be the five-check verified source for 4–8 Hz totals.
assert candidate.get('all_five_checks_pass') is True
cur = candidate['current']
assert cur['dom48_minutes'] == 57210
assert abs(float(cur['dom48_hours']) - 953.5) < 1e-9
assert abs(float(cur['dom48_percent_of_analyzed']) - 36.83) < 1e-9
assert cur['count15'] == 612 and cur['count30'] == 325 and cur['count60'] == 160
assert cur['ordinance_events'] == 75
print('PASS 4/5 — five-gate spectral totals remain locked and unchanged')

# Display formatter. Project convention uses Eastern-time labels on the public dashboard.
def parse_display(v: str):
    # Example: 2026-08-17 06:20:47 PM EDT
    core = v.rsplit(' ', 1)[0]
    return datetime.strptime(core, '%Y-%m-%d %I:%M:%S %p')

def t_short(dt):
    return dt.strftime('%I:%M %p').lstrip('0') + ' EST'

def t_full(dt):
    return dt.strftime('%I:%M:%S %p').lstrip('0') + ' EST'

def d_long(dt):
    return dt.strftime('%B %d, %Y').replace(' 0', ' ').upper()

def d_title(dt):
    return dt.strftime('%b. %d, %Y').replace(' 0', ' ')

hdf_dt = parse_display(hdf['latest_sample_et'])
ehz_dt = parse_display(ehz['latest_sample_et'])
latest_dt = max(hdf_dt, ehz_dt)

# Current verified spectral cutoff from candidate: latest returned 08:38:01, latest complete 08:37.
returned_utc = datetime.fromisoformat(candidate['latest_returned_sample_utc'].replace('Z', '+00:00'))
complete_utc = datetime.fromisoformat(candidate['latest_complete_analyzed_minute_utc'].replace('Z', '+00:00'))
# August Detroit offset is UTC-4; dashboard project convention labels Eastern as EST.
from datetime import timedelta
returned_et = returned_utc - timedelta(hours=4)
complete_et = complete_utc - timedelta(hours=4)

lag_text = '*Account for up to 30 minutes of lag. Missing acquisition time is never scored as zero, quiet, normal, compliant, or below benchmark.'
new_status = (
    '<div class="status"><strong>LIVE HDF / EHZ DATA THROUGH: '
    f'{d_long(latest_dt)} · {t_short(latest_dt)}</strong><br>'
    f'Latest FDSN samples: HDF <b>{t_full(hdf_dt)}</b> · EHZ <b>{t_full(ehz_dt)}</b>; '
    'both channels verified at <b>100% acquisition coverage</b> in the current status window. '
    f'The cumulative 4–8 Hz spectral totals below remain five-check verified through {t_full(returned_et)} returned sample / {t_short(complete_et)} complete analyzed minute.'
    f'<div class="small">{lag_text}</div></div>'
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
    f'The cumulative 4–8 Hz calculation remains locked to complete HDF minutes through {t_short(complete_et)} because only a five-gate spectral candidate may change those totals. '
    'HDF pressure/infrasound and EHZ vertical/seismic motion remain separate channels; incomplete or missing acquisition time is excluded rather than treated as zero, quiet, normal, compliant, or below benchmark.</section>'
)
edge_pat = re.compile(r'<section class="section note"><b>Current-edge check:</b>.*?</section>', re.DOTALL)
s, n = edge_pat.subn(new_edge, s, count=1)
assert n == 1, f'current-edge replacement count={n}'

# Update the first publication-integrity current-cutoff sentence without touching measured totals.
s = re.sub(
    r'The dashboard prominently states HDF data through .*? EST\.',
    f'The dashboard prominently states live HDF/EHZ continuity through {d_title(latest_dt)} at {t_short(latest_dt)}; 4–8 Hz spectral totals remain locked through {t_short(complete_et)}.',
    s,
    count=1,
)

# Footer makes both cutoffs explicit.
s = re.sub(
    r'R6E8A public dashboard · data through .*? EST\.',
    f'R6E8A public dashboard · live HDF/EHZ through {d_title(latest_dt)} {t_short(latest_dt)} · five-check 4–8 Hz totals through {t_short(complete_et)}.',
    s,
    count=1,
)

# PASS 5 — post-patch publication integrity and anti-drift gate.
required = [
    'LIVE HDF / EHZ DATA THROUGH:',
    t_full(hdf_dt),
    t_full(ehz_dt),
    '100% acquisition coverage',
    '953.50 Hours',
    '57,210 valid 4–8 Hz-dominant minutes',
    '36.83% of analyzed HDF time',
    '612 Events', '325 Events', '160 Events', '75 conservative ordinance Events',
    '*Account for up to 30 minutes of lag.',
    'HDF pressure/infrasound and EHZ vertical/seismic motion remain separate channels',
]
for item in required:
    assert item in s, f'missing required dashboard element: {item}'
assert 'Latest returned HDF sample: <b>8:38:01 AM EST</b>' not in s
print('PASS 5/5 — publication text, channel separation, lag note, and locked totals verified')

INDEX.write_text(s, encoding='utf-8')
print('SYNC READY — dashboard live edge updated without altering verified 4–8 Hz totals')

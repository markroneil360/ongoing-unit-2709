#!/usr/bin/env python3
from pathlib import Path

p = Path('index.html')
s = p.read_text(encoding='utf-8')


def replace(old: str, new: str, min_count: int = 1):
    global s
    n = s.count(old)
    if n < min_count:
        raise SystemExit(f'Expected at least {min_count} occurrence(s), found {n}: {old!r}')
    s = s.replace(old, new)
    print(f'replaced {n}: {old[:80]}')


# Verified candidate: data/r6e8a_4_8_refresh_candidate.json
# Generated 2026-08-17T13:12:20Z; all five validation gates passed.
replace('HDF DATA THROUGH: AUGUST 16, 2026 · 8:29 PM EST',
        'HDF DATA THROUGH: AUGUST 17, 2026 · 8:38 AM EST')
replace('Latest returned HDF sample: <b>8:29:00 PM EST</b>. Cumulative 4–8 Hz dominance uses complete clock-aligned HDF minutes through 8:28 PM EST.',
        'Latest returned HDF sample: <b>8:38:01 AM EST</b>. Cumulative 4–8 Hz dominance uses complete clock-aligned HDF minutes through 8:37 AM EST.')

# Cumulative 4–8 Hz values shown on the public page.
replace('950 Hours', '954 Hours')
replace('950.07 Hours', '953.50 Hours')
replace('57,004', '57,210')
replace('36.87%', '36.83%')
replace('56.33%', '56.13%')
replace('45.98%', '45.82%')
replace('33.88%', '33.76%')
replace('24,893 minutes', '25,099 minutes')

# Verified values that remain unchanged:
# 612 events >=15 min / 535.18 h; 325 events >=30 min / 436.88 h;
# 160 events >=60 min / 321.88 h; 75 nighttime ordinance subset.
# Candidate shorter-segment subtotal is 25,099 min = 418.32 h; the page displays the minute subtotal.

replace('R6E8A HDF archive calculation; current through Aug. 16, 2026, 8:29 PM EST.',
        'R6E8A HDF archive calculation; current through Aug. 17, 2026, 8:38 AM EST.')
replace('The 950.07-hour environmental record', 'The 953.50-hour environmental record')
replace('<section class="section note"><b>Current-edge check:</b> the latest returned HDF sample was 8:29:00 PM EST. The cumulative 4–8 Hz calculation includes only complete clock-aligned minutes through 8:28 PM EST; incomplete or missing acquisition time is excluded rather than treated as zero, quiet, normal, compliant, or below benchmark.</section>',
        '<section class="section note"><b>Current-edge check:</b> the latest returned HDF sample was 8:38:01 AM EST. The cumulative 4–8 Hz calculation includes only complete clock-aligned minutes through 8:37 AM EST; incomplete or missing acquisition time is excluded rather than treated as zero, quiet, normal, compliant, or below benchmark.</section>')
replace('The dashboard prominently states HDF data through Aug. 16 at 8:29 PM EST.',
        'The dashboard prominently states HDF data through Aug. 17 at 8:38 AM EST.')
replace('R6E8A public dashboard · data through Aug. 16, 2026 8:29 PM EST.',
        'R6E8A public dashboard · data through Aug. 17, 2026 8:38 AM EST.')

# Explicit stale-value gates before write.
for forbidden in (
    '950.07 Hours', '950.07-hour', '57,004', '36.87%',
    '56.33%', '45.98%', '33.88%', '24,893 minutes',
    'AUGUST 16, 2026 · 8:29 PM EST', 'Aug. 16, 2026, 8:29 PM EST',
    'Aug. 16 at 8:29 PM EST', 'Aug. 16, 2026 8:29 PM EST'
):
    if forbidden in s:
        raise SystemExit(f'Stale dashboard value remains: {forbidden}')

required = (
    '954 Hours', '953.50 Hours', 'The 953.50-hour environmental record',
    '57,210 valid 4–8 Hz-dominant minutes', '36.83% of analyzed HDF time',
    '612 Events', '535.18 Hours', '56.13%',
    '325 Events', '436.88 Hours', '45.82%',
    '160 Events', '321.88 Hours', '33.76%',
    '25,099 minutes',
    '75 conservative ordinance Events',
    'HDF DATA THROUGH: AUGUST 17, 2026 · 8:38 AM EST',
    'Latest returned HDF sample: <b>8:38:01 AM EST</b>',
    '*Account for up to 30 minutes of lag.',
    'Download 24 Hour Report', 'Download 7 Day Trailing Report'
)
for item in required:
    if item not in s:
        raise SystemExit(f'Required published value/design element missing: {item}')

p.write_text(s, encoding='utf-8')
print('VERIFIED DASHBOARD PATCH READY — AUG 17 8:38 AM ET')

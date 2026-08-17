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

# Current FDSN edge and cumulative measured HDF values from verified run 31983573493.
replace('HDF DATA THROUGH: AUGUST 15, 2026 · 5:02 PM EST',
        'HDF DATA THROUGH: AUGUST 16, 2026 · 8:29 PM EST')
replace('Latest returned HDF sample: <b>5:02:02 PM EST</b>. The next tested edge at 5:04 PM was not yet present in the public archive.',
        'Latest returned HDF sample: <b>8:29:00 PM EST</b>. Cumulative 4–8 Hz dominance uses complete clock-aligned HDF minutes through 8:28 PM EST.')

replace('941.20 Hours', '950.07 Hours', 1)
replace('941 Hours', '950 Hours', 1)
replace('56,472', '57,004', 1)
replace('36.92%', '36.87%', 1)

replace('608 Events', '612 Events', 1)
replace('532.67 Hours', '535.18 Hours', 1)
replace('56.59%', '56.33%', 1)
replace('324 Events', '325 Events', 1)
replace('435.17 Hours', '436.88 Hours', 1)
replace('46.24%', '45.98%', 1)
replace('159 Events', '160 Events', 1)
replace('320.17 Hours', '321.88 Hours', 1)
replace('34.02%', '33.88%', 1)
replace('408.53 Hours', '414.88 Hours', 1)

replace('74<span class="events-word">Events</span>', '75<span class="events-word">Events</span>', 2)
replace('74 Events · 22.84% of the 30+ minute event pool', '75 Events · 23.08% of the 30+ minute event pool')
replace('<b>74 Events</b>', '<b>75 Events</b>')
replace('width:22.84%', 'width:23.08%')
replace('Why 74 is conservative:', 'Why 75 is conservative:')
replace('<b>74-Event ordinance subset</b>', '<b>75-Event ordinance subset</b>')
replace('74 conservative ordinance Events', '75 conservative ordinance Events')

replace('R6E8A HDF archive calculation; current through Aug. 15, 2026, 5:02 PM EST.',
        'R6E8A HDF archive calculation; current through Aug. 16, 2026, 8:29 PM EST.')
replace('The 941.20-hour environmental record', 'The 950.07-hour environmental record')
replace('<section class="section note"><b>Current-edge check:</b> the last post-5 PM HDF segment analyzed was 4:56–5:02 PM EST and was 4–8 Hz dominant for 6 minutes. Because it remained below the 15-minute sustained threshold, it added to the 941.20-hour total but did <b>not</b> increase the sustained-event or ordinance-event counts.</section>',
        '<section class="section note"><b>Current-edge check:</b> the latest returned HDF sample was 8:29:00 PM EST. The cumulative 4–8 Hz calculation includes only complete clock-aligned minutes through 8:28 PM EST; incomplete or missing acquisition time is excluded rather than treated as zero, quiet, normal, compliant, or below benchmark.</section>')
replace('The dashboard prominently states HDF data through Aug. 15 at 5:02 PM EST.',
        'The dashboard prominently states HDF data through Aug. 16 at 8:29 PM EST.')
replace('R6E8A public dashboard · data through Aug. 15, 2026 5:02 PM EST.',
        'R6E8A public dashboard · data through Aug. 16, 2026 8:29 PM EST.')

# Explicit integrity gates before write.
for forbidden in (
    '941.20 Hours', '941.20-hour', '56,472', '36.92%', '608 Events', '532.67 Hours',
    '324 Events', '435.17 Hours', '159 Events', '320.17 Hours',
    '74 conservative ordinance Events', '74-Event ordinance subset',
    'Aug. 15, 2026, 5:02 PM EST', 'Aug. 15 at 5:02 PM EST'
):
    if forbidden in s:
        raise SystemExit(f'Stale dashboard value remains: {forbidden}')

required = (
    '950.07 Hours', '950.07-hour environmental record',
    '57,004 valid 4–8 Hz-dominant minutes', '36.87% of analyzed HDF time',
    '612 Events', '535.18 Hours', '325 Events', '436.88 Hours',
    '160 Events', '321.88 Hours', '75 conservative ordinance Events',
    'HDF DATA THROUGH: AUGUST 16, 2026 · 8:29 PM EST',
    '*Account for up to 30 minutes of lag.',
    'Download 24 Hour Report', 'Download 7 Day Trailing Report'
)
for item in required:
    if item not in s:
        raise SystemExit(f'Required published value/design element missing: {item}')

p.write_text(s, encoding='utf-8')
print('VERIFIED DASHBOARD PATCH READY')

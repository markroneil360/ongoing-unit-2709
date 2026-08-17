#!/usr/bin/env python3
from pathlib import Path

p = Path('index.html')
s = p.read_text(encoding='utf-8')
old = '<div class="math"><b>535.18 Hours</b> in sustained ≥15-minute runs + <b>414.88 Hours</b> in shorter 4–8 Hz segments = <b>950.07 Hours total.</b></div>'
new = '<div class="math"><b>32,111 minutes</b> in sustained ≥15-minute runs + <b>24,893 minutes</b> in shorter 4–8 Hz segments = <b>57,004 minutes = 950.07 Hours total.</b> Hour subtotals shown above are independently rounded to two decimals.</div>'
if s.count(old) != 1:
    raise SystemExit(f'Expected one rounded reconciliation sentence; found {s.count(old)}')
s = s.replace(old, new, 1)
required = (
    '950.07 Hours', '57,004 valid 4–8 Hz-dominant minutes',
    '<div class="value">325<span class="events-word">Events</span></div><div class="detail">436.88 cumulative Hours',
    '32,111 minutes', '24,893 minutes', '57,004 minutes = 950.07 Hours total.',
    '75 Events · 23.08% of the 30+ minute event pool',
    'HDF DATA THROUGH: AUGUST 16, 2026 · 8:29 PM EST',
    'Download 24 Hour Report', 'Download 7 Day Trailing Report'
)
for item in required:
    if item not in s:
        raise SystemExit(f'Required consistency item missing: {item}')
for stale in ('941.20 Hours', '56,472', '74-Event ordinance subset', '324<span class="events-word">Events</span>', '435.17 cumulative Hours'):
    if stale in s:
        raise SystemExit(f'Stale value remains: {stale}')
p.write_text(s, encoding='utf-8')
print('EXACT-MINUTE RECONCILIATION PASS')

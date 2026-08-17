#!/usr/bin/env python3
from pathlib import Path

p = Path('index.html')
s = p.read_text(encoding='utf-8')

old_count = '<div class="value">324<span class="events-word">Events</span></div><div class="detail">435.17 cumulative Hours in sustained 30+ minute runs</div>'
new_count = '<div class="value">325<span class="events-word">Events</span></div><div class="detail">436.88 cumulative Hours in sustained 30+ minute runs</div>'

n = s.count(old_count)
if n != 1:
    raise SystemExit(f'Expected exactly one stale top-card tuple; found {n}')
s = s.replace(old_count, new_count, 1)

required = (
    'Exact current total: <b>950.07 Hours</b> · 57,004 valid 4–8 Hz-dominant minutes · 36.87% of analyzed HDF time',
    '<div class="value">325<span class="events-word">Events</span></div><div class="detail">436.88 cumulative Hours in sustained 30+ minute runs</div>',
    '<div class="small">325 Events</div></div><div><b>436.88 Hours</b>',
    '75 Events · 23.08% of the 30+ minute event pool',
    'HDF DATA THROUGH: AUGUST 16, 2026 · 8:29 PM EST',
    'Download 24 Hour Report',
    'Download 7 Day Trailing Report'
)
for item in required:
    if item not in s:
        raise SystemExit(f'Required consistency item missing: {item}')

for stale in ('941.20 Hours', '56,472', '74-Event ordinance subset', '324<span class="events-word">Events</span>', '435.17 cumulative Hours'):
    if stale in s:
        raise SystemExit(f'Stale value remains after correction: {stale}')

p.write_text(s, encoding='utf-8')
print('TOP CARD CONSISTENCY PASS')

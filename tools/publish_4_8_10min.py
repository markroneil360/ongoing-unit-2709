#!/usr/bin/env python3
"""Publish a hash-bound R6E8A cache snapshot without changing its design.

Available complete minutes extend the accepted record. Missing intervals stay
excluded for a later device/USB miniSEED patch. Source receipts remain in cache.
"""
from __future__ import annotations
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from generate_reports import load_inputs, tail_stats, runs48

TZ = ZoneInfo('America/Detroit')

def stamp(value, seconds=True):
    d = datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(TZ)
    return d.strftime('%B %-d, %Y · %-I:%M:%S %p %Z' if seconds else '%B %-d, %Y · %-I:%M %p %Z')

def duration(minutes):
    h, m = divmod(int(minutes), 60)
    return f'{h} Hours {m} Minutes' if m else f'{h} Hours'

def render(inputs, html, now):
    candidate, status = inputs['candidate'], inputs['status']
    c = candidate['current']
    checked = now.astimezone(TZ).strftime('%B %-d, %Y · %-I:%M:%S %p %Z')
    hdf, ehz = status['channels']['HDF'], status['channels']['EHZ']
    cutoff = stamp(candidate['latest_complete_analyzed_minute_utc'], False)
    missing = int((inputs['end'] - datetime.fromisoformat(inputs['cache']['start_utc'])).total_seconds() / 60) - len(inputs['minutes'])
    def replace(pattern, value, label):
        nonlocal html
        html, count = re.subn(pattern, lambda _: value, html, flags=re.S)
        if count != 1:
            raise ValueError(f'{label}: expected exactly one matching section, got {count}')
    header = (
        f'<div class="status"><strong>LAST UPDATE: {checked}</strong><br>'
        f'<b>Latest verified samples:</b> HDF {stamp(hdf["latest_sample_utc"])} / EHZ {stamp(ehz["latest_sample_utc"])}. '
        f'Both channels were checked separately: <b>{hdf["coverage_pct"]:.1f}% HDF</b> and <b>{ehz["coverage_pct"]:.1f}% EHZ acquisition coverage</b> in the checked window. '
        f'Cumulative HDF analysis begins <b>April 12, 2026</b>; complete analyzed minutes extend through <b>{cutoff}</b>. '
        f'<b>Offline/missing intervals:</b> {missing:,} unobserved minutes in the cached tail after August 12 are excluded, pending the device-to-USB miniSEED patch. '
        '<div class="small">LAST UPDATE is the publication time, not a measurement time. Verified station recordings and the accepted archive supply the results. '
        'Missing acquisition time is excluded, never scored as zero, quiet, normal, compliant, or below benchmark. HDF pressure and EHZ seismic data remain separate. '
        '*Account for up to 30 minutes of lag.</div></div>'
    )
    replace(r'<div class="status">.*?</div><div class="download-actions">', header + '<div class="download-actions">', 'status')
    summary = re.search(r'<!-- EVIDENCE SUMMARY START -->(.*?)<!-- EVIDENCE SUMMARY END -->', html, re.S)
    if not summary:
        raise ValueError('Evidence summary markers missing')
    content = summary[1]
    old_count = re.search(r'<div class="violation-number">([\d,]+)</div>', content)[1]
    content = content.replace(f'<div class="violation-number">{old_count}</div>', f'<div class="violation-number">{c["ordinance_events"]:,}</div>')
    content = re.sub(r'How the [\d,]+ events were counted', f'How the {c["ordinance_events"]:,} events were counted', content)
    cards = {'Repeated Noise Violations': (f'{c["ordinance_events"]:,}', 'Events'),
             'Documented 4–8 Hz Activity': (f'{c["dom48_hours"]:,.2f}', 'Hours'),
             'Repeated ≥10-Minute Events': (f'{c["count10"]:,}', 'Events'),
             'Sustained ≥30-Minute Events': (f'{c["count30"]:,}', 'Events'),
             'Sustained ≥60-Minute Events': (f'{c["count60"]:,}', 'Events'),
             'Longest Continuous Run': (duration(c['longest_minutes']), '4–8 Hz Dominant')}
    for title, (number, unit) in cards.items():
        pattern = r'(<div class="stat-title">' + re.escape(title) + r'</div><div class="stat-number">).*?</div>'
        content, count = re.subn(pattern, lambda m: m[1] + number + '<span>' + unit + '</span></div>', content)
        if count != 1:
            raise ValueError('Missing or duplicate stat card: ' + title)
    longest = c['longest_runs'][0]
    start = datetime.fromisoformat(longest['start_et'])
    end = datetime.fromisoformat(longest['end_et']) - timedelta(seconds=1)
    dates = start.strftime('%B %-d, %Y') if start.date() == end.date() else start.strftime('%B %-d, %Y') + ' — ' + end.strftime('%B %-d, %Y')
    content = re.sub(r'<div class="stat-date">Occurred: .*?</div>', '<div class="stat-date">Occurred: ' + dates + '</div>', content)
    replace(r'<!-- EVIDENCE SUMMARY START -->.*?<!-- EVIDENCE SUMMARY END -->', '<!-- EVIDENCE SUMMARY START -->' + content + '<!-- EVIDENCE SUMMARY END -->', 'metrics')
    html = re.sub(r'The [\d,.]+-hour environmental record', f'The {c["dom48_hours"]:,.2f}-hour environmental record', html)
    html = re.sub(r'the <b>[\d,]+-Event ordinance subset</b>', f'the <b>{c["ordinance_events"]:,}-Event ordinance subset</b>', html)
    replace(r'<section class="section note"><b>Current-edge check:</b>.*?</section>',
        f'<section class="section note"><b>Current-edge check:</b> Complete HDF minutes extend through {cutoff}. HDF pressure/infrasound and EHZ vertical/seismic motion remain separate channels. Offline and incomplete intervals remain excluded pending the USB miniSEED patch; no interpolation or zero-filling is used.</section>', 'current edge')
    replace(r'<section class="section panel"><h2>Publication integrity</h2>.*?</section>',
        '<section class="section panel"><h2>Publication integrity</h2><div class="approval">'
        f'<div class="check"><span class="dot"></span><div><b>Update time and measurement time are separate.</b><div class="small">LAST UPDATE: {checked}. Complete HDF minutes through {cutoff}.</div></div></div>'
        f'<div class="check"><span class="dot"></span><div><b>Cumulative values retain the uploaded evidence.</b><div class="small">{c["dom48_hours"]:,.2f} Hours · {c["count10"]:,} Events ≥10 · {c["count30"]:,} Events ≥30 · {c["count60"]:,} Events ≥60 · {c["ordinance_events"]:,} Repeated Noise Violations.</div></div></div>'
        '<div class="check"><span class="dot"></span><div><b>Offline intervals remain excluded.</b><div class="small">The future USB miniSEED patch will be reconciled by recording timestamps and hashes; duplicates count once.</div></div></div>'
        '<div class="check"><span class="dot"></span><div><b>Counting rule is unchanged.</b><div class="small">Complete clock minutes, separated channels, and the existing nighttime screen are retained.</div></div></div>'
        '<div class="check"><span class="dot"></span><div><b>Five checks before publication completed.</b><div class="small">Station and cache integrity, duplicate reconciliation, independent cumulative recount, dashboard/report agreement, and the publication snapshot were checked. Public file delivery is verified separately after deployment.</div></div></div></div></section>', 'integrity')
    replace(r'<footer><div class="wrap">.*?</div></footer>',
        f'<footer><div class="wrap">R6E8A public dashboard · LAST UPDATE: {checked} · Complete HDF minutes through {cutoff} · Offline intervals excluded pending the USB miniSEED patch.</div></footer>', 'footer')
    return html

def main():
    inputs = load_inputs(ROOT)
    c = inputs['candidate']['current']
    base = json.loads((ROOT / 'data/r6e8a_4_8_base_10min_2026-08-12.json').read_text())['base']
    post = tail_stats(inputs['minutes'])
    now = datetime.now(timezone.utc)
    channels = inputs['status']['channels']
    fields = ('analyzed_minutes', 'dom48_minutes', 'count10', 'mins10', 'count15', 'mins15', 'count30', 'mins30', 'count60', 'mins60', 'ordinance_events')
    gates = [
        ('1_station_hashes_and_acquisition', inputs['candidate']['all_five_checks_pass'] and all(v['identity_verified'] and v['coverage_pct'] >= 99 for v in channels.values())),
        ('2_duplicate_gap_and_provenance', not inputs['cache'].get('conflicts') and len(inputs['minutes']) == inputs['cache']['minute_count'] and bool(inputs['cache'].get('local_upload_patch', {}).get('raw_files'))),
        ('3_independent_cumulative_recount', all(c[k] == base[k] + post[k] for k in fields) and c['band_counts'] == {k: base['band_counts'].get(k, 0) + post['band_counts'][k] for k in post['band_counts']} and c['mins10'] + c['shorter10_minutes'] == c['dom48_minutes']),
        ('4_measurement_dates_and_freshness', timedelta(0) <= now - inputs['end'] <= timedelta(hours=1) and all(timedelta(0) <= now - datetime.fromisoformat(v['latest_sample_utc']) <= timedelta(hours=1) for v in channels.values())),
    ]
    if not all(v for _, v in gates):
        raise ValueError('Publication gates failed: ' + repr(gates))
    index = ROOT / 'index.html'
    html = render(inputs, index.read_text(), now)
    gates.append(('5_dashboard_snapshot_values_and_gap_disclosure', all(f'<div class="stat-number">{c[k]:,}<span>Events</span></div>' in html for k in ('count10', 'count30', 'count60')) and 'Offline/missing intervals' in html and 'July recording' not in html and 'LAST UPDATE:' in html))
    if not all(v for _, v in gates):
        raise ValueError('Dashboard snapshot failed verification')
    index.write_text(html)
    receipt = {'station': 'AM.R6E8A.00', 'checked_utc': now.isoformat(), 'checked_et': now.astimezone(TZ).isoformat(), 'candidate_sha256': inputs['candidate_sha256'], 'cache_payload_sha256': inputs['cache_payload_sha256'], 'status_sha256': inputs['status_sha256'], 'checks': [{'name': k, 'pass': v} for k, v in gates], 'all_five_checks_pass': True, 'public_delivery': 'Verified separately by deployment workflow', 'offline_patch': 'Pending device-to-USB miniSEED; gaps excluded'}
    (ROOT / 'data/r6e8a-publication-verification.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))

if __name__ == '__main__':
    main()

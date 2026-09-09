# R6E8A — Sep. 9, 2026 comparison analysis checkpoint

**Checkpoint updated:** 2026-09-09 19:41 ET
**Purpose:** Preserve validated calculations and source anchors so analysis resumes from this state after any connection loss, without publishing personal location or presence information.

## Final dashboard state
- Full Apr. 12-to-current HDF 4–8 Hz candidate passed all five calculation gates.
- Dashboard publication passed all five publication-integrity gates.
- Latest five-check spectral endpoint: 2026-09-09 18:34 ET complete HDF minute / 18:34:59 ET returned HDF sample.
- Latest dashboard live-channel status during publication: HDF 18:55:45 ET; EHZ 18:55:43 ET; both 100.0% acquisition coverage in the sampled status window.
- Published totals: 188,851 analyzed HDF minutes; 73,380 4–8 Hz-dominant minutes = 1,223.00 hours = 38.86% of analyzed HDF time; 1,456 >=10-minute runs / 820.17 h; 386 >=30-minute runs / 564.37 h; 189 >=60-minute runs / 426.30 h; 84 conservative nighttime ordinance-subset events; longest continuous 4–8 Hz-dominant run 976 min = 16 h 16 min.
- HDF and EHZ remain separate. Personal location/presence context is intentionally excluded from the dashboard and this cache.

## Direct trailing-96-hour environmental probe — supersedes snapshot subtraction
A dedicated waveform pull was used because differences between cumulative snapshots can be distorted when later FDSN requests backfill minutes that were previously missing. Therefore the earlier snapshot-subtraction interval estimate is **superseded** and must not be treated as an exact interval measurement.

### Probe request and actual acquisition
- Requested environmental window: 2026-09-05 19:12 ET → 2026-09-09 19:12 ET.
- Actual latest samples returned during this specific probe: HDF 2026-09-09 07:12:02 ET; EHZ 2026-09-09 07:12:00 ET.
- Complete analyzed minutes: HDF 5,028; EHZ 5,028. Missing acquisition time was excluded, never scored as zero or quiet.
- All five interval sanity checks: PASS.

### HDF frequency-band result
- 4–8 Hz: 4,959 complete minutes
- 1–4 Hz: 20 complete minutes
- 8–16 Hz: 49 complete minutes
- 4–8 Hz share: **98.628%** of complete HDF minutes
- >=10-minute 4–8 Hz runs: 36 events / 4,902 min = 81.70 h
- >=30-minute runs: 29 events / 4,770 min = 79.50 h
- >=60-minute runs: 17 events / 4,222 min = 70.37 h
- Longest continuous 4–8 Hz-dominant run: 976 min = 16 h 16 min

### HDF daily frequency continuity
- Sep. 5 partial: 94.10% 4–8 Hz dominant
- Sep. 6: 97.92%
- Sep. 7: 99.23%
- Sep. 8: 99.24%
- Sep. 9 through 07:12 ET: 100.00%

### HDF amplitude behavior — raw counts, within-channel only
- 96-hour median RMS: 2,935.33 counts
- mean: 2,970.62
- p95: 3,253.60
- p99: 3,579.50
- maximum minute RMS: 35,175.74 counts at 2026-09-05 19:49 ET, dominant band 1–4 Hz
- This maximum was an isolated extreme amplitude outlier: approximately 12× the overall HDF median and 9.8× the p99.
- Largest HDF hourly mean increase: +4.12% (Sep. 5 21:00→22:00 ET).
- Largest HDF hourly mean drop: -9.70% (Sep. 5 19:00→20:00 ET), influenced by the extreme 19:49 spike in the preceding hour.
- Excluding isolated spikes, HDF hourly background was comparatively stable.

### EHZ behavior — separate seismic/vertical channel
- 96-hour median RMS: 3,658.96 raw counts
- mean: 3,651.73
- p95: 5,352.55
- p99: 7,487.09
- maximum minute RMS: 10,507.06 counts at 2026-09-05 22:43 ET
- EHZ showed materially larger hour-to-hour swings than HDF: largest hourly increase +36.70%; largest hourly drop -22.19%.
- EHZ median by day declined from 4,220.74 counts on the Sep. 5 partial day to 2,241.72 counts through Sep. 9 07:12 ET, while HDF 4–8 Hz dominance became more complete. This supports keeping HDF spectral behavior distinct from EHZ ground-motion amplitude.

## Neutral Sep. 9 transition window — 18:30 to 19:05 ET
A separate current-data probe retrieved both channels through approximately 19:06 ET and passed all five sanity checks. This section stores environmental values only; no personal timing or location label is attached.

### HDF
- 18:30–18:43 ET: predominantly stable 4–8 Hz, roughly 2,837–3,184 raw RMS counts/minute.
- 18:44 ET: 18,747.79 RMS counts, dominant band 1–4 Hz — major isolated spike.
- 18:45 ET: 40,915.11 RMS counts, dominant band 1–4 Hz — largest spike in this transition window, approximately 13.9× the 96-hour HDF median.
- 18:46–18:47 ET: returned to ~3,025–3,112 counts and 4–8 Hz.
- 18:48–18:49 ET: 3,809.99 and 4,123.04 counts, both 1–4 Hz.
- 18:50–19:04 ET: predominantly 4–8 Hz; 19:00 = 3,552.53; 19:01 = 2,998.96; 19:02 = 2,911.63; 19:03 = 2,931.69; 19:04 = 2,814.82 counts.
- 19:05 ET: 3,971.31 counts with a shift to 1–4 Hz; elevated relative to immediately preceding minutes but far below the 18:44–18:45 spikes.

### EHZ
- 19:00 = 3,976.67; 19:01 = 3,788.20; 19:02 = 4,094.76; 19:03 = 3,331.18; 19:04 = 4,165.84; 19:05 = 3,348.88 raw RMS counts.
- EHZ remained variable but within the range already observed in the preceding half hour; there was no unique extreme at 19:03.

### Transition-window interpretation boundary
- The dominant environmental anomalies in this short window are the 18:44–18:45 HDF 1–4 Hz spikes, followed by smaller 1–4 Hz activity at 18:48–18:49 and 19:05.
- HDF at 19:03 and 19:04 remained 4–8 Hz and close to the local background, not an abrupt amplitude spike.
- Environmental measurements alone do not identify a source or intent. Any private comparison to user-provided timing is done outside the public dashboard/cache narrative.

## Interpretation boundary
- The directly measured multi-day interval shows persistent, unusually continuous HDF 4–8 Hz dominance across the available record rather than a broad shutdown or disappearance.
- The HDF background amplitude drifted modestly downward across the available days while 4–8 Hz dominance increased; EHZ ground-motion amplitude changed more substantially and was more variable.
- Environmental measurements alone do not establish source identity, intent, or personal causation.
- Any private presence/absence comparison must use only timestamps actually covered by validated acquisition. Personal timing/location must not be published.

## Resume point after connection loss
1. Treat the published 1,223.00-hour dashboard state as the current validated aggregate checkpoint.
2. Treat the direct trailing-96-hour probe as the authoritative multi-day interval-specific comparison; disregard the earlier cumulative-snapshot subtraction estimate.
3. Treat the neutral 18:30–19:05 ET Sep. 9 probe as the current transition-window checkpoint.
4. For any later private presence/absence question, compare user-provided timing against these environmental timestamps in chat only; never publish that timing/location.

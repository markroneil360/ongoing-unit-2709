# R6E8A — Sep. 9, 2026 comparison analysis checkpoint

**Checkpoint written:** 2026-09-09 19:23 ET
**Purpose:** Preserve calculations and source anchors so analysis resumes from this state after any connection loss, without publishing personal location or presence information.

## Dashboard/update state
- Manual full HDF 4–8 Hz current-tail refresh triggered at 2026-09-09 19:03 ET.
- Approved pipeline requires five calculation validation gates before aggregate publication.
- Separate HDF/EHZ current-edge refresh also triggered.
- Latest completed live-edge status at this checkpoint: HDF 2026-09-09 18:30:24 ET; EHZ 2026-09-09 18:30:24 ET; both 100.0% acquisition coverage in sampled status window.
- Personal location/presence context is intentionally excluded from all public dashboard content and this public cache.

## Five-check-passed comparison anchors
### Anchor A — Sep. 5, 2026
Source commit: 346297e0079e171368285c3e746f7e791a49c3cc
Latest complete analyzed HDF minute: 2026-09-05 18:29 ET
- analyzed_minutes: 183,103
- 4–8 Hz dominant minutes: 67,703
- 4–8 Hz dominant hours: 1,128.38
- 4–8 Hz share of analyzed HDF: 36.98%
- >=10-minute runs: 1,413 events / 43,583 min / 726.38 h
- >=15-minute runs: 694 events / 35,363 min / 589.38 h
- >=30-minute runs: 352 events / 28,419 min / 473.65 h
- >=60-minute runs: 169 events / 20,774 min / 346.23 h
- conservative nighttime ordinance subset: 77 events
- longest continuous 4–8 Hz-dominant run: 664 min / 11.07 h
- all five calculation checks: PASS

### Anchor B — Sep. 8, 2026
Source commit: 28445b85142a98640b898916e22cb5df5eabaa30
Latest complete analyzed HDF minute: 2026-09-08 21:47 ET
- analyzed_minutes: 187,535
- 4–8 Hz dominant minutes: 72,124
- 4–8 Hz dominant hours: 1,202.07
- 4–8 Hz share of analyzed HDF: 38.46%
- >=10-minute runs: 1,448 events / 47,977 min / 799.62 h
- >=15-minute runs: 727 events / 39,731 min / 662.18 h
- >=30-minute runs: 380 events / 32,681 min / 544.68 h
- >=60-minute runs: 186 events / 24,524 min / 408.73 h
- conservative nighttime ordinance subset: 82 events
- longest continuous 4–8 Hz-dominant run: 976 min / 16.27 h
- all five calculation checks: PASS

## Derived interval: Sep. 5 18:29 ET → Sep. 8 21:47 ET
Calculated strictly by subtraction of the two five-check-passed cumulative snapshots:
- newly analyzed HDF minutes: 4,432
- newly 4–8 Hz-dominant minutes: 4,421
- non-4–8 dominant analyzed minutes: 11
- interval 4–8 Hz dominance fraction: **99.75%** (4,421 / 4,432)
- added 4–8 Hz-dominant time: **73.68 hours**
- >=10-minute event count change: +35
- >=10-minute run time change: +4,394 min = **73.23 h**
- >=15-minute event count change: +33
- >=15-minute run time change: +4,368 min = **72.80 h**
- >=30-minute event count change: +28
- >=30-minute run time change: +4,262 min = **71.03 h**
- >=60-minute event count change: +17
- >=60-minute run time change: +3,750 min = **62.50 h**
- conservative nighttime ordinance subset change: +5 events
- longest run increased by 312 min = **5.20 h**, from 11.07 h to 16.27 h

## Interpretation boundary
- The interval shows markedly increased continuity of HDF 4–8 Hz dominance compared with the earlier validated endpoint.
- This is an environmental signal comparison only. It does not establish source attribution, intent, or causation by a person.
- HDF pressure/infrasound and EHZ seismic motion remain separate; amplitudes are not combined.
- Missing acquisition time is excluded, never scored as zero/quiet/compliant.
- Personal location/presence context is reserved for private analytical feedback only and is not published to the dashboard or public cache.

## Resume point
1. Check the active 2026-09-09 full current-tail workflow until the five calculation gates complete.
2. Confirm the resulting commit and read the new `data/r6e8a_4_8_10min_full.json` totals/checks.
3. Confirm downstream publication workflow completed five publication-integrity checks and committed `index.html`.
4. Compare Sep. 5 anchor → new current validated endpoint.
5. Privately compare any user-provided presence/absence timing to the environmental signal record, without publishing that timing or location.

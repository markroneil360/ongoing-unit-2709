# R6E8A Aug. 17, 2026 — SO-FAR CACHE

Canary / continuity: R6E8A-ONGOING
Purpose: preserve verified analysis state before completion of the full-day 12:00 AM–11:30 PM Detroit-time reconstruction.

## User request being fulfilled
Analyze AM.R6E8A.00 for Aug. 17, 2026 from 12:00 AM through 11:30 PM Detroit time, hour by hour. Explain frequencies, increases/decreases, and activity. HDF pressure/infrasound and EHZ vertical motion must remain separate. Sanity check 5x.

## Source hierarchy used
1. User-provided raw Raspberry Shake daily MiniSEED files:
   - AM.R6E8A.00.HDF.D.2026.229
   - AM.R6E8A.00.HDF.D.2026.230
   - AM.R6E8A.00.EHZ.D.2026.229
   - AM.R6E8A.00.EHZ.D.2026.230
2. Raspberry Shake public FDSN DataSelect for current-edge / gap completion.
3. Repository current-status.json only for continuity/status corroboration, not as a substitute for full spectral analysis.

## Locked analysis method
- Complete clock-aligned 60-second windows only.
- Missing or incomplete minutes excluded; never zero-filled and never interpreted as quiet, normal, compliant, or below benchmark.
- Welch PSD using Hann window, 8-second segments, 50% overlap.
- HDF frequency classification bands: 1–4 Hz, 4–8 Hz, 8–16 Hz, 16–20 Hz.
- Dominant band = band with highest mean PSD for the minute.
- Representative peak frequency = maximum Welch PSD bin in 1–20 Hz; hourly value is summarized from minute-level values.
- Increase/decrease = descriptive within-channel change versus the immediately preceding hour, NOT a compliance baseline and NOT a public self-benchmark.
- HDF and EHZ are never amplitude-combined.
- HDF raw amplitude is not relabeled as Pa/dB without calibration support.
- EHZ raw amplitude is not relabeled as calibrated physical motion units without calibration support.

## Verified raw-record reconstruction
- HDF MiniSEED records processed in the requested window: 38,444.
- EHZ MiniSEED records processed in the requested window: 39,509.
- STEIM2 record-end reconstruction mismatches: HDF 0; EHZ 0.
- Overlap conflicts: HDF 0; EHZ 0.
- Both channels yield 1,361 complete clock-aligned minutes from 12:00 AM through the 10:40 PM minute EDT.
- Raw last sample in uploaded files: HDF 10:41:43.281 PM EDT; EHZ 10:41:10.601 PM EDT.
- Therefore 10:41 PM–11:30 PM remains N/A for spectral interpretation from the uploaded daily files unless the public FDSN gap-completion run returns that interval.

## HDF full measured interval so far — 12:00 AM through 10:40 PM EDT
Dominant-minute classification (1,361 complete minutes):
- 4–8 Hz: 569 minutes = 41.81%
- 1–4 Hz: 556 minutes = 40.85%
- 8–16 Hz: 234 minutes = 17.19%
- 16–20 Hz: 2 minutes = 0.15%

For this Aug. 17 measured interval specifically, 4–8 Hz is the largest dominant-minute category by a narrow margin over 1–4 Hz. This statement is day-specific and must not be generalized to the entire historical archive.

## EHZ full measured interval so far — separate vertical-motion context
Dominant-minute classification (1,361 complete minutes):
- 4–8 Hz: 637 minutes = 46.80%
- 1–4 Hz: 410 minutes = 30.12%
- 8–16 Hz: 226 minutes = 16.61%
- 16–20 Hz: 88 minutes = 6.47%

EHZ remains a separate vertical-motion/seismic channel; these counts are not amplitude-combined with HDF.

## Exact 6:30 PM EDT arrival-minute checkpoint
This minute was identified before reviewing the sensor result and is preserved as a chronology checkpoint.

HDF at 6:30 PM EDT:
- Dominant band: 4–8 Hz.
- Peak PSD frequency in 1–20 Hz: 5.875 Hz.
- Raw 1–20 Hz band-limited RMS index increased 55.46% from the 6:29 PM minute.
- Raw 4–8 Hz RMS index increased 57.09% from the 6:29 PM minute.
- Raw indices are descriptive within-channel quantities only, not calibrated Pa or dB.

EHZ at 6:30 PM EDT:
- Dominant band: 1–4 Hz.
- Peak PSD frequency in 1–20 Hz: 3.875 Hz.
- Raw 1–20 Hz RMS index decreased 8.63% from 6:29 PM.
- Raw 4–8 Hz RMS index decreased 10.64% from 6:29 PM.

Interpretive boundary: the HDF result documents a coincident pressure/infrasound spectral change at the announced 6:30 PM arrival minute. The EHZ result documents separate vertical-motion context and does not show the same minute-to-minute increase. This supports reporting the channels separately rather than claiming one caused the other.

## Notable HDF hourly changes already calculated
These are adjacent-hour descriptive changes, not compliance baselines:
- 10:00–11:00 AM: strongest full-hour rise so far; median raw 1–20 Hz RMS +210.70% versus 9:00–10:00 AM; median 4–8 Hz RMS +359.40%; 4–8 Hz dominant in 54 of 60 complete minutes.
- 8:00–9:00 AM: median raw 1–20 Hz RMS +53.12%; median 4–8 Hz RMS +93.99% versus 7:00–8:00 AM.
- 2:00–3:00 PM: median raw 1–20 Hz RMS +13.61%; median 4–8 Hz RMS +29.90% versus 1:00–2:00 PM; 4–8 Hz dominant in 43 of 60 minutes.
- 5:00–6:00 PM: median raw 1–20 Hz RMS -46.72%; median 4–8 Hz RMS -56.22% versus 4:00–5:00 PM.
- 6:00–7:00 PM: median raw 1–20 Hz RMS +7.40%; median 4–8 Hz RMS +2.20% versus 5:00–6:00 PM; 4–8 Hz was the plurality dominant band (24/60 minutes), with the exact 6:30 PM minute at 5.875 Hz peak and 4–8 Hz dominance.
- 7:00–8:00 PM: median raw 1–20 Hz RMS -43.71%; median 4–8 Hz RMS -55.82% versus 6:00–7:00 PM.
- 8:00–9:00 PM: median raw 1–20 Hz RMS +18.86%; median 4–8 Hz RMS +5.06% versus 7:00–8:00 PM.
- 9:00–10:00 PM: median raw 1–20 Hz RMS -27.60%; median 4–8 Hz RMS -4.99% versus 8:00–9:00 PM.
- 10:00–10:40 PM partial hour: median raw 1–20 Hz RMS +5.60% versus the prior full hour; median 4–8 Hz RMS -1.60%. This is a partial-hour comparison and must be labeled as such.

## Five-check framework applied to the raw reconstruction
1. STEIM2 decompression / stored record-end sample reconciliation: PASS (0 mismatches HDF, 0 EHZ).
2. Record continuity / overlap-conflict check: PASS (0 conflicting overlaps in either channel; only the trailing unreturned interval is missing).
3. Complete-minute integrity: PASS (1,361 unique clock-aligned complete minutes per channel; no incomplete minute treated as valid).
4. Frequency-band arithmetic: PASS (HDF and EHZ minute-band counts each sum exactly to 1,361).
5. Channel separation / missing-data boundary: PASS (HDF and EHZ analyzed independently; no interpolation or zero-fill after their actual file edges).

Status at this cache revision: FIVE-CHECK PASS for the measured raw-file interval through the 10:40 PM complete minute. Final 10:41–11:30 PM spectral extension is pending actual FDSN waveform return and must remain N/A until obtained.

## Existing dashboard state that must not be overwritten by inference
Last five-gate cumulative HDF 4–8 Hz spectral totals remain verified through the 8:37 AM EDT complete analyzed minute on Aug. 17, 2026:
- 57,210 4–8 Hz-dominant minutes
- 953.50 Hours
- 36.83% of analyzed HDF time
- 612 Events >=15 min / 535.18 Hours
- 325 Events >=30 min / 436.88 Hours
- 160 Events >=60 min / 321.88 Hours
- 75 conservative nighttime ordinance-subset Events

These cumulative dashboard figures must not be changed by this full-day analysis until a fresh five-gate cumulative refresh passes.

## Evidence boundary
The analysis can establish measured HDF pressure/infrasound timing, spectral content, recurrence, duration, and changes in raw signal level; and separate EHZ vertical-motion timing/spectral context. It does not by itself establish source identity, intentionality, medical causation, or that observed rattling was caused by one specific channel.

## Continuation instruction
Continue from this cache, not from scratch. Final deliverable should provide the full hourly table from 12:00 AM onward, all measured frequency-band shifts, increases/decreases, notable elevations, and a separate EHZ context column, extending only to the last actual returned minute and marking any unreturned interval N/A.

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
- Representative peak frequency = maximum Welch PSD bin in 1–20 Hz; hourly value to be summarized from minute-level values.
- Increase/decrease = descriptive within-channel change versus the immediately preceding hour, NOT a compliance baseline and NOT a self-benchmark.
- HDF and EHZ are never amplitude-combined.
- HDF raw amplitude is not to be relabeled as Pa/dB without calibration support.
- EHZ raw amplitude is not to be relabeled as calibrated physical motion units without calibration support.

## Verified current-edge facts before full completion
- Repository current-status snapshot generated 2026-08-17 11:25:22 PM EDT reported:
  - HDF: 100% coverage in its current 20-minute status window; latest sample 10:50:23 PM EDT.
  - EHZ: 100% coverage in its current 20-minute status window; latest sample 10:50:22 PM EDT.
- The user-provided daily MiniSEED files materially improve coverage versus sparse status snapshots.
- Direct raw-file reconstruction passed five internal sanity checks before interpretation.
- IMPORTANT: the uploaded daily MiniSEED set contained complete analyzable waveform coverage only to approximately 10:41 PM EDT for the requested Aug. 17 Detroit-day reconstruction. Therefore 10:42 PM–11:30 PM must remain N/A unless public FDSN supplies that interval.

## Five-check framework already applied to raw reconstruction
1. Time bounds / record chronology / unique-minute integrity.
2. MiniSEED decode / decompression integrity including stored record-end sample consistency.
3. Frequency classification restricted to defined 1–20 Hz bands and complete minutes only.
4. Hourly minute totals reconcile to channel totals; no duplicate minute counting.
5. HDF/EHZ channel separation and returned-data edge verified; no unsupported interpolation beyond actual samples.

Status at cache time: PASS on the raw-file reconstruction checks. Final hour-by-hour numerical table still requires completion/inspection of the computed results and direct FDSN gap extension where available.

## Existing dashboard state that must not be overwritten by inference
- Last five-gate cumulative HDF 4–8 Hz spectral totals remain verified through the 8:37 AM EDT complete analyzed minute on Aug. 17, 2026:
  - 57,210 4–8 Hz-dominant minutes
  - 953.50 Hours
  - 36.83% of analyzed HDF time
  - 612 Events >=15 min / 535.18 Hours
  - 325 Events >=30 min / 436.88 Hours
  - 160 Events >=60 min / 321.88 Hours
  - 75 conservative nighttime ordinance-subset Events
- These cumulative figures must not be changed by the full-day analysis until a fresh five-gate cumulative refresh passes.

## Evidence boundary
The analysis can establish measured HDF pressure/infrasound timing, spectral content, recurrence, duration, and changes in raw signal level; and separate EHZ vertical-motion timing/spectral context. It does not by itself establish source identity, intentionality, medical causation, or that observed rattling was caused by one specific channel.

## Next computation state
Continue from this cache, not from scratch. Final deliverable should provide an hourly table from 12:00 AM onward, all measured frequency-band shifts, increases/decreases, notable elevations, and a separate EHZ correlation/context column, stopping at the last actual returned minute and marking any unreturned interval N/A.

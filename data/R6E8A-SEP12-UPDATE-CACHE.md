# R6E8A - September 12, 2026 update recovery checkpoint

Checkpoint: R6E8A-SEP12-CONTINUITY. This records technical update state only, with no personal location or presence information.

## Resume the existing calculation; do not restart
- Repository: markroneil360/ongoing-unit-2709; branch: main.
- Calculation run: 34718056613.
- Calculation job: 103618724305.
- Trigger commit: 457aaf5863255484874d2eac6b1888ca24f33b43.
- Last observed state: calculation and five validation gates in progress; candidate commit pending.
- In-flight waveform buffers held by the remote runner have not yet been returned or independently cached. Do not claim those bytes are preserved here.

## Last verified cumulative checkpoint
- Complete HDF minute: September 10, 2026, 12:15 PM Eastern.
- Candidate file: data/r6e8a_4_8_10min_full.json.
- Candidate blob SHA: 62022d14da6ec69595452aca6468c7f86b39bbd4.
- Scope begins April 12, 2026, midnight Eastern.
- Analyzed HDF minutes: 189751.
- 4-8 Hz dominant minutes: 74253 = 1237.55 hours = 39.13% of analyzed HDF time.
- Runs lasting at least 10 minutes: 1466; 50049 minutes / 834.15 hours.
- Runs lasting at least 30 minutes: 390; 34595 minutes / 576.58 hours.
- Runs lasting at least 60 minutes: 192; 26254 minutes / 437.57 hours.
- Nighttime rule-based subset: 87 events. This is not a determination of legal violations.
- Longest continuous 4-8 Hz dominant run: 976 minutes / 16 hours 16 minutes.

## Latest separately verified acquisition checkpoint
- Status file: data/current-status.json.
- Status blob SHA: f7568e4e4033f091c32f2efce1faeef4ae60ba24.
- Both HDF and EHZ samples: September 12, 2026, 4:22:41 PM Eastern.
- Each channel: 99.999% acquisition coverage in its checked 20-minute window; station/channel identity verified; 100 Hz sample rate.
- This acquisition check does not advance the cumulative spectral calculation cutoff.

## Outstanding publication work
1. Retrieve the completed output of the existing run and preserve its logs and candidate hash.
2. Verify all five candidate gates and independently reconcile totals, durations, nested thresholds, scope and timestamps.
3. Verify or repair the calculation-to-publication and publication-to-Pages workflow handoffs. Workflow-generated pushes alone do not trigger downstream push workflows when using GITHUB_TOKEN.
4. Run all five publication-integrity checks, then verify the actual served dashboard matches the committed candidate.
5. Replace this checkpoint with the completed verified state; retain the old checkpoint in Git history.

## Locked boundaries
Preserve the approved visual design and DPD header. Keep HDF pressure/infrasound separate from EHZ seismic/vertical motion. Exclude missing or incomplete time rather than treating it as zero, quiet, compliant, or below benchmark. Do not extrapolate totals. Do not publish personal timing, travel, presence or absence. Do not infer source, intent or medical causation from environmental frequency-band dominance.

*Account for up to 30 minutes of lag.*

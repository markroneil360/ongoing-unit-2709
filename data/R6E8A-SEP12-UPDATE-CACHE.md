# R6E8A - September 12, 2026 update recovery checkpoint

Checkpoint: R6E8A-SEP12-CONTINUITY. Technical update state only; no personal location, presence, absence, or travel information.

## Completed calculation - do not restart
- Repository: markroneil360/ongoing-unit-2709; branch: main.
- Calculation run 34718056613 / job 103618724305 completed successfully.
- All five calculation gates passed; result committed after validation.
- Candidate generated September 12, 2026 at 5:09:53 PM Eastern.
- Candidate: data/r6e8a_4_8_10min_full.json.
- Candidate blob SHA: e541e8f5b650b01dbcef537b6feb7f90d944932b.
- Scope starts April 12, 2026 at midnight Eastern.
- Latest complete HDF minute: September 12, 2026, 4:15 PM Eastern.
- Latest returned HDF sample in that calculation: September 12, 2026, 4:16:01.233 PM Eastern.
- Full raw waveform bytes are not stored in this checkpoint; do not claim they are. The committed candidate, source URLs, calculation logs, and retained historical-base provenance are the resume anchors.

## Verified cumulative figures
- Analyzed HDF minutes: 193037.
- 4-8 Hz dominant minutes: 76916 = 1281.93 hours = 39.85% of analyzed HDF time.
- Runs >=10 minutes: 1494; 52667 minutes / 877.78 hours.
- Runs >=15 minutes: 768; 44370 minutes / 739.50 hours.
- Runs >=30 minutes: 407; 37028 minutes / 617.13 hours.
- Runs >=60 minutes: 203; 28429 minutes / 473.82 hours.
- Shorter-than-10-minute 4-8 activity: 24249 minutes / 404.15 hours.
- Nighttime rule-based screening subset: 91 events; not a determination of legal violations.
- Longest continuous 4-8 Hz dominant run: 976 minutes / 16 hours 16 minutes.
- Duration tiers overlap and must not be added together.
- Snapshot differences can include backfilled earlier acquisition; do not present aggregate subtraction as an exact intervening-window measurement.

## Five additional independent consistency checks - all passed
These are checks of retrieved aggregates and metadata, not a second full raw-waveform download.
1. Scope/count bounds: 148544 source rows minus 89 pre-scope rows = 148455 base minutes; observed counts do not exceed elapsed time.
2. Historical base plus tail: 148455 + 44582 = 193037 analyzed minutes; 55159 + 21757 = 76916 dominant minutes; all band counts and threshold counts/durations reconcile.
3. Units/percentage/partition: 52667 + 24249 = 76916 minutes; hours and 39.85% independently recomputed.
4. Nested event durations/counts and nighttime subset bounds checked.
5. Complete-minute alignment, timestamp ordering, requested versus returned edge, and Eastern conversion checked.

## Publication and acquisition status
- Publication run 34719568917 / job 103622809044 completed successfully, including all five publication-integrity checks before the dashboard commit.
- Publication handoff repair commit: 5159893a624565dd7b4107d617902365ee855c0e.
- Both separate HDF and EHZ channels were verified through September 12, 2026, 4:48:48 PM Eastern, with 100.0% acquisition coverage in each checked 20-minute window and 100 Hz sample rate.
- Current-status blob SHA: b2de33ea1e3d9e87315e1f83bcaf89f01f925ae5.
- Channel acquisition status does not advance the cumulative spectral cutoff.

## Public-delivery verification resume point
- Successful calculation now triggers the checked publisher; successful publication triggers Pages. Both handoffs require main-branch, same-repository successful upstream runs.
- Pages now verifies direct HTTPS byte equality for index.html, the spectral candidate, and current-status.json against the files actually deployed.
- Public-delivery verification workflow commit: e522969aca5b724d15486061bddd943f12146f86.
- Receipt artifact name: r6e8a-public-delivery-verification; file public-delivery-verification.json. It records expected/served SHA-256 hashes, actual checked-out commit, verified Eastern time, candidate cutoff and channel cutoffs.
- At this checkpoint, direct served-file verification is pending. Do not report final completion solely from calculation success, publication success, or an old Pages deployment.
- Existing R6E8A Completion Notice automation is configured to verify completion and notify. Do not create a duplicate.

## Locked boundaries
Preserve the approved visual design and DPD header. HDF pressure/infrasound and EHZ seismic/vertical motion remain separate. Missing or incomplete time is excluded, never scored as zero, quiet, compliant, or below benchmark. No extrapolated totals. Band dominance is an environmental signal metric, not a calibrated personal medical dose, a health threshold, legal violation, or proof of source or intent.

Previous September 10 checkpoint (1237.55 hours through 12:15 PM Eastern) remains preserved in Git history.

*Account for up to 30 minutes of lag.*

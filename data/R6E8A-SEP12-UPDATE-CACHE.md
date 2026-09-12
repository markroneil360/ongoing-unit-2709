# R6E8A - September 12, 2026 completed update checkpoint

Checkpoint: R6E8A-SEP12-CONTINUITY.
Status: COMPLETE - calculation, checked publication, deployment, and direct public-file verification succeeded.
Public files verified September 12, 2026 at 5:20:24 PM Eastern.
Technical record only; no personal location, presence, absence, or travel information.

## Resume anchors - do not repeat the completed calculation
- Repository: markroneil360/ongoing-unit-2709; branch: main.
- Calculation run: 34718056613; job: 103618724305; success.
- Publication run: 34719568917; job: 103622809044; success.
- Direct-public-verification deployment run: 34719651927; job: 103623022574; success.
- Verified deployment commit: e522969aca5b724d15486061bddd943f12146f86.
- Candidate file: data/r6e8a_4_8_10min_full.json.
- Candidate blob SHA: e541e8f5b650b01dbcef537b6feb7f90d944932b.
- Separate-channel status blob SHA: b2de33ea1e3d9e87315e1f83bcaf89f01f925ae5.
- Receipt artifact: r6e8a-public-delivery-verification; artifact ID 10305763815; file public-delivery-verification.json.
- Full raw waveform bytes are not stored in this checkpoint. Resume from the committed candidate, source URLs, calculation logs, retained historical-base provenance, and receipt hashes below. Do not claim that temporary runner waveform buffers are archived here.

## Exact analysis and channel cutoffs
- Historical analysis begins April 12, 2026 at midnight Eastern.
- Candidate generated September 12, 2026 at 5:09:53 PM Eastern.
- Complete analyzed HDF minute: September 12, 2026, 4:15 PM Eastern.
- Returned HDF sample for that spectral calculation: September 12, 2026, 4:16:01.233 PM Eastern.
- Separately verified HDF and EHZ acquisition: September 12, 2026, 4:48:48 PM Eastern for each channel.
- Each acquisition window: 20 minutes; 100.0% coverage; one continuous segment; 100 Hz; station/channel identity verified.
- Channel acquisition status does not advance the cumulative spectral cutoff.

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
- Aggregate differences can include backfilled earlier acquisition; do not present snapshot subtraction as an exact intervening-window measurement.

## Five calculation gates - all passed before publication
1. Apr 12 scope and retained preview totals.
2. Corrected legacy-threshold checkpoint.
3. Six-minute checkpoint boundary sequence.
4. Unique complete clock-minute and defined-band integrity.
5. >=10-minute reconciliation, nested event counts, and retained nighttime-screening anchor.

## Five additional independent consistency checks - all passed
These checked retrieved aggregates and metadata, not a second full raw-waveform download.
1. Scope/count bounds: 148544 source rows minus 89 pre-scope rows = 148455 base minutes; valid counts within elapsed-time bounds.
2. Historical base plus tail: 148455 + 44582 = 193037 analyzed minutes; 55159 + 21757 = 76916 dominant minutes; band counts and threshold statistics reconcile.
3. Units, percentage and partition: 52667 + 24249 = 76916 minutes; hours and 39.85% independently recomputed.
4. Nested durations/counts and nighttime-subset bounds.
5. Complete-minute alignment, timestamp ordering, requested/returned edge, and Eastern conversion.

## Five publication-integrity checks - all passed before dashboard commit
1. Candidate identity, Apr 12 scope, and returned-data edge.
2. Separate, covered HDF and EHZ acquisition windows.
3. Arithmetic, nested thresholds, hours and percentage.
4. Reconciled dashboard values, dates and cutoffs.
5. Threshold wording, missing-data treatment, channel separation and freshness guard.

## Direct public delivery - all three exact byte comparisons passed
Verified at 2026-09-12T17:20:24.979373-04:00 by HTTPS GET, each returning HTTP 200. Each served SHA-256 equals the corresponding deployed file SHA-256.
- index.html: 2ebbdac8ce418e115410e42ff5d79de122085691c5b6dadb3ad4b23f7f11f740
- data/r6e8a_4_8_10min_full.json: a409ff36f6d1b9870e5bfb5e67a147eb8bc0c0da91e371a912deff71829ca321
- data/current-status.json: ed0338c2b29d452c60eb3d6b8e43178dfbac43a992eead4d5ddb012317b208a6
- Receipt flags: candidate_all_five_checks_pass=true; all_public_files_match=true.

## Operational repairs and scope
- Successful current-tail calculation now triggers the checked publisher; successful publication triggers Pages. Upstream-triggered jobs require a successful main-branch run from the same repository.
- Pages checks direct public byte equality and preserves a verification receipt.
- The approved dashboard design, DPD header, analysis method and existing download buttons were retained.
- This completion covers the dashboard and its spectral/status data files. The two PDF reports were not regenerated by this run.
- The existing R6E8A Completion Notice automation remains the notification checkpoint; do not create duplicate watches or restart the completed run.

## Evidence boundaries
HDF pressure/infrasound and EHZ seismic/vertical motion remain separate. Missing or incomplete time is excluded, never scored as zero, quiet, compliant, or below benchmark. No extrapolated totals. Band dominance is an environmental signal metric, not a calibrated personal medical dose, health threshold, established legal violation, or proof of source or intent.

Previous September 10 checkpoint (1237.55 hours through 12:15 PM Eastern) and intermediate September 12 checkpoints remain preserved in Git history.

*Account for up to 30 minutes of lag.*

# Unit 2709 Infrasound & Seismic Pressure Data

A static, evidence-first dashboard for public Raspberry Shake station **AM.R6E8A.00** (Detroit, MI).

- **Primary channel — HDF:** very-low-frequency air-pressure changes, in pascals (Pa). Infrasound (below 20 Hz) is largely below ordinary human audibility; a calibrated pressure sensor is used to quantify it.
- **Secondary channel — EHZ:** vertical ground-motion velocity, in µm/s, shown only as separate context. HDF and EHZ units are never mixed.

All values are **response-corrected, per-minute RMS** with no interpolation. Each channel is compared only against its own deterministic peer baseline drawn from other public Raspberry Shake stations (same channel, units, frequency band, and day window). The band-limited Pa RMS metric is **not** a dB SPL exposure measurement and cannot by itself be used to establish harm.

## Coverage

The dashboard reports the **documented archived window** (the date range shown in the header). It is not a real-time feed: the fixed daily 24-hour report uses a **07:00 AM America/Detroit** cutoff and is generated after the Raspberry Shake FDSN archive delay. The header label reflects the actual latest archived data date and does not claim coverage up to the present. Days without retrievable data are recorded as gaps rather than interpolated.

## Data & automation

- `data/` — derived public aggregates (per-minute RMS caches and embeds, peer baselines, events, snapshot metadata). No raw MiniSEED is stored or redistributed.
- `assets/` — independently generated composite snapshot images.
- `tools/` — Python/Node utilities that build the derived data and run QA.
- `.github/workflows/pages.yml` — deploys the static root to GitHub Pages via GitHub Actions.
- `.github/workflows/daily-refresh.yml` — regenerates derived data once per day at the fixed 07:00 ET cutoff (DST-safe), committing only derived assets.

## Attribution

Data powered by **Raspberry Shake, S.A.**, a citizen-science project. Please visit [raspberryshake.org](https://raspberryshake.org) and join the Citizen Science Community. DOI: <https://doi.org/10.7914/SN/AM>.

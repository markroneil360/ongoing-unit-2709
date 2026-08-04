# Unit 2709 R6E8A Instrument Dashboard (Ongoing)

Public single-page dashboard for Raspberry Shake station **AM.R6E8A** in Detroit.

- **Project span:** April 12, 2026 - Ongoing
- **Primary channel:** HDF pressure / infrasound
- **Secondary channel:** EHZ vertical motion
- **Public page:** <https://markroneil360.github.io/ongoing-unit-2709/>

HDF and EHZ are always processed and reported independently. Missing samples remain unavailable and are never interpolated or set to zero.

The public comparison rule is strict: R6E8A is never benchmarked against its own history and is never benchmarked against another Raspberry Shake station. HDF pressure is the lead record; EHZ remains separate supporting motion data.

## Live display and derived status

The homepage combines two different official-source paths:

1. Raspberry Shake's supported DataView embeds display the current HDF and EHZ waveforms.
2. `.github/workflows/update-daily-highest.yml` retrieves no more than 24 hours per FDSN request, runs `scripts/update_daily_highest.py`, and publishes a compact dual-channel status record at `data/daily-highest.json`.

Raw MiniSEED is streamed for processing and is not stored or redistributed in this repository.

The live event record includes a clearly labeled nominal HDF pressure estimate using the manufacturer's 56,000 counts/Pa sensitivity (estimated +/-10%). That estimate is unweighted and response-uncorrected. It is a physical-unit aid, not dB(G), an outside-guide exceedance, or a safety grade.

## External references

The dashboard names the approved comparison framework:

- ISO 7196 for G-weighted infrasound measurement
- ANSI/ASA S12.2 and ASHRAE RC/NC for room-noise criteria
- Defra NANR45 for calibrated 1/3-octave low-frequency assessment
- WHO night-noise guidance and ISO 1996 for the acoustic metrics they specify

No standard is treated as interchangeable with another. Raw instrument counts are not labeled as dB(A), dB(C), dB(G), NC or RC. When calibration, frequency weighting, banding, averaging or coverage is insufficient, the result is shown as **N/A** and no monitoring tier is assigned.

ISO 7196 defines a G-weighting method but does not set a danger limit. The dashboard therefore does not invent a percentage or tier from ISO 7196 alone. ASHRAE, NANR45 and WHO values are displayed only in the units and context specified by those publications.

The four tiers describe duration relative to a valid named external reference:

- Tier 1: within named reference
- Tier 2: intermittent verified exceedance, each interval under 30 minutes
- Tier 3: prolonged verified exceedance, 30-119 minutes
- Tier 4: extended verified exceedance, 120 minutes or longer

These are monitoring-priority categories, not medical, safety, causation or source-identification categories.

The homepage also accounts for every date from April 12 through the current record. It distinguishes source-backed dates, explicitly marked no-data dates, and dates whose source was not retained in the reproducible project bundle. Source availability is not itself a noise tier.

## Reports

`scripts/generate_reports.py` creates the two linked reports from derived JSON:

- `downloads/R6E8A-24-hour-report.pdf`
- `downloads/R6E8A-7-day-trailing-report.pdf`

Each report keeps HDF and EHZ separate and includes the source-method limitations.

## Verification

Data are independently verifiable through [Raspberry Shake DataView](https://dataview.raspberryshake.org/) and the [Raspberry Shake FDSN service](https://data.raspberryshake.org/fdsnws/). Data powered by Raspberry Shake, S.A.; DOI: <https://doi.org/10.7914/SN/AM>.

*This Data may lag.*

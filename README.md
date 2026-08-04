# R6E8A Unit 2709 dashboard

Static, direct-upload dashboard for the R6E8A record from April 12, 2026 onward.

Public page: <https://markroneil360.github.io/ongoing-unit-2709/>

## Locked public rules

- HDF pressure/infrasound leads; EHZ vertical motion remains separate.
- Public measurement results are percentages.
- R6E8A is indexed only against four named outside-reference families: ISO 7196; ANSI/ASA with ASHRAE RC/NC; Defra NANR45; and WHO Night Noise with ISO 1996.
- The page never uses a within-station or another-station comparison.
- Public gaps are omitted instead of converted to zero.
- Four monitoring tiers remain visible and the current uploaded record receives a recommendation.
- Source attribution appears in the small page footer.
- The two PDF reports repeat the same percentage-only findings.

## Current direct-upload result

The current HDF and EHZ files are each internally continuous. HDF supplies the four acoustic indices; EHZ supplies separate vertical-motion context. The displayed rounded indices are ISO scope share 90%, ANSI/ASHRAE measured-band index 172%, Defra measured-band index 46%, and WHO measured-band contribution 12%. The sensitivity-tolerant recommendation is Tier 2.

## Update control

The public page and reports are pre-rendered. The GitHub workflow is manual verification only: it has no schedule, no feed pull, and no repository write permission. Direct-upload processing can be added later without changing the static fail-safe.

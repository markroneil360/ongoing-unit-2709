# R6E8A dashboard update cache

Before every publication of this dashboard, run and record five independent sanity checks:

1. Confirm the station, HDF and EHZ identities, source hashes, acquisition coverage, and latest available sample timestamps.
2. Reconcile new complete HDF minutes with the existing cache; exclude gaps and check overlap for conflicting classifications.
3. Recompute cumulative 4–8 Hz minutes, hours, event counts, and date boundaries from the verified minute data.
4. Compare every displayed total, data cutoff, and both downloadable PDF reports with the candidate and report manifest.
5. Verify publication integrity on the public page, including time zone, update time versus measurement time, missing-data disclosure, links, and served file hashes.

Publish only when all five pass. Record the checks with the update. Never label the dashboard's publication date as a measurement date. HDF pressure/infrasound and EHZ seismic data remain separate. A missing interval is unobserved and never scored as quiet or zero.

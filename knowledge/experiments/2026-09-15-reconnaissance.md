# Reconnaissance execution record — 2026-09-15

Environment: provided Linux container, repository branch `work`, Python standard
library and current Git. No packages were installed; no upstream scripts, services,
models, checkpoints, datasets, or paid APIs were used.

## Source-only acquisition

Command: `python fetch_references.py --groups core --clone`
Exit: 1
Result: all six GitHub fetches failed with `CONNECT tunnel failed, response 403`.
The downloader left initialized partial directories for inspection as designed.
No commit was fetched and no lock record was produced.

## Alternate read-only retrieval checks

- Repository web retrieval returned HTTP 401 before results.
- `curl -I -L --max-time 10` to a GitHub raw file, GitHub API commit endpoint,
  and arXiv WISERouter HTML each failed at CONNECT with HTTP 403.

These checks downloaded no source or paper content. The study notes therefore mark
all upstream implementation details as NOT INSPECTED and do not claim reproduction.

# Blocked items

## B01 — audited blueprint missing (blocking)

`IcebergRouter_Implementation_Blueprint_v2_Audited.docx` was not found under
`/workspace`. Without it, conflicts between the authoritative design and the
working synthesis cannot be audited.

Resolution: provide the original file; extract/read it without executing embedded
content; record conflicts rather than silently reconciling them.

## B02 — all six core source fetches blocked (blocking)

Command: `python fetch_references.py --groups core --clone`
Environment: provided Linux container, 2026-09-15
Result: each Git HTTPS fetch failed at the proxy CONNECT step with HTTP 403, before
`FETCH_HEAD` was resolved. Partial initialized directories remain under ignored
`references/repos/`; no `vendor-lock.json` repository records were created.

Impact: exact upstream SHAs, code symbols/lines, notices, retries, budget semantics,
feedback assumptions, and reuse boundaries cannot be reported as inspected.

Resolution: run the reviewed source-only downloader in a network environment that
permits GitHub HTTPS, or provide unmodified source-only archives plus independently
verifiable commit identities and notices. Review/remove partial directories before
retrying because the downloader intentionally refuses unmanaged destinations.

## B03 — WISERouter paper retrieval blocked (blocking)

The configured web tool returned HTTP 401 and direct HTTPS access to arXiv returned
proxy CONNECT 403. No paper content was received.

Resolution: provide arXiv v1 text/PDF (`2607.23765v1`) or allow read-only arXiv
access. Verify the document identifier and record page/section evidence.

## B04 — upstream licensing and artifact terms unresolved (blocking for reuse)

LLMRouterBench and R2-Router code licenses are unconfirmed in the workspace;
LiteLLM has reported mixed boundaries; reported Apache/MIT labels for other repos
have not been verified at pinned commits. Dataset, checkpoint, and bundled
third-party terms remain separate unknowns.

## B05 — R2-Router provenance discrepancy unresolved

The workspace register reports that a reviewed README clone example pointed to
`jqxue1999/router` and a different branch, while the manifest names
`UCF-ML-Research/R2-Router`. Preserve both facts until pinned source/history or an
author statement resolves the relationship.

## B06 — hidden retries and unsupported guarantees unknown

No upstream call chain was available. Retry/fallback defaults, usage on streaming
cancellation, missing usage, concurrent budget state, duplicate settlement, and
provider enforcement are unverified for every baseline/gateway. No upstream
mechanism currently has evidence of satisfying Iceberg's strict shared ceiling.

## Non-blocking local evidence

The study downloader's 10 local tests pass. They use temporary local Git fixtures;
they are not remote-fetch, upstream-build, router-quality, or paper-reproduction
evidence.

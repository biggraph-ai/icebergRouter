# IcebergRouter: coding-agent study kit
Prepared 15 September 2026. This is a reference-acquisition and onboarding kit, not an Iceberg implementation.

## Recommended decision
Prepare six core source repositories and the WISERouter paper. Require source-linked notes and small, isolated baseline checks before coding Iceberg's new policy. Do not put all repositories into one dependency environment or one giant agent prompt.

## Use
Requires Python 3.10+ and a current Git installation. The downloader itself has no third-party Python dependencies.
From this extracted directory:

```sh
python fetch_references.py --groups core
python fetch_references.py --groups core --clone
```

The first command is a dry run. The second fetches selected source/text files and records exact commits in `vendor-lock.json`.
On Windows, `py -3` may be used instead of `python`.

Additional material is opt-in:

```sh
python fetch_references.py --groups docs --clone
python fetch_references.py --groups architecture --clone
python fetch_references.py --groups java,typescript --clone
```

Use `--ids routellm` to select one repository. Use `--root PATH` and `--lock PATH` for a different location. Never run concurrent downloader instances against the same destination/lock file.

## What the downloader does and does not do
It records a fetched commit on first use and verifies it on later use. It does not pull newer commits automatically. It refuses to overwrite changed/unmanaged reference directories. It uses shallow, blob-filtered fetches and sparse source checkouts, skips symlinks, skips LFS downloads, and excludes recognized data/checkpoint directories and binary formats. A server may ignore the blob-filter request; this is not a promise about network bytes.

It does NOT install packages, execute upstream scripts, run agents, start services, fetch external datasets, or call model APIs. These are source-reading copies, NOT build-complete worktrees. A later reproduction needs a separate, reviewed full checkout at the same SHA and its own environment. Treat checkpoints and serialized objects as untrusted until reviewed; do not load a pickle merely because it accompanies a paper.

The script ignores inherited Git hooks and global/system Git configuration for reference fetches. Corporate proxy/credential setups may therefore require a manual equivalent. Do not disable certificate validation. A SHA provides reproducibility, not proof that the upstream code is safe or author-authenticated.

`vendor-lock.json` records notice-file hashes but does not decide licensing. Read code, dataset, checkpoint and embedded third-party terms separately. No license was conclusively verified for every public repository in this kit.

## Agent entry point
Read `AGENTS.md`, then `STUDY_ORDER.md`. Use the first prompt in `HANDOFF_PROMPTS.md`. The deliverables belong in `knowledge/`; new implementation belongs in a separate folder not referring anything existing .

The audited user blueprint is `IcebergRouter_Implementation_Blueprint_v2_Audited.docx`. Keep that original nearby; it is not redistributed or rewritten here. `requirements/PLAN_CONSTRAINTS.md` is a working synthesis of the decisions in this conversation, not a verbatim copy of that document.

## Product implementation workspace

Iceberg-owned code lives under `src/iceberg_router/`; its design notes live under
`iceberg/`. Increments 0–8 establish boundaries, portable contracts, a single-host
budget authority, bounded option graphs, guarded execution and audit, offline
control policies, an injected single-attempt adapter boundary, end-to-end
orchestration, and exact offline evaluation accounting. There is still no real
provider integration, upstream reproduction, or Iceberg acquisition policy. See
`iceberg/ARCHITECTURE.md` before adding product code. Reference directories must
remain unchanged and must not be imported as runtime packages.

## Validation
Run `python -m unittest discover -s tests -v` for the downloader's local tests. See `TEST_STATUS.md` for what was actually tested. No upstream build or paper-result reproduction is claimed.

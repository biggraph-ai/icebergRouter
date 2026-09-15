# Assumption register

| ID | Statement | Class | Consequence / validation |
|---|---|---|---|
| A01 | The audited blueprint is authoritative. | User requirement | File is absent; obtain and compare before design approval. |
| A02 | The six manifest URLs are canonical. | Unverified assumption | Confirm repository ownership/provenance and pin exact SHAs. |
| A03 | The named upstream paths still exist on their pinned commits. | Unverified assumption | Verify with `git ls-tree`; do not cite mutable branch URLs. |
| A04 | RouteLLM maps a score and threshold to weak/strong choice. | Workspace description | Inspect controller/router/calibration call chain and equality case. |
| A05 | Cascade Routing makes sequential stop/call/select decisions. | Workspace description | Inspect exact state, missing responses, exhaustion, and selection. |
| A06 | R2-Router jointly selects model and output budget. | Workspace description | Inspect representation and distinguish estimate, cap, and bill. |
| A07 | LLMRouter exposes reusable router interfaces. | Workspace description | Inspect one minimal interface and configuration/evaluation path. |
| A08 | LiteLLM normalizes usage/pricing/retries. | Workspace description | Trace every attempt, failure, stream, and billing path. |
| A09 | WISERouter optimizes expected cost using contextual allocation. | Workspace description of paper | Verify sections 3–4, algorithms, assumptions, and appendices. |
| A10 | Repository-page license labels cover relevant code/artifacts. | Unverified assumption | Read pinned notices plus dataset/checkpoint/bundled terms. |
| A11 | A provider output-token parameter yields an invoice upper bound. | Unsafe assumption | Require enforceability and coverage of all charge components. |
| A12 | Timeout or cancellation costs zero. | Unsafe assumption | Retain authorized liability pending authoritative settlement. |
| A13 | Missing user feedback means acceptance. | Prohibited assumption | Represent accept/reject/abstain/missing explicitly. |
| A14 | Router score or cosine similarity is calibrated success probability. | Prohibited assumption | Calibrate and validate separately or label as score only. |
| A15 | Independent benchmark answers form a conditional workflow trace. | Prohibited assumption | Execute real bounded branches or label synthetic simulation. |
| A16 | Atomic JSON replacement gives multi-process ledger safety. | False for proposed runtime | Use transactional/locked persistence with deployment guarantees. |

## Evidence vocabulary

- **Documented:** stated by an identified paper/upstream document at a fixed version.
- **Inspected:** traced in code at an exact commit, file, symbol, and line range.
- **Tested:** exercised by a recorded command with environment, artifacts, output,
  and limitations. A mock test supports only the mocked contract.
- **Workspace description:** stated by this study kit but not independently verified
  against upstream material during this pass.
- **Inference:** analyst conclusion from cited evidence, explicitly labeled.
- **Unknown:** no adequate evidence; never silently mapped to zero, success, or false.

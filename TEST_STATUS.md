# Validation record

Date: 15 September 2026.

Command executed: `python -m unittest discover -s tests -v`

Result: 10 tests passed. Tests include real operations against temporary local Git repositories: sparse source checkout, commit pinning, no automatic update, fetching a locked commit into a new destination, refusing unmanaged/modified directories, plus manifest validation, exclusions, exact path escaping, atomic JSON writes and dry-run behavior.

These are downloader tests, not Iceberg routing tests. GitHub pages and selected source-directory listings were checked through web retrieval. Direct GitHub downloads could not be executed from this container's network, so the complete remote fetch path is not end-to-end validated here. Upstream packages were not installed, checkpoint files were not loaded, upstream tests were not run, and no paper results were reproduced.

No claim of supported behavior for every provider, runtime or operating system is made. The downloader uses Python's standard library and Git; its local tests ran in the provided Linux environment. Windows usage is documented but not independently exercised here.

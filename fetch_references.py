#!/usr/bin/env python3
"""Prepare pinned, source-only reference checkouts. Dry-run unless --clone is set.

Python 3.10+ and Git are the only requirements. This program never installs
packages, downloads external datasets, starts services, or executes repo scripts.
First fetch records a commit; later runs refuse changes rather than updating it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from typing import Any

BASE = Path(__file__).resolve().parent
SOURCE_EXTENSIONS = {
    '.py', '.pyi', '.java', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs',
    '.go', '.rs', '.md', '.rst', '.txt', '.json', '.yaml', '.yml', '.toml',
    '.xml', '.gradle', '.kts', '.sql', '.proto', '.sh', '.mod', '.sum',
}
EXCLUDED_PARTS = {
    '.git', 'node_modules', '.venv', 'venv', '__pycache__', 'checkpoints',
    'weights', 'datasets', 'data', 'artifacts', 'assets', 'results',
    'dist', 'build', 'target', '.agents', '.claude', '.codex', '.cursor',
}
EXCLUDED_INSTRUCTIONS = {'agents.md', 'claude.md', 'gemini.md'}
METADATA = {
    'readme', 'readme.md', 'readme.rst', 'pyproject.toml', 'requirements.txt',
    'package.json', 'pom.xml', 'build.gradle', 'build.gradle.kts',
    'go.mod', 'go.sum', 'cargo.toml', 'data_release.md',
}


def validate_entry(entry: dict[str, Any]) -> None:
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', entry.get('id', '')):
        raise ValueError('Repository id must be a simple lowercase folder name.')
    if not re.fullmatch(r'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git', entry.get('url', '')):
        raise ValueError('Only explicit HTTPS github.com repository URLs are accepted.')
    if entry.get('commit') and not re.fullmatch(r'[0-9a-fA-F]{40}', entry['commit']):
        raise ValueError('An optional manifest commit must be a full 40-character SHA.')
    for root in entry.get('study_roots', []):
        p = PurePosixPath(root)
        if not root or p.is_absolute() or '..' in p.parts or '\n' in root or '\\' in root:
            raise ValueError(f'Unsafe study root: {root!r}')


def is_notice(path: str) -> bool:
    name = PurePosixPath(path).name.lower()
    return name.startswith(('license', 'licence', 'copying', 'notice', 'ip_notice'))


def select_paths(tree: str, roots: list[str]) -> list[str]:
    """Select tracked regular text/source files, not symlinks, submodules or data."""
    selected = []
    for line in tree.splitlines():
        if '\t' not in line:
            continue
        meta, path = line.split('\t', 1)
        fields = meta.split()
        if len(fields) != 3 or fields[0] not in {'100644', '100755'} or fields[1] != 'blob':
            continue
        # With core.quotepath=false unusual Git-quoted paths still need decoding;
        # skip them for this source-reading kit rather than guessing.
        if path.startswith('"') or '\n' in path or '\r' in path:
            continue
        pp = PurePosixPath(path)
        parts = [p.lower() for p in pp.parts]
        if any(p in EXCLUDED_PARTS for p in parts) or pp.name.lower() in EXCLUDED_INSTRUCTIONS:
            continue
        under_root = any(path == r or path.startswith(r.rstrip('/') + '/') for r in roots)
        root_metadata = len(pp.parts) == 1 and pp.name.lower() in METADATA
        if is_notice(path) or root_metadata or (under_root and pp.suffix.lower() in SOURCE_EXTENSIONS):
            selected.append(path)
    return sorted(set(selected))


def sparse_pattern(path: str) -> str:
    # Exact gitignore-style path; escape pattern metacharacters in tracked names.
    escaped = ''.join('\\' + ch if ch in '\\*?[]!' else ch for ch in path)
    return '/' + escaped


def git(args: list[str], *, cwd: Path | None = None, stdin: str | None = None,
        allow_local_for_tests: bool = False) -> str:
    env = os.environ.copy()
    env.update({
        'GIT_TERMINAL_PROMPT': '0', 'GIT_LFS_SKIP_SMUDGE': '1',
        'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull,
    })
    # Reference fetches intentionally ignore inherited Git hooks/filters. This
    # may require manual setup in a corporate proxy environment; never weaken
    # certificate validation to work around a failed fetch.
    with tempfile.TemporaryDirectory(prefix='iceberg-empty-hooks-') as hooks:
        cmd = ['git', '-c', f'core.hooksPath={hooks}', '-c', 'core.quotePath=false',
               '-c', 'core.autocrlf=false', '-c', 'protocol.ext.allow=never',
               '-c', f'protocol.file.allow={"always" if allow_local_for_tests else "never"}',
               '-c', 'filter.lfs.process=', '-c', 'filter.lfs.smudge=',
               '-c', 'filter.lfs.required=false'] + args
        result = subprocess.run(cmd, cwd=cwd, env=env, input=stdin, text=True,
                                capture_output=True, timeout=240, check=False)
    if result.returncode:
        raise RuntimeError(f'Git failed ({result.returncode}): {" ".join(args)}\n{result.stderr.strip()}')
    return result.stdout.strip()


def atomic_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent,
                                     prefix=path.name + '.', delete=False) as out:
        temporary = Path(out.name)
        json.dump(data, out, indent=2, ensure_ascii=False)
        out.write('\n')
        out.flush()
        os.fsync(out.fileno())
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def prepare(entry: dict[str, Any], root: Path, old: dict[str, Any] | None,
            *, allow_local_for_tests: bool = False) -> dict[str, Any]:
    target = root / entry['id']
    def run(args: list[str], stdin: str | None = None) -> str:
        return git(args, cwd=target, stdin=stdin, allow_local_for_tests=allow_local_for_tests)
    if target.exists():
        if not old:
            raise RuntimeError(f'Refusing to adopt unmanaged directory {target}. Choose an empty destination.')
        if target.is_symlink():
            raise RuntimeError(f'Refusing symlink destination: {target}')
        actual = run(['rev-parse', 'HEAD'])
        origin = run(['remote', 'get-url', 'origin'])
        if actual != old['commit'] or origin != entry['url'] or origin != old['url']:
            raise RuntimeError(f'Pinned reference changed: {target}. No reset or update performed.')
        if run(['status', '--porcelain', '--untracked-files=normal']):
            raise RuntimeError(f'Reference has local changes: {target}. No files overwritten.')
        print(f'VERIFIED {entry["id"]}: {actual}')
        return old
    target.mkdir(parents=True)
    run(['init', '--quiet'])
    run(['remote', 'add', 'origin', entry['url']])
    requested = (old or {}).get('commit') or entry.get('commit') or 'HEAD'
    run(['fetch', '--depth=1', '--filter=blob:none', '--no-tags', 'origin', requested])
    commit = run(['rev-parse', 'FETCH_HEAD'])
    if old and commit != old['commit']:
        raise RuntimeError('Fetch did not resolve to the locked commit.')
    tree = run(['ls-tree', '-r', commit])
    paths = select_paths(tree, entry['study_roots'])
    if not paths:
        raise RuntimeError(f'No source files selected for {entry["id"]}; review manifest paths.')
    run(['sparse-checkout', 'init', '--no-cone'])
    run(['sparse-checkout', 'set', '--no-cone', '--stdin'],
        stdin='\n'.join(sparse_pattern(p) for p in paths) + '\n')
    run(['checkout', '--detach', commit])
    if run(['status', '--porcelain', '--untracked-files=normal']):
        raise RuntimeError('New reference checkout is unexpectedly dirty; review it before use.')
    notices = {p: hashlib.sha256((target / p).read_bytes()).hexdigest()
               for p in paths if is_notice(p) and (target / p).is_file()}
    record = {
        'url': entry['url'], 'commit': commit,
        'fetched_at_utc': datetime.now(timezone.utc).isoformat(),
        'source_path_count': len(paths), 'selected_paths': paths,
        'notice_sha256': notices,
        'license_review_status': 'NOT_REVIEWED',
        'upstream_tests_status': 'NOT_RUN',
        'checkout_scope': 'Selected source/text only; not a build-complete clone',
    }
    print(f'PINNED {entry["id"]}: {commit} ({len(paths)} source/text files)')
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=BASE / 'repo_manifest.json')
    parser.add_argument('--root', type=Path, default=BASE / 'references' / 'repos')
    parser.add_argument('--lock', type=Path, default=BASE / 'vendor-lock.json')
    parser.add_argument('--groups', default='core', help='Comma-separated groups; default core')
    parser.add_argument('--ids', nargs='+', help='Select exact manifest ids instead of groups')
    parser.add_argument('--clone', action='store_true', help='Fetch pinned sparse source checkouts; default is dry-run')
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    entries = manifest['repositories']
    for entry in entries:
        validate_entry(entry)
    known_ids = {r['id'] for r in entries}
    known_groups = {g for r in entries for g in r['groups']}
    groups = set(args.groups.split(','))
    if args.ids:
        if set(args.ids) - known_ids:
            raise ValueError(f'Unknown ids: {sorted(set(args.ids) - known_ids)}')
        chosen = [r for r in entries if r['id'] in args.ids]
    else:
        if groups - known_groups:
            raise ValueError(f'Unknown groups: {sorted(groups - known_groups)}. Available: {sorted(known_groups)}')
        chosen = [r for r in entries if groups.intersection(r['groups'])]
    if not args.clone:
        for entry in chosen:
            print(f'{entry["id"]:22s} {entry["url"]}')
            print('  Start with: ' + ', '.join(entry['read_first']))
        print(f'\nDRY RUN: {len(chosen)} repositories. Add --clone to fetch selected source files.')
        return 0
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    lock_path = args.lock.resolve()
    lock = json.loads(lock_path.read_text(encoding='utf-8')) if lock_path.exists() else {
        'schema_version': 1, 'repositories': {}}
    failures = []
    for entry in chosen:
        try:
            old = lock['repositories'].get(entry['id'])
            lock['repositories'][entry['id']] = prepare(entry, root, old)
            atomic_json(lock_path, lock)
        except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
            failures.append(entry['id'])
            print(f'ERROR {entry["id"]}: {exc}', file=sys.stderr)
            print('Any partial directory is left intact for inspection; no files were deleted.', file=sys.stderr)
    print(f'Lock file: {lock_path}')
    return 1 if failures else 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        raise SystemExit(2)

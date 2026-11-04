#!/usr/bin/env python3
"""Check the public source snapshot and every local Git object for known remnants.

This guard checks known byte hashes, source packaging rules and nested ZIP/PK3
members. It does not independently establish the authorship or license of
unrecognized content. --history includes unreachable objects and reflog-only
objects, so deleting a branch alone cannot make an old stock blob pass.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import struct
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
MAX_GIT_FILE_BYTES = 100 * 1024 * 1024
MAX_ARCHIVE_BYTES = 1024 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 50000
MAX_ARCHIVE_DEPTH = 6
FORBIDDEN_COMMITS = {'1a71577727adbe993e1fa56c7a4e09149fd17b50'}
REQUIRED_NOTICES = ('LICENSE', 'ASSET-LICENSE.md', 'tools/assets/asset-provenance.json')
# These bytes were recorded before the local cleanup/history replacement.
KNOWN_HASHES = {
    '4cc63f1c2a4c04ece2ec3f11c2b941ba90a099528ad3d1ef5c6948778535db36': 'legacy male grunt atlas',
    '7448a9a3f61fcff7b2819b56957ea5ac54c65f316e14df33002a2024aff529d2': 'legacy grunt portrait',
    '36f56c0f9cc11add6d3fbad1cf257bfc595cfca1459d53c9d65d5ab392709a61': 'legacy male player model',
    '8259152d5e9e2cfa7aa98cdc708a64ebafd810cd8a6e069aab7a6a3c8337ecc6': 'legacy male weapon model',
    '909d30f02111ad0a124010cf71420434cd901e44c326bf8fe195e86d831c6e2d': 'legacy crosshair palette image',
    'fbae581b9c5b5121ff2f23ecfd58d61da7d545a2e999381183cebedf95965248': 'legacy crosshair model',
    '241b171cb69bbf0b24108d8f252931f7451f3e2536ff932e3531b9e5de941b97': 'legacy compiled Quake icon artwork',
    'da1d500f816ef80c84823a90a8320736e3767d2588c886e84490dec3ac931e38': 'legacy macOS application bundle',
}
ZIP_MAGIC = (b'PK\x03\x04', b'PK\x05\x06', b'PK\x07\x08')
FS_EXCLUDES = {'.git', 'build', 'release', 'debug', '__pycache__', '.pytest_cache'}


def issue(violations, code, location, detail, **extra):
    violations.append(dict(code=code, location=location, detail=detail, **extra))


def path_policy(name):
    """Check packaging paths, allowing the project's custom player/male audio."""
    normalized = name.replace('\\', '/')
    parts = tuple(part.lower() for part in normalized.split('/') if part)
    filename = parts[-1] if parts else ''
    if '\\' in name or normalized.startswith('/') or '..' in parts:
        return 'unsafe_path', 'Absolute paths, parent traversal and backslashes are forbidden.'
    if '.git' in parts or any('private-backup' in part for part in parts) or 'asset-backups' in parts:
        return 'private_backup', 'Private backups and Git repositories must remain outside the public source tree.'
    if filename.endswith(('.bundle', '.blend1', '.blend2', '.pyc', '.pyo', '.prt')) or '__pycache__' in parts or 'autosave' in parts:
        return 'generated_or_backup', 'Editor backups, Git bundles and generated caches/intermediates are not source inputs.'
    if filename.endswith(('.tar', '.tar.gz', '.tar.xz', '.tar.bz2', '.tgz', '.tbz', '.7z', '.rar')):
        return 'uninspected_archive', 'Publish inspected ZIP/PK3 source inputs rather than opaque backup/archive formats.'
    if any(parts[i:i + 2] == ('players', 'male') for i in range(len(parts) - 1)):
        return 'legacy_player_path', 'Legacy male-player media was removed; custom sound/player/male recordings are separate.'
    if filename.endswith('.pak'):
        return 'pak_data', 'The public TC uses project PK3s and must not include PAK data.'
    if 'quake2-appbundle' in filename or filename == 'quake2.icns' or 'quake 2.app' in parts:
        return 'legacy_app_bundle', 'The obsolete branded macOS bundle is not a source input.'
    if filename.endswith(('.exe', '.so', '.dylib', '.dll')):
        return 'compiled_binary', 'Compiled runtime/library binaries belong in release artifacts, not the source snapshot.'
    return None


def stock_hashes(root):
    """Supplement fixed byte identities from the local removal ledger, if present."""
    hashes = dict(KNOWN_HASHES)
    ledger = root / 'tools/assets/review/public-cleanup.json'
    if ledger.is_file():
        data = json.loads(ledger.read_text())
        if not isinstance(data, dict) or not isinstance(data.get('removed_files', []), list):
            raise ValueError('cleanup ledger must be an object with a removed_files array')
        for entry in data.get('removed_files', []):
            if not isinstance(entry, dict) or not isinstance(entry.get('path', ''), str):
                raise ValueError('cleanup ledger contains an invalid file record')
            name = entry.get('path', '')
            if (name.startswith(('baseq2/players/male/', 'stuff/models/crosshair/'))
                    or name == 'stuff/osx/quake2-appbundle.zip'):
                checksum = entry.get('sha256', '')
                if re.fullmatch(r'[0-9a-f]{64}', checksum):
                    hashes[checksum] = name
    return hashes


def inspect_stream(stream, size, location, banned, violations, stats, *, name=None, depth=0, budget=None):
    """Hash in chunks; inspect one spooled object/member at a time, never all history."""
    checksum = hashlib.sha256()
    with tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024) as content:
        remaining = size
        prefix = b''
        while remaining:
            chunk = stream.read(min(1024 * 1024, remaining))
            if not chunk:
                raise ValueError(f'truncated content at {location}')
            if len(prefix) < 12:
                prefix += chunk[:12 - len(prefix)]
            checksum.update(chunk)
            content.write(chunk)
            remaining -= len(chunk)
        digest = checksum.hexdigest()
        if digest in banned:
            issue(violations, 'known_removed_bytes', location, banned[digest], sha256=digest)
        # Reject a hidden, structurally recognizable PACK archive too.
        if len(prefix) >= 12 and prefix[:4] == b'PACK':
            start, length = struct.unpack_from('<ii', prefix, 4)
            if start >= 12 and length >= 0 and length % 64 == 0 and start + length <= size:
                issue(violations, 'pak_data', location, 'Quake PACK archive bytes found, regardless of filename.')
        suffix_is_zip = name is not None and PurePosixPath(name).suffix.lower() in ('.zip', '.pk3')
        if prefix[:4] in ZIP_MAGIC or suffix_is_zip:
            if depth >= MAX_ARCHIVE_DEPTH:
                issue(violations, 'archive_limit', location, 'Nested archive depth exceeds the audit limit.')
                return
            budget = {'bytes': 0, 'members': 0} if budget is None else budget
            content.seek(0)
            try:
                with zipfile.ZipFile(content) as archive:
                    stats['archives_checked'] += 1
                    seen = set()
                    for member in archive.infolist():
                        budget['members'] += 1
                        if budget['members'] > MAX_ARCHIVE_MEMBERS:
                            raise ValueError('archive member count exceeds the audit limit')
                        member_location = location + ':' + member.filename
                        problem = path_policy(member.filename)
                        if problem:
                            issue(violations, problem[0], member_location, problem[1])
                        if member.filename in seen:
                            issue(violations, 'ambiguous_archive', member_location, 'Duplicate ZIP member name.')
                        seen.add(member.filename)
                        if member.is_dir():
                            continue
                        budget['bytes'] += member.file_size
                        if budget['bytes'] > MAX_ARCHIVE_BYTES:
                            raise ValueError('archive expanded size exceeds the audit limit')
                        stats['archive_members_checked'] += 1
                        with archive.open(member) as source:
                            inspect_stream(source, member.file_size, member_location, banned,
                                           violations, stats, name=member.filename,
                                           depth=depth + 1, budget=budget)
            except (ValueError, OSError, RuntimeError, EOFError, zipfile.BadZipFile, NotImplementedError) as error:
                issue(violations, 'invalid_archive', location, str(error))


def git(root, *args, check=True):
    return subprocess.run(['git', '-C', str(root), *args], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=check)


def git_root(root):
    result = git(root, 'rev-parse', '--show-toplevel', check=False)
    if result.returncode:
        return False
    return Path(os.fsdecode(result.stdout).strip()).resolve() == root.resolve()


def source_files(root, filesystem):
    if filesystem:
        for directory, folders, filenames in os.walk(root, followlinks=False):
            relative_dir = Path(directory).relative_to(root)
            for name in sorted(folders):
                if name not in FS_EXCLUDES and (Path(directory) / name).is_symlink():
                    yield (relative_dir / name).as_posix()
            folders[:] = sorted(name for name in folders if name not in FS_EXCLUDES)
            for name in sorted(filenames):
                if name == '.git' or name.endswith(('.pyc', '.pyo')):
                    continue
                yield (relative_dir / name).as_posix()
    else:
        for encoded in git(root, 'ls-files', '-z').stdout.split(b'\0'):
            if encoded:
                yield os.fsdecode(encoded)


def history_audit(root, banned, violations, *, forbidden_commits=FORBIDDEN_COMMITS):
    stats = dict(objects_checked=0, blobs_checked=0, blob_bytes_checked=0,
                 archives_checked=0, archive_members_checked=0)
    object_dir = Path(os.fsdecode(git(root, 'rev-parse', '--git-path', 'objects').stdout).strip())
    if not object_dir.is_absolute():
        object_dir = root / object_dir
    if (object_dir / 'info/alternates').exists() or os.environ.get('GIT_ALTERNATE_OBJECT_DIRECTORIES'):
        issue(violations, 'object_alternates', 'git:objects/info/alternates',
              'External object stores must not be attached to the cleaned repository.')
    if list((object_dir / 'pack').glob('*.promisor')):
        issue(violations, 'partial_object_store', 'git:objects/pack',
              'A partial clone cannot certify that every historical object is locally audited.')
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(['git', '-C', str(root), 'cat-file', '--batch-all-objects', '--batch'],
                                   stdout=subprocess.PIPE, stderr=errors)
        try:
            while True:
                header = process.stdout.readline()
                if not header:
                    break
                fields = header.decode('ascii').strip().split()
                if len(fields) != 3:
                    raise ValueError('unexpected cat-file object header')
                oid, kind, raw_size = fields
                size = int(raw_size)
                stats['objects_checked'] += 1
                if kind == 'commit' and oid in forbidden_commits:
                    issue(violations, 'old_commit_object', 'git:' + oid,
                          'The pre-cleanup baseline commit still exists in the local object store.')
                if kind == 'blob':
                    stats['blobs_checked'] += 1
                    stats['blob_bytes_checked'] += size
                    if size > MAX_GIT_FILE_BYTES:
                        issue(violations, 'oversized_git_blob', 'git:' + oid,
                              'Git blob exceeds the 100 MiB source-file limit.', bytes=size)
                    inspect_stream(process.stdout, size, 'git:' + oid, banned, violations, stats)
                else:
                    remaining = size
                    while remaining:
                        chunk = process.stdout.read(min(1024 * 1024, remaining))
                        if not chunk:
                            raise ValueError('truncated cat-file object')
                        remaining -= len(chunk)
                if process.stdout.read(1) != b'\n':
                    raise ValueError('missing cat-file object separator')
            returncode = process.wait()
            if returncode:
                errors.seek(0)
                raise ValueError(errors.read().decode(errors='replace').strip())
        except (ValueError, OSError, UnicodeError) as error:
            issue(violations, 'git_history_error', 'git:objects', str(error))
            if process.poll() is None:
                process.kill()
            process.wait()
        finally:
            process.stdout.close()
    return stats


def audit(root, *, filesystem=False, history=False, banned=None, max_file_bytes=MAX_GIT_FILE_BYTES):
    root = Path(root).resolve()
    violations = []
    repository = git_root(root)
    if not filesystem and not repository:
        issue(violations, 'not_repository', str(root), 'Use --filesystem before initializing the cleaned repository.')
    try:
        banned = stock_hashes(root) if banned is None else banned
    except (ValueError, OSError) as error:
        banned = dict(KNOWN_HASHES)
        issue(violations, 'invalid_cleanup_ledger', 'tools/assets/review/public-cleanup.json', str(error))
    stats = dict(files_checked=0, file_bytes_checked=0, archives_checked=0,
                 archive_members_checked=0, largest_file_bytes=0, largest_file=None)
    for required in REQUIRED_NOTICES:
        path = root / required
        if not path.is_file() or not path.stat().st_size:
            issue(violations, 'missing_notice', required, 'Required license/provenance document is absent or empty.')
    for name in source_files(root, filesystem) if filesystem or repository else ():
        path = root / name
        problem = path_policy(name)
        if problem:
            issue(violations, problem[0], name, problem[1])
        try:
            if path.is_symlink():
                if not path.resolve().is_relative_to(root):
                    issue(violations, 'escaping_symlink', name, 'Symlink escapes the source root.')
                else:
                    issue(violations, 'source_symlink', name, 'Review source symlinks explicitly rather than auditing target bytes.')
                continue
            if not path.is_file():
                issue(violations, 'missing_tracked_file', name, 'Tracked file is absent from the checkout.')
                continue
            size = path.stat().st_size
            stats['files_checked'] += 1
            stats['file_bytes_checked'] += size
            if size > stats['largest_file_bytes']:
                stats['largest_file_bytes'], stats['largest_file'] = size, name
            if size > max_file_bytes:
                issue(violations, 'oversized_source_file', name, 'Source file exceeds the configured Git file-size limit.', bytes=size)
            with path.open('rb') as source:
                inspect_stream(source, size, name, banned, violations, stats, name=name)
        except (OSError, ValueError) as error:
            issue(violations, 'file_audit_error', name, str(error))
    history_stats = None
    if history:
        if not repository:
            issue(violations, 'history_unavailable', str(root), '--history requires a local Git repository at this exact root.')
        else:
            history_stats = history_audit(root, banned, violations)
    return dict(schema=1, root=str(root), source_selection='filesystem' if filesystem else 'tracked_git_files',
                public_source_checks_pass=not violations, independent_rights_certification=False,
                scope='Known removed-byte identities, nested ZIP/PK3 members, source packaging rules and optional full local Git-object scan.',
                limitations=['Unknown modified stock content cannot be identified from these hashes alone.',
                             'Owner authorship and license declarations remain the provenance evidence.',
                             'Filesystem mode skips local build/release/debug directories and caches; tracked mode audits every tracked file.',
                             'A passing history check concerns this local object store, not an existing remote or third-party forks.'],
                forbidden_hashes=len(banned), source=stats, history=history_stats,
                violations=violations)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--filesystem', action='store_true', help='audit publishable working files before Git initialization')
    parser.add_argument('--history', action='store_true', help='stream every Git object, including unreachable blobs')
    parser.add_argument('--output', type=Path, help='write JSON here instead of stdout')
    parser.add_argument('--strict', action='store_true', help='exit 1 when any check fails')
    args = parser.parse_args()
    report = audit(args.root, filesystem=args.filesystem, history=args.history)
    data = json.dumps(report, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(data)
        print(f'{args.output}: {report["source"]["files_checked"]} source files, '
              f'{len(report["violations"])} violations; independent rights certification not asserted')
    else:
        print(data, end='')
    if args.strict and not report['public_source_checks_pass']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()

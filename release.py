#!/usr/bin/env python3
"""A local, source-derived exact-artifact boundary. No transport or activation."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile
import zlib

PAYLOAD = 'public/index.html'
MEMBERS = {PAYLOAD, 'RELEASE.json', 'MANIFEST.sha256'}
LIMIT = 1024 * 1024


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read_field(text, name):
    match = re.search(rf'^{re.escape(name)}: (.+)$', text, re.M)
    return match.group(1).strip() if match else None


def path_name(name):
    path = PurePosixPath(name)
    require(not path.is_absolute() and '..' not in path.parts and '\\' not in name and '\x00' not in name, 'Unsafe archive path')
    return path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_name(name):
    try:
        path = path_name(name)
    except ValueError as error:
        raise ValueError('STRUCTURE_INVALID: unsafe path') from error
    require(path.as_posix() == name and name != '.' and not re.search(r'[\x00-\x1f\x7f]', name),
            'STRUCTURE_INVALID: noncanonical path')
    return name


def context(repository, workflow, run_id, attempt):
    require(isinstance(repository, str) and re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository), 'EVIDENCE_MISMATCH: repository')
    require(isinstance(workflow, str) and re.fullmatch(r'[^\x00-\x1f\x7f]{1,128}', workflow) and workflow == workflow.strip() and len(workflow.splitlines()) == 1, 'EVIDENCE_MISMATCH: workflow')
    for value in (run_id, attempt):
        require(isinstance(value, str) and re.fullmatch(r'[1-9][0-9]*', value), 'EVIDENCE_MISMATCH: run/attempt')


def git(source, *args):
    result = subprocess.run(['git', '-C', str(source), *args], capture_output=True)
    require(result.returncode == 0, 'SOURCE_INVALID: Git lookup failed')
    return result.stdout


def clean(source):
    require(not git(source, 'status', '--porcelain', '--untracked-files=all').strip(), 'SOURCE_INVALID: dirty checkout')


def archive_bytes(records):
    """Canonical builder, also used by synthetic adversarial fixture construction."""
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode='w', format=tarfile.USTAR_FORMAT) as bundle:
        for name, data in sorted(records.items()):
            member = tarfile.TarInfo(name)
            member.size = len(data)
            member.mode = 0o644
            bundle.addfile(member, io.BytesIO(data))
    return gzip.compress(raw.getvalue(), mtime=0)


def manifest_bytes(records):
    return ''.join(f'{digest(data)}  {name}\n' for name, data in sorted(records.items())).encode()


def evidence_fields(repository, workflow, revision, tree, run_id, attempt, archive, sha, manifest):
    return {'Repository': repository, 'Workflow name': workflow, 'Workflow event': 'push',
            'Workflow ref': 'refs/heads/main', 'Workflow conclusion': 'success',
            'Git revision': revision, 'Git tree': tree, 'Workflow run': f'{run_id} attempt {attempt}',
            'Release archive': archive, 'Release SHA256': sha, 'Release manifest SHA256': manifest}


def package(source, output, *, repository, workflow, run_id, attempt):
    context(repository, workflow, run_id, attempt)
    source, output = Path(source).resolve(), Path(output)
    require(not output.is_symlink(), 'SOURCE_INVALID: output link')
    output = output.resolve()
    require(not output.is_relative_to(source), 'SOURCE_INVALID: output must be outside source')
    require(git(source, 'rev-parse', '--show-toplevel').decode().strip() == str(source), 'SOURCE_INVALID: expected Git root')
    clean(source)
    revision = git(source, 'rev-parse', 'HEAD').decode().strip()
    tree = git(source, 'rev-parse', f'{revision}^{{tree}}').decode().strip()
    require(all(re.fullmatch(r'[0-9a-f]{40}', item) for item in (revision, tree)), 'SOURCE_INVALID: full SHA-1 identity required')
    inventory = git(source, 'ls-tree', '-rz', '--name-only', revision, '--', 'public/').split(b'\0')
    require(inventory == [PAYLOAD.encode(), b''], 'SOURCE_INVALID: unexpected/missing public member')
    mode = git(source, 'ls-tree', revision, '--', PAYLOAD).decode().split()[0]
    require(mode in ('100644', '100755'), 'SOURCE_INVALID: payload must be a committed regular file')
    payload = git(source, 'show', f'{revision}:{PAYLOAD}')
    require(len(payload) <= LIMIT // 2, 'SOURCE_INVALID: payload too large')
    metadata = {'format_version': 1, 'commit': revision, 'tree': tree, 'dirty': False}
    records = {PAYLOAD: payload, 'RELEASE.json': (json.dumps(metadata, sort_keys=True) + '\n').encode()}
    manifest = manifest_bytes(records)
    records['MANIFEST.sha256'] = manifest
    data = archive_bytes(records)
    require(len(data) <= LIMIT, 'SOURCE_INVALID: archive too large')
    require(not output.exists() or (output.is_dir() and not any(output.iterdir())), 'SOURCE_INVALID: output must be empty')
    name = f'release-{revision[:12]}.tar.gz'
    fields = evidence_fields(repository, workflow, revision, tree, run_id, attempt, name, digest(data), digest(manifest))
    output.mkdir(parents=True, exist_ok=True)
    archive, evidence = output / name, output / 'evidence.txt'
    written = []
    try:
        for path, content in [(archive, data), (evidence, ''.join(f'{k}: {v}\n' for k, v in fields.items()).encode())]:
            with path.open('xb') as stream:
                written.append(path)
                stream.write(content)
        clean(source)
        require(git(source, 'rev-parse', 'HEAD').decode().strip() == revision, 'SOURCE_INVALID: source revision changed')
    except Exception:
        for path in written:
            path.unlink()
        raise
    return {'archive': str(archive), 'evidence': str(evidence), 'repository': repository, 'workflow': workflow,
            'revision': revision, 'tree': tree, 'run_id': run_id, 'attempt': attempt,
            'expected_sha': digest(data), 'expected_manifest': digest(manifest)}


def bounded_file(path, label):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), f'STRUCTURE_INVALID: regular {label} required')
    with path.open('rb') as stream:
        data = stream.read(LIMIT + 1)
    require(len(data) <= LIMIT, f'STRUCTURE_INVALID: {label} too large')
    return data


def read_members(data):
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
            raw = stream.read(LIMIT + 1)
    except (OSError, EOFError, zlib.error) as error:
        raise ValueError('STRUCTURE_INVALID: malformed gzip') from error
    require(len(raw) <= LIMIT and len(raw) % 512 == 0, 'STRUCTURE_INVALID: expanded size')
    records, offset = {}, 0
    while offset < len(raw):
        header = raw[offset:offset + 512]
        if header == bytes(512):
            require(len(raw) - offset >= 1024 and not any(raw[offset:]), 'STRUCTURE_INVALID: invalid tar ending')
            break
        try:
            member = tarfile.TarInfo.frombuf(header, 'utf-8', 'strict')
        except (tarfile.TarError, UnicodeError, ValueError) as error:
            raise ValueError('STRUCTURE_INVALID: malformed tar header') from error
        require(member.type in (tarfile.REGTYPE, tarfile.AREGTYPE), 'STRUCTURE_INVALID: links/extensions/specials prohibited')
        name = safe_name(member.name)
        require(name not in records, 'STRUCTURE_INVALID: duplicate member')
        require(name in MEMBERS, 'INVENTORY_MISMATCH: unexpected member')
        require(0 <= member.size <= LIMIT, 'STRUCTURE_INVALID: member size')
        end = offset + 512 + member.size
        require(end <= len(raw), 'STRUCTURE_INVALID: truncated member')
        records[name] = raw[offset + 512:end]
        offset += 512 + ((member.size + 511) // 512) * 512
    else:
        raise ValueError('STRUCTURE_INVALID: missing tar ending')
    require(set(records) == MEMBERS, 'INVENTORY_MISMATCH: missing member')
    return records


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'IDENTITY_MISMATCH: duplicate metadata key')
        result[key] = value
    return result


def verify_payload(expected, actual):
    """Keep inventory and content comparison distinct for fault-sensitivity tests."""
    require(expected.keys() == actual.keys(), 'INVENTORY_MISMATCH: manifest membership')
    require(expected == actual, 'PAYLOAD_HASH_MISMATCH: manifest files or hashes differ')


def validate(archive, evidence, *, repository, revision, tree, workflow, run_id, attempt, expected_sha, expected_manifest):
    context(repository, workflow, run_id, attempt)
    require(all(isinstance(v, str) and re.fullmatch(r'[0-9a-f]{40}', v) for v in (revision, tree)), 'IDENTITY_MISMATCH: full source SHA required')
    require(all(isinstance(v, str) and re.fullmatch(r'[0-9a-f]{64}', v) for v in (expected_sha, expected_manifest)), 'EVIDENCE_MISMATCH: expected digests')
    archive = Path(archive)
    require(archive.name == f'release-{revision[:12]}.tar.gz', 'IDENTITY_MISMATCH: archive name')
    data = bounded_file(archive, 'archive')
    require(digest(data) == expected_sha, 'ARCHIVE_HASH_MISMATCH: archive differs from trusted digest')
    try:
        text = bounded_file(evidence, 'evidence').decode('utf-8')
    except UnicodeError as error:
        raise ValueError('EVIDENCE_MISMATCH: invalid text') from error
    expected = evidence_fields(repository, workflow, revision, tree, run_id, attempt, archive.name, expected_sha, expected_manifest)
    keys = []
    for row in text.splitlines():
        match = re.fullmatch(r'([^:]+): (.+)', row)
        require(match is not None and match[2] == match[2].strip(), 'EVIDENCE_MISMATCH: malformed field')
        keys.append(match[1])
    require(len(keys) == len(set(keys)) and set(keys) == set(expected), 'EVIDENCE_MISMATCH: missing/extra/duplicate field')
    require(all(read_field(text, key) == value for key, value in expected.items()), 'EVIDENCE_MISMATCH: context or digest differs')
    records = read_members(data)
    try:
        metadata = json.loads(records['RELEASE.json'], object_pairs_hook=strict_object)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise ValueError('IDENTITY_MISMATCH: malformed release metadata') from error
    require(isinstance(metadata, dict) and type(metadata.get('format_version')) is int
            and metadata.get('dirty') is False
            and metadata == {'format_version': 1, 'commit': revision, 'tree': tree, 'dirty': False},
            'IDENTITY_MISMATCH: release must match exact clean source')
    manifest = records.pop('MANIFEST.sha256')
    require(digest(manifest) == expected_manifest, 'MANIFEST_HASH_MISMATCH: manifest differs from trusted digest')
    inventory = {}
    try:
        rows = manifest.decode('utf-8').splitlines()
    except UnicodeError as error:
        raise ValueError('STRUCTURE_INVALID: invalid manifest text') from error
    for row in rows:
        match = re.fullmatch(r'([0-9a-f]{64})  (.+)', row)
        require(match is not None, 'STRUCTURE_INVALID: malformed manifest row')
        name = safe_name(match[2])
        require(name not in inventory, 'INVENTORY_MISMATCH: duplicate manifest member')
        inventory[name] = match[1]
    actual = {name: digest(content) for name, content in records.items()}
    verify_payload(inventory, actual)
    return {'status': 'verified', 'revision': revision, 'tree': tree, 'sha256': expected_sha,
            'manifest_sha256': expected_manifest, 'members': len(records) + 1}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    build = commands.add_parser('package')
    build.add_argument('source', type=Path)
    build.add_argument('output', type=Path)
    check = commands.add_parser('validate')
    check.add_argument('archive', type=Path)
    check.add_argument('evidence', type=Path)
    for command in (build, check):
        for name in ('repository', 'workflow', 'run-id', 'attempt'):
            command.add_argument('--' + name, required=True)
    for name in ('revision', 'tree', 'expected-sha', 'expected-manifest'):
        check.add_argument('--' + name, required=True)
    args = vars(parser.parse_args())
    command = args.pop('command')
    try:
        result = (package if command == 'package' else validate)(**args)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, OSError) as error:
        print(json.dumps({'status': 'rejected', 'error': str(error)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

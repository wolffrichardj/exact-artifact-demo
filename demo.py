#!/usr/bin/env python3
"""Rehearse a valid artifact and an inner-layer tamper, entirely locally."""
import json
from pathlib import Path
import tempfile
import release as r


def main():
    with tempfile.TemporaryDirectory(prefix='exact-artifact-') as temporary:
        info = r.package(Path(__file__).resolve().parent, Path(temporary) / 'artifact',
                         repository='example/exact-artifact-demo', workflow='synthetic-local', run_id='1', attempt='1')
        valid = r.validate(**info)
        archive = Path(info['archive'])
        records = r.read_members(archive.read_bytes())
        records[r.PAYLOAD] = b'Synthetic substituted payload\n'
        archive.write_bytes(r.archive_bytes(records))
        # Test constructor re-pins only the outer digest. Stale file manifest stays.
        new_sha = r.digest(archive.read_bytes())
        evidence = Path(info['evidence'])
        evidence.write_text(evidence.read_text().replace(info['expected_sha'], new_sha))
        try:
            r.validate(**(info | {'expected_sha': new_sha}))
        except ValueError as error:
            if not str(error).startswith('PAYLOAD_HASH_MISMATCH:'):
                raise
            rejection = str(error)
        else:
            raise RuntimeError('Tampered payload was accepted')
        print(json.dumps({'valid': valid, 'tampered': {'status': 'rejected', 'error': rejection},
                          'context': 'synthetic local expectations, not authenticated CI'}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

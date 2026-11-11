#!/bin/sh
# Python 3.11+ and Git. No deployment or authenticated CI.
# Leaves its fresh temporary workspace for inspection, prints its location.
set -eu
workspace=$(mktemp -d "${TMPDIR:-/tmp}/exact-walkthrough.XXXXXX")
printf 'Synthetic reproduction workspace: %s\n' "$workspace"
git clone --quiet https://github.com/wolffrichardj/exact-artifact-demo.git "$workspace/source"
git -C "$workspace/source" checkout --quiet --detach 076da3474dbbac3f3cd882dd3b37403501933c56
cd "$workspace/source"
test "$(git rev-parse HEAD)" = 076da3474dbbac3f3cd882dd3b37403501933c56
python3 -B -m unittest discover -s tests -v
python3 -B demo.py > "$workspace/demo.json"
cat "$workspace/demo.json"
python3 -B - "$workspace/demo.json" <<'PY'
import json,sys
x=json.load(open(sys.argv[1]))
assert x['valid']['status']=='verified' and x['valid']['members']==3
assert x['valid']['revision']=='076da3474dbbac3f3cd882dd3b37403501933c56'
assert x['tampered']=={'status':'rejected','error':'PAYLOAD_HASH_MISMATCH: manifest files or hashes differ'}
assert x['context']=='synthetic local expectations, not authenticated CI'
print('PASS: valid artifact verified; substituted payload rejected beneath repinned outer hash.')
PY
test -z "$(git status --porcelain --untracked-files=all)"

'''
Bring the fetched-html folder up to date with the child repositories.

For every child in children.json this finds the latest successful run of the
child's docs workflow and, if it differs from the run recorded in runs.json,
downloads that run's HTML artifact into <fetched>/<child>/.  When the
workflow was started by a child's signal, the signalling run (CHILD, RUN_ID)
is used for that child instead:  its artifact is ready although the run has
not finished yet.

A child whose artifact cannot be downloaded keeps its previous copy.

    python scripts/fetch.py fetched

Needs the gh command line tool and GH_TOKEN (read access to the children's
Actions).  Writes changed=true|false to GITHUB_OUTPUT when that is set.
'''

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

root     = Path(__file__).resolve().parent.parent
children = json.loads((root / 'children.json').read_text())
fetched  = Path(sys.argv[1])
fetched.mkdir(parents=True, exist_ok=True)
runsfile = fetched / 'runs.json'
runs     = json.loads(runsfile.read_text()) if runsfile.exists() else {}

signal_child = os.environ.get('CHILD', '')
signal_run   = os.environ.get('RUN_ID', '')
if signal_child and (signal_child not in children or not signal_run.isdigit()):
    print(f'::warning::ignoring signal child={signal_child!r} run={signal_run!r}')
    signal_child = ''


def gh(*args):
    return subprocess.run(['gh', *args], check=True, capture_output=True, text=True).stdout.strip()


def latest_run(c):
    return gh('run', 'list', '-R', c['repo'], '-w', c['workflow'], '-b', c['branch'], '-s', 'success',
              '-L', '1', '--json', 'databaseId', '-q', '.[0].databaseId')


changed = False
for name, c in children.items():
    try:
        run = signal_run if name == signal_child else latest_run(c)
    except subprocess.CalledProcessError as e:
        print(f'::warning::{name}: cannot list runs of {c["repo"]}: {e.stderr.strip()}')
        continue
    if not run:
        print(f'::warning::{name}: no successful run of workflow {c["workflow"]} in {c["repo"]}')
        continue
    if runs.get(name) == run and (fetched / name).is_dir():
        print(f'{name}: up to date (run {run})')
        continue
    tmp = Path(tempfile.mkdtemp())
    try:
        gh('run', 'download', run, '-R', c['repo'], '-n', c['artifact'], '-D', str(tmp))
    except subprocess.CalledProcessError as e:
        print(f'::warning::{name}: cannot download artifact {c["artifact"]} of run {run}: {e.stderr.strip()}')
        shutil.rmtree(tmp, ignore_errors=True)
        continue
    shutil.rmtree(fetched / name, ignore_errors=True)
    shutil.move(str(tmp), fetched / name)
    runs[name] = run
    changed    = True
    print(f'{name}: fetched run {run}')

for d in fetched.iterdir():                     # children no longer listed
    if d.is_dir() and d.name not in children and not d.name.startswith('.'):
        shutil.rmtree(d)
        runs.pop(d.name, None)
        changed = True
        print(f'{d.name}: removed (not in children.json)')

runsfile.write_text(json.dumps(runs, indent=2, sort_keys=True) + '\n')
if 'GITHUB_OUTPUT' in os.environ:
    with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
        f.write(f'changed={"true" if changed else "false"}\n')

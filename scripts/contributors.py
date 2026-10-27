'''
Write the list of code contributors to <dir>/contributors.json.

Reads the commits of each repository in REPOS through the GitHub API and
lists every GitHub user who authored a commit, most recent contributor
first, as [{"login": ..., "name": ...}, ...].  Commits whose author is not
linked to a GitHub account, and bots, are left out.  Dates are not written:
the landing page shows names only.

    python scripts/contributors.py fetched

Uses GITHUB_TOKEN (the built-in token is enough, the repositories are
public); without it the unauthenticated rate limit applies.  If the API
cannot be read, the previous contributors.json is kept.  Writes
changed=true|false to GITHUB_OUTPUT when that is set.
'''

import json
import os
import sys
import urllib.request
from pathlib import Path

API   = os.environ.get('GITHUB_API_URL', 'https://api.github.com')
REPOS = [
    'spm1d-org/spm1d-v0.4',
    'spm1d-org/spm1d-matlab-v0.4',
    'spm1d-org/rft1d',
    'spm1d-org/power1d',
]


def get(url):
    req = urllib.request.Request(url, headers={'Accept': 'application/vnd.github+json'})
    if os.environ.get('GITHUB_TOKEN'):
        req.add_header('Authorization', f'Bearer {os.environ["GITHUB_TOKEN"]}')
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r), r.headers.get('Link', '')


def pages(url):
    while url:
        data, link = get(url)
        yield from data
        url = next((p.split(';')[0].strip(' <>') for p in link.split(',') if 'rel="next"' in p), None)


def is_bot(user):
    return user.get('type') == 'Bot' or user['login'].endswith('[bot]')


def contributors():
    last = {}                                    # login -> date of the latest commit
    for repo in REPOS:
        for c in pages(f'{API}/repos/{repo}/commits?per_page=100'):
            user = c.get('author')
            if not user or is_bot(user):
                continue
            date = c['commit']['author']['date']
            if date > last.get(user['login'], ''):
                last[user['login']] = date
    logins = sorted(last, key=lambda u: last[u], reverse=True)
    return [{'login': u, 'name': get(f'{API}/users/{u}')[0].get('name') or u} for u in logins]


out  = Path(sys.argv[1]) / 'contributors.json'
old  = out.read_text() if out.exists() else ''
try:
    new = json.dumps(contributors(), indent=2, ensure_ascii=False) + '\n'
except Exception as e:                           # keep the previous list
    print(f'::warning::cannot read the contributors: {e}')
    new = old
if new != old:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(new)
print(f'{len(json.loads(new)) if new else 0} contributors{" (changed)" if new != old else ""}')
if 'GITHUB_OUTPUT' in os.environ:
    with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
        f.write(f'changed={"true" if new != old else "false"}\n')

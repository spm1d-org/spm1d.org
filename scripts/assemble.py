'''
Assemble the site from the site's own pages and the children's HTML.

    /                the pages in site/ (landing page, ...)
    /<child>/        each child's HTML, for every child in children.json
    /<old path>      for a child with "redirect_from_root", a redirect stub at
                     each of its pages' old top-level addresses

All links are relative, so the site works both at spm1d.org and at its
GitHub Pages project address (spm1d-org.github.io/spm1d.org/).

Every HTML page except the redirect stubs gets the GoatCounter snippet
(pages that already carry it are left as they are).

On GitHub Actions the children's HTML comes from the fetched-html branch:

    python scripts/assemble.py --fetched fetched --out _site

Locally it can come from your own builds, child by child:

    python scripts/assemble.py --out _site --child rft1d=../rft1d/doc/build/html

A child given with --child overrides the copy in --fetched.  A child with no
HTML is left out with a warning.
'''

import argparse
import json
import os
import re
import shutil
from pathlib import Path

GOATCOUNTER = '<script data-goatcounter="https://spm1d.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>'

STUB = '''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="0; url={url}">
<link rel="canonical" href="{url}">
<script>location.replace("{url}" + location.hash)</script>
<title>Redirecting</title></head>
<body><p>This page has moved to <a href="{url}">{url}</a>.</p></body></html>
'''

root = Path(__file__).resolve().parent.parent
ap   = argparse.ArgumentParser()
ap.add_argument('--fetched', type=Path)
ap.add_argument('--child', action='append', default=[], metavar='NAME=PATH')
ap.add_argument('--out', type=Path, required=True)
args = ap.parse_args()

children  = json.loads((root / 'children.json').read_text())
overrides = {}
for item in args.child:
    name, _, path = item.partition('=')
    if name not in children:
        ap.error(f'--child {name}: not in children.json')
    overrides[name] = Path(path).expanduser()

out = args.out
if out.exists():
    shutil.rmtree(out)
shutil.copytree(root / 'site', out)
shutil.copy(root / 'CNAME', out / 'CNAME')
(out / '.nojekyll').touch()

included = []
for name in children:
    src = overrides.get(name) or (args.fetched / name if args.fetched else None)
    if src is None or not src.is_dir():
        print(f'warning: {name}: no HTML found, left out')
        continue
    shutil.copytree(src, out / name, ignore=shutil.ignore_patterns('.doctrees', '.buildinfo'))
    included.append(name)
    print(f'{name}: from {src}')

head = re.compile(r'</head>', re.IGNORECASE)
n = 0
for page in out.rglob('*.html'):
    text = page.read_text(encoding='utf-8', errors='surrogateescape')
    if 'gc.zgo.at/count.js' in text or not head.search(text):
        continue
    page.write_text(head.sub(GOATCOUNTER + '\n</head>', text, count=1), encoding='utf-8', errors='surrogateescape')
    n += 1
print(f'GoatCounter snippet added to {n} pages')

n = 0
for name in included:
    if not children[name].get('redirect_from_root'):
        continue
    for page in (out / name).rglob('*.html'):
        rel  = page.relative_to(out / name)
        stub = out / rel
        if rel.as_posix() == 'index.html' or stub.exists():
            continue
        stub.parent.mkdir(parents=True, exist_ok=True)
        url = os.path.relpath(out / name / rel, stub.parent).replace(os.sep, '/')   # relative, so it also works under a project-site path
        stub.write_text(STUB.format(url=url))
        n += 1
print(f'{n} redirect stubs written')

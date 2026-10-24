# spm1d.org

The site is assembled, not built here. Each child package builds its own documentation in its own repository with GitHub Actions. This repository fetches those builds, keeps them on the branch `fetched-html`, adds the site's own pages, and deploys the result to GitHub Pages. No documentation source is edited here.

```
site/                    the site's own pages (landing page), copied to /
children.json            the child packages: repository, branch, docs workflow, artifact
scripts/fetch.py         updates fetched-html from the children's latest successful builds
scripts/assemble.py      lays out the site, adds redirects and the GoatCounter snippet
.github/workflows/deploy.yml
CNAME                    spm1d.org
```

Branch `fetched-html` holds one folder per child (`spm1d-v0.4/`, `rft1d/`, `power1d/`) and `runs.json`, the workflow run each folder came from. It always holds a single commit, which the deploy workflow replaces whenever a child's HTML changes.

## How a change reaches the site

1. A change is pushed to a child repository.
2. The child's `docs` workflow builds the HTML and uploads it as the artifact `docs-html`.
3. If the build succeeded, the workflow's last step sends a `docs-updated` signal to this repository.
4. The `deploy` workflow here downloads that build, replaces the child's folder on `fetched-html`, assembles the site and deploys it.

A child that has not changed keeps its stored copy, so the 90-day expiry of workflow artifacts does not matter. The `deploy` workflow also checks every child's latest successful build each time it runs, so a missed signal is caught up on the next run. It also runs on every push to `main` and can be run by hand (Actions → deploy → Run workflow).

## Addresses

- `/` is the landing page in `site/index.html`.
- `/<child>/` is each child's documentation, for example `/spm1d-v0.4/`, `/rft1d/`, `/power1d/`.
- The old spm1d v0.4 addresses (`/Downloads.html`, `/doc/...`, ...) are small pages that redirect to the same page under `/spm1d-v0.4/`.

Every page except the redirect pages carries the GoatCounter snippet (`spm1d.goatcounter.com`). `scripts/assemble.py` inserts it before `</head>` unless the page already has it.

## Setting it up

1. Repository `spm1d-org/spm1d.org`, with this folder's contents on `main`.
2. Token for reading the children's builds: a fine-grained token with resource owner `spm1d-org`, repository access to the child repositories, permissions **Actions: read-only** (+ Metadata). Store it here as the Actions secret `DOCS_TOKEN`.
3. Settings → Actions → General → Workflow permissions: **Read and write**, so that the workflow can update `fetched-html`.
4. Settings → Pages → Source: **GitHub Actions**.
5. Domain: verify `spm1d.org` for the organization (Settings → Pages → Add a domain, add the TXT record). At the switch, remove `CNAME` from the old `gh-pages` branch of the old site and set the custom domain here. DNS needs no change if the apex already points at GitHub Pages.
6. In each child repository: the `docs` workflow below and the secret `SITE_DISPATCH_TOKEN`.
7. Run the `deploy` workflow by hand and check `/`, `/spm1d-v0.4/`, `/rft1d/`, `/power1d/` and one old v0.4 address such as `/Downloads.html` (it should redirect).

## Adding a child

1. In the child repository, add the `docs` workflow below (adjusted to how that child builds its docs) and the secret `SITE_DISPATCH_TOKEN`: a fine-grained token with repository access to `spm1d-org/spm1d.org` and permission **Contents: read and write** (+ Metadata).
2. Add the child's repository to the access list of `DOCS_TOKEN`.
3. Add the child to `children.json`. Its key is its folder name and address on the site.
4. Add a button for it to `site/index.html`.
5. Push to `main`. The `deploy` workflow fetches the child's latest successful build and publishes it.

The child's `docs` workflow (the build step differs from child to child):

```yaml
name: docs

on:
  push:
    branches: [ main ]
  workflow_dispatch:

jobs:

  build:
    runs-on: ubuntu-24.04

    steps:

    - name: Checkout
      uses: actions/checkout@v5

    - name: Set up Python
      uses: actions/setup-python@v6
      with:
        python-version: '3.12'

    - name: Install dependencies
      run: pip install -r doc/requirements.txt

    - name: Build
      run: sphinx-build -E -a -b html doc/source doc/build/html

    - name: Upload the HTML
      uses: actions/upload-artifact@v4
      with:
        name: docs-html
        path: doc/build/html

    - name: Notify the site
      if: github.ref == 'refs/heads/main'
      env:
        TOKEN: ${{ secrets.SITE_DISPATCH_TOKEN }}
        CHILD: rft1d          # this child's key in children.json
      run: |
        if [ -z "$TOKEN" ]; then echo "no SITE_DISPATCH_TOKEN; skipped"; exit 0; fi
        curl -sS -X POST -H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github+json" \
          https://api.github.com/repos/spm1d-org/spm1d.org/dispatches \
          -d "{\"event_type\": \"docs-updated\", \"client_payload\": {\"child\": \"$CHILD\", \"run_id\": \"$GITHUB_RUN_ID\"}}"
```

## Building the site locally

Build each child's docs in its own clone as usual (for example `make html`), then assemble the site from those builds and serve it:

```
python scripts/assemble.py --out _site \
    --child spm1d-v0.4=../spm1d/doc/build \
    --child rft1d=../rft1d/doc/build/html \
    --child power1d=../power1d/docs/build/html
python -m http.server -d _site 8000
```

and open `http://localhost:8000/`. The paths are examples: give each child's own build folder. A child given no `--child` path is left out. Adding `--fetched <folder>` uses a checkout of `fetched-html` for the children not given with `--child`.

`_site/` is not committed.

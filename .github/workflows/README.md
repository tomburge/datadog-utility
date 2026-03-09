# GitHub Actions Workflows

## Overview

Three workflows handle CI and publishing in a dependent chain:

```text
Test Build  ── (v* tag) ──►  Publish to TestPyPI
                                    │
                          (create GitHub release)
                                    ▼
                             Publish to PyPI
```

---

## Workflows

### 1. Test Build (`test-build.yml`)

Validates the package builds correctly across all supported platforms and Python versions.

**Triggers:**

- Push to `main`, `master`, or `develop`
- Push of a `v*` tag
- Pull request to `main`, `master`, or `develop`
- Manual dispatch

**Matrix:** Python 3.12 – 3.14 × Ubuntu / Windows / macOS

**Jobs:**

| Job | Description |
| -- | -- |
| `test-build` | Builds, metadata-checks, and inspects the wheel on each matrix combination |
| `upload-dist` | Runs only on `v*` tags (after `test-build` passes); builds once and uploads the distribution artifact for downstream workflows |

---

### 2. Publish to TestPyPI (`publish-test.yml`)

Publishes the package to [TestPyPI](https://test.pypi.org) for validation before a production release.

**Triggers:**

- Automatic: `workflow_run` — fires when **Test Build** completes successfully on a `v*` tag
- Manual dispatch: requires a `source-run-id` (the Test Build run ID to download the artifact from)

**Jobs:**

| Job | Description |
| -- | -- |
| `publish-to-testpypi` | Downloads the artifact from the triggering Test Build run, publishes to TestPyPI, then re-uploads the artifact so Publish to PyPI can reference it |

**Required GitHub environment:** `testpypi`

---

### 3. Publish to PyPI (`publish.yml`)

Publishes the package to the production [PyPI](https://pypi.org).

**Triggers:**

- Automatic: GitHub `release` event (`published`)
- Manual dispatch

**Jobs:**

| Job | Description |
| -- | -- |
| `build` | Checks out code, builds the distribution, and uploads the artifact |
| `publish-to-pypi` | Depends on `build`; downloads the artifact and publishes to PyPI |

**Required GitHub environment:** `pypi`

---

## Setup

### Trusted Publishing (OIDC — Recommended)

No API tokens required. Configure once on PyPI/TestPyPI.

**TestPyPI:**

1. Go to <https://test.pypi.org/manage/account/publishing/>
2. Add a pending publisher:
   - Project: `ddutil`
   - Owner: `<your-github-username-or-org>`
   - Repository: `datadog-utility`
   - Workflow: `publish-test.yml`
   - Environment: `testpypi`

**PyPI:**

1. Go to <https://pypi.org/manage/account/publishing/>
2. Add a pending publisher with the same details but:
   - Workflow: `publish.yml`
   - Environment: `pypi`

### GitHub Environments

Create two environments in **Settings → Environments**:

| Environment | Protection rules (recommended) |
| -- | -- |
| `testpypi` | None required |
| `pypi` | Required reviewers or deployment branch rule (`v*` tags) |

---

## Release Process

```bash
# 1. Update version in pyproject.toml
#    [project]
#    version = "x.y.z"

# 2. Commit and push a version tag — triggers Test Build + Publish to TestPyPI
git tag vx.y.z
git push --tags

# 3. Verify the package on TestPyPI
pip install -i https://test.pypi.org/simple/ ddutil==x.y.z

# 4. Create a GitHub release — triggers Publish to PyPI
#    GitHub UI: Releases → Draft a new release → select tag vx.y.z → Publish
```

# Release Process

This document describes how to release a new version of `ddutil` to PyPI.

## Prerequisites

1. **PyPI Account**: Ensure you have a PyPI account
2. **Trusted Publishing** (Recommended): Configure trusted publishing on PyPI
3. **GitHub Permissions**: Write access to create releases

## Release Steps

### 1. Update Version

Edit `pyproject.toml` and update the version:

```toml
[project]
version = "0.2.0"  # Update this line
```

### 2. Update ROADMAP.md (if needed)

Mark completed features and add new planned features.

### 3. Commit Changes

```bash
git add pyproject.toml ROADMAP.md
git commit -m "Bump version to 0.2.0"
git push origin main
```

### 4. Create a GitHub Release

1. Go to: <https://github.com/tomburge/datadog-utility/releases/new>
2. Click "Choose a tag" and create a new tag: `v0.2.0`
3. Enter release title: `v0.2.0 - <Release Name>`
4. Add release notes describing:
   - New features
   - Bug fixes
   - Breaking changes (if any)
   - Upgrade instructions (if needed)
5. Click "Publish release"

### 5. Automatic Publishing

The GitHub Action will automatically:

1. Build the distribution packages (wheel + source)
2. Validate the packages
3. Publish to PyPI (using trusted publishing)

Monitor the workflow at: <https://github.com/tomburge/datadog-utility/actions>

### 6. Verify Publication

Check that the new version appears on PyPI:

- <https://pypi.org/project/ddutil/>

Test installation:

```bash
pip install --upgrade ddutil
ddutil --version
```

## Testing Before Release

### Test with TestPyPI First

1. Go to Actions → "Publish to PyPI" → "Run workflow"
2. Select `testpypi` from the dropdown
3. Click "Run workflow"
4. After successful publish, test installation:

   ```bash
   pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ ddutil
   ```

### Local Build Test

Test building the package locally:

```bash
# Install build tools
pip install build twine

# Build the package
python -m build

# Check the distribution
twine check dist/*

# View wheel contents
python -m zipfile -l dist/*.whl
```

## Setting Up Trusted Publishing

### On PyPI

1. Go to <https://pypi.org/manage/account/publishing/>
2. Add a new pending publisher:
   - **PyPI Project Name**: `ddutil`
   - **Owner**: `<your-github-username>` (or organization)
   - **Repository name**: `datadog-utility`
   - **Workflow name**: `publish.yml`
   - **Environment name**: `pypi`
3. Save the configuration

### On TestPyPI (for testing)

1. Go to <https://test.pypi.org/manage/account/publishing/>
2. Follow the same steps as PyPI above

## Version Numbering

Follow [Semantic Versioning](https://semver.org/):

- **MAJOR** version (1.0.0): Incompatible API changes
- **MINOR** version (0.1.0): Add functionality (backwards compatible)
- **PATCH** version (0.0.1): Backwards compatible bug fixes

## Rollback

If you need to remove a version from PyPI:

```bash
# Cannot delete, but can yank (hide from default searches)
# This requires pypi-token with appropriate permissions
twine upload --skip-existing dist/*
```

Note: PyPI doesn't allow re-uploading the same version number. If there's an issue, release a new patch version.

## Troubleshooting

### Build Fails

1. Check Python version compatibility in `pyproject.toml`
2. Ensure all dependencies are correctly specified
3. Verify LICENSE files are included correctly

### Publish Fails

1. Check GitHub Action logs
2. Verify trusted publishing is configured on PyPI
3. Ensure the tag follows the pattern `v*` (e.g., `v0.1.0`)
4. Check that the PyPI project name matches `ddutil`

### Installation Issues

1. Verify the version exists on PyPI
2. Check for typos in package name
3. Ensure pip is up to date: `pip install --upgrade pip`

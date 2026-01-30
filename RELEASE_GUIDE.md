# PyPI Release Steps for flaqes v0.1.0

## Pre-Release Checklist ✅

- [x] All tests passing (270/270)
- [x] Coverage at 90%
- [x] CLI tested on real database
- [x] README.md updated
- [x] Python version requirement: 3.10+
- [x] Package name: `flaqes`
- [x] Version: `0.1.0` in pyproject.toml
- [x] LICENSE file present (MIT)
- [x] Dependencies specified correctly

## Release Steps

### 1. Build the Package

```bash
# Clean any previous builds
rm -rf dist/ build/ *.egg-info

# Build the package
python -m build

# or with uv
uv build
```

This creates:
- `dist/flaqes-0.1.0.tar.gz` (source distribution)
- `dist/flaqes-0.1.0-py3-none-any.whl` (wheel distribution)

### 2. Test the Package Locally

```bash
# Create a test environment
uv venv test-env
source test-env/bin/activate

# Install from local wheel
pip install dist/flaqes-0.1.0-py3-none-any.whl[postgresql]

# Test the CLI
flaqes --help
flaqes analyze postgresql://localhost/test_db

# Deactivate when done
deactivate
```

### 3. Upload to Test PyPI (Optional but Recommended)

```bash
# Install twine if needed
pip install twine

# Upload to Test PyPI
twine upload --repository testpypi dist/*

# Test installation from Test PyPI
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ flaqes[postgresql]
```

### 4. Upload to Production PyPI

```bash
# Upload to PyPI
twine upload dist/*

# You'll be prompted for your PyPI credentials
# Username: __token__
# Password: <your PyPI API token>
```

### 5. Verify the Release

```bash
# Install from PyPI
pip install flaqes[postgresql]

# Test it works
flaqes --version
flaqes analyze <your-database-url>
```

### 6. Create GitHub Release

```bash
# Tag the release
git tag -a v0.1.0 -m "Release v0.1.0 - Initial alpha release"
git push origin v0.1.0
```

Then on GitHub:
1. Go to Releases → Draft a new release
2. Select tag `v0.1.0`
3. Title: `flaqes v0.1.0 - Initial Alpha Release`
4. Description: Use content from RELEASE_SUMMARY.md
5. Attach `dist/*` files
6. Mark as "pre-release" (it's alpha)
7. Publish release

### 7. Update Documentation

After release, update README.md badge section with:

```markdown
[![PyPI version](https://badge.fury.io/py/flaqes.svg)](https://badge.fury.io/py/flaqes)
[![Python versions](https://img.shields.io/pypi/pyversions/flaqes.svg)](https://pypi.org/project/flaqes/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
```

## Post-Release

- [ ] Announce on social media/relevant communities
- [ ] Update project STATUS.md
- [ ] Plan next iteration features
- [ ] Monitor PyPI download statistics
- [ ] Address any user feedback/issues

## Troubleshooting

### Build Fails
```bash
# Ensure build tools are installed
pip install --upgrade build twine

# Check pyproject.toml for syntax errors
```

### Upload Fails
```bash
# Ensure you have a PyPI account and API token
# Create token at: https://pypi.org/manage/account/token/

# Store in ~/.pypirc:
[pypi]
username = __token__
password = pypi-<your-token>
```

### Import Errors After Install
```bash
# Make sure package structure is correct
# Check that flaqes/ directory contains __init__.py
# Verify all imports use `flaqes.` prefix
```

## Quick Reference

```bash
# Complete release in one go (after testing)
rm -rf dist/ build/
python -m build
twine check dist/*
twine upload dist/*
git tag -a v0.1.0 -m "v0.1.0"
git push origin v0.1.0
```

---

**Ready for release!** 🚀

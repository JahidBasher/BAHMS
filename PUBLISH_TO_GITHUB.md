# Publish this repository to GitHub

This directory contains the **BAHMS reusable installer**, not any research project's private memory.

On macOS, install the GitHub CLI if necessary:

```bash
brew install gh
```

From the directory containing `install_bahms.py`:

```bash
gh auth login
git init -b main
git add README.md INSTALLATION.md UNINSTALL.md SECURITY.md PUBLISH_TO_GITHUB.md .gitignore install_bahms.py runtime/ tests/ .github/
git diff --cached --stat
git diff --cached --check
git commit -m "Initial BAHMS reusable project add-on"
gh repo create bahms --private --source=. --remote=origin --push
```

If the repository already exists in your GitHub account, use `git remote add origin https://github.com/YOUR_USERNAME/bahms.git` followed by `git push -u origin main` instead of `gh repo create`.

If `git init` reports an existing repository, do not recreate or overwrite its configuration; inspect `git status` and `git remote -v` first.

Before publishing research projects with BAHMS installed, confirm `.bahms/data/`, `.bahms/shared/`, and `.bahms/export/` are ignored and not already tracked.

The GitHub Actions workflow runs the unit tests on pushes and pull requests.

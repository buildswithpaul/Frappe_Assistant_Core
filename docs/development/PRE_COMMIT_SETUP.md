# Pre-commit Setup Guide

A one-time setup that runs the **same linters GitHub Actions runs** on your machine, before you push. No more round-trips waiting for CI to tell you your commit message is wrong or your imports aren't sorted.

## Why Use Pre-commit?

Stop CI failures before they happen. Every check in this project's `.github/workflows/linter.yml` and `commitlint.yml` is mirrored locally via [.pre-commit-config.yaml](../../.pre-commit-config.yaml) — so if your commit goes through locally, it will pass CI.

## What Gets Checked

| Check | Stage | Mirrors CI workflow |
|---|---|---|
| `trailing-whitespace`, `check-ast`, `check-json`, `check-toml`, `check-yaml`, `check-merge-conflict`, `debug-statements` | pre-commit | `linter.yml` |
| **ruff** — import sort, lint, format | pre-commit | `linter.yml` |
| **Frappe semgrep rules** (`frappe/semgrep-rules` + `r/python.lang.correctness`) | pre-commit | `linter.yml` |
| **commitlint** (conventional commits, angular preset) | commit-msg | `commitlint.yml` |
| **pip-audit** (known-vuln deps) | manual (opt-in) | `linter.yml` — *Vulnerable Dependency Check* |

## Quick Setup

### 1. Install pre-commit

```bash
pip install pre-commit
```

### 2. Install the hooks in your clone

From the app root (`apps/frappe_assistant_core`):

```bash
pre-commit install                          # pre-commit stage (ruff, semgrep, etc.)
pre-commit install --hook-type commit-msg   # commit-msg stage (commitlint)
```

**Both commands are required.** `pre-commit install` alone will not wire up commitlint — it only installs the `pre-commit` stage. Without the second command your commit messages will not be validated locally and will fail CI instead.

### 3. Install Node deps (for commitlint)

The `alessandrojcm/commitlint-pre-commit-hook` manages its own Node runtime, so you don't normally need Node installed locally. But if you want to run `npx commitlint` manually or match the exact CI environment:

```bash
npm install
```

This pulls the versions pinned in [package.json](../../package.json) — same versions CI installs in `commitlint.yml`.

### 4. (Optional) Migrate config if you see warnings

```bash
pre-commit migrate-config
```

## Daily Usage

### Normal workflow — hooks run automatically

```bash
git add .
git commit -m "feat: add new tool"
# ↑ pre-commit runs ruff, semgrep, etc.
# ↑ commit-msg runs commitlint
```

If anything fails, the commit is aborted. Fix the issues, re-stage, commit again.

### Run all checks manually before pushing

```bash
# Run every pre-commit hook on your changed files
pre-commit run

# Or run against the whole repo
pre-commit run --all-files
```

### Run a specific hook

```bash
pre-commit run ruff --all-files
pre-commit run frappe-semgrep --all-files
```

### Run the opt-in pip-audit check

This one is on the `manual` stage — it's not run automatically because it hits PyPI and is slow. Run it before pushing dependency changes:

```bash
pre-commit run pip-audit --hook-stage manual
```

## Commit Message Format

commitlint enforces [conventional commits](https://www.conventionalcommits.org/) (angular preset). Format:

```
<type>(<optional-scope>): <subject>
```

**Valid types:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.

**Subject rules:** lowercase, no trailing period, imperative mood ("add" not "added").

### Examples

```
feat: add OCR extraction tool
fix(audit): stop logging false-positive successes
docs: clarify pre-commit setup steps
refactor(tools): extract shared permission check
chore(deps): bump semgrep to 1.159.0
```

Bad messages commitlint will reject:

```
Added new feature              ← no type prefix
feat: Added new feature.       ← uppercase subject, trailing period
FIX: bug                       ← uppercase type
```

See [commitlint.config.js](../../commitlint.config.js) for the exact config and the handful of grandfathered historical commits.

## Troubleshooting

### "isort / ruff failed"

ruff auto-fixes most issues. Re-stage and commit again:

```bash
git add .
git commit -m "feat: your message"
```

### "semgrep failed"

Read the message carefully — it names the rule. The Frappe rule catalog explains each one at <https://github.com/frappe/semgrep-rules>. The 7 rules most likely to bite you are documented in this project's CLAUDE.md under `feedback_frappe_semgrep_rules`.

### "commitlint failed"

Your commit message doesn't match the conventional format. Rewrite it:

```bash
git commit --amend -m "feat: the correct message"
```

Then commit again. `git commit --amend` will re-run the commit-msg hook.

### "pip-audit found vulnerabilities"

Upgrade the flagged dependency in [pyproject.toml](../../pyproject.toml), or if no fix is available, document the exception and flag it in the PR.

### Emergency bypass (avoid)

```bash
git commit --no-verify -m "..."
```

**Only use this for genuine emergencies** — CI will still run the same checks, so skipping locally just means finding out on GitHub. Do not push `--no-verify`'d commits without a followup fix.

## Keeping Hooks Up to Date

Pre-commit auto-updates hook versions weekly via the `ci:` block in [.pre-commit-config.yaml](../../.pre-commit-config.yaml). To update manually:

```bash
pre-commit autoupdate
```

The Frappe semgrep rules themselves refresh on their own cadence — [scripts/run_frappe_semgrep.sh](../../scripts/run_frappe_semgrep.sh) pulls a fresh copy if the local cache is older than 7 days.

## Related Docs

- [Contributing.md](../../Contributing.md) — contribution workflow
- [DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md) — local dev environment
- [RELEASE_GUIDE.md](RELEASE_GUIDE.md) — how releases consume conventional-commit history

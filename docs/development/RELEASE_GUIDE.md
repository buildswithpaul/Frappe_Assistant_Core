# Release & Branching Guide

## Branching Strategy

```
main          ← production-ready, auto-releases on merge
develop       ← integration branch, all PRs target here
feature/*     ← new features
bug/*         ← bug fixes
improvement/* ← refactors/enhancements
hotfix/*      ← urgent production fixes → PR to main
```

## Branch Naming

| Type | Pattern | Example | PR Target |
|------|---------|---------|-----------|
| Feature | `feature/<short-description>` | `feature/tool_management_system` | `develop` |
| Bug fix | `bug/<issue#>-<short-description>` | `bug/109-auth-credential-leak` | `develop` |
| Improvement | `improvement/<short-description>` | `improvement/ocr_extraction` | `develop` |
| Hotfix | `hotfix/<short-description>` | `hotfix/make-paddleocr-optional` | `main` |

## Conventional Commits (Required)

All commit messages must follow the [Conventional Commits](https://www.conventionalcommits.org/) format. This is enforced by CI on all PRs.

```
<type>: <description>

[optional body]
```

| Prefix | Version Bump | Example |
|--------|-------------|---------|
| `feat:` | MINOR (2.3.2 -> 2.4.0) | `feat: add PDF table extraction tool` |
| `fix:` | PATCH (2.3.2 -> 2.3.3) | `fix: prevent OCR crash on empty file` |
| `perf:` | PATCH | `perf: cache plugin registry lookups` |
| `revert:` | PATCH | `revert: back out tool annotation hints` |
| `feat!:` | MAJOR (2.3.2 -> 3.0.0) | `feat!: remove STDIO bridge support` |
| `refactor:` | No release | `refactor: extract auth logic to mixin` |
| `docs:` | No release | `docs: update OAuth setup guide` |
| `chore:` | No release | `chore: update dev dependencies` |
| `ci:` | No release | `ci: add Python 3.14 to test matrix` |
| `test:` | No release | `test: add plugin toggle tests` |
| `style:` | No release | `style: fix import order` |

`.releaserc` uses the `angular` preset, under which **only `feat`, `fix`, `perf`, `revert`, and breaking changes cut a release.** Everything else lands in `develop` and ships with the next release that contains one of those, contributing nothing to the version number.

## Release Flow (Automated)

Releases are fully automated via `semantic-release` (same toolchain as Frappe and ERPNext).

1. Merge feature/bug/improvement PRs into `develop`
2. Write the change log file (see "Change Log Files" section below)
3. Raise a PR from `develop` to `main` and **rebase-merge** it — `main` requires linear history, and the merge method has consequences; see "Merging develop into main" below
4. **Automatic**: semantic-release runs on push to `main` and:
   - Detects version bump from commit messages
   - Updates `pyproject.toml` and `frappe_assistant_core/__init__.py`
   - Commits, tags, and pushes
   - Creates GitHub Release with auto-generated notes
5. Reset `develop` to `main` — **not** `git merge main`, which duplicates history. See "Merging develop into main" below.

No manual version bumping, tagging, or release creation needed. Do **not** hand-edit
`__version__` or `pyproject.toml`; `.releaserc` rewrites both with `sed` and commits
them as `chore(release): vX.Y.Z`, so a hand-set value is overwritten.

## Merging develop into main

`main` has **Require linear history** enabled, so a merge commit is rejected outright —
the release PR can only be rebase-merged or squash-merged. Both rewrite SHAs, and that
is the fact the rest of this section follows from.

**Use rebase-and-merge, then reset `develop` to `main`. Never merge `main` back into
`develop`.**

```bash
# 1. release
gh pr create --base main --head develop --title "fix: <summary of the release>"
gh pr merge --rebase              # semantic-release then tags and commits chore(release)

# 2. reconcile — replaces step 5 of the release flow
git checkout develop
git fetch origin
git reset --hard origin/main
git push --force-with-lease
```

Rebase-and-merge is preferred over squash because it keeps one commit per change on
`main`, which is what gives the GitHub release its per-change notes. A squash collapses
the whole release to a single line.

### Why the reset, and not `git merge main`

Rebase rewrites every commit's SHA. Merging those rewritten commits back into `develop`,
which still holds the originals, leaves `develop` carrying two copies of every released
change — permanently:

```
main:     d07f696  fix: prevent list_documents permission leak   <- released
develop:  9c83374  fix: prevent list_documents permission leak   <- original
          d07f696  fix: prevent list_documents permission leak   <- rebased copy, merged back
```

semantic-release reads `git log <last-tag>..HEAD`. The tag sits on the rebased copy, so
the originals are *not* ancestors of it — the next release makes them reachable again and
analyzes them a second time. If any is a `feat:`, the version bumps a minor it should not,
and the notes re-list changes that already shipped. That is exactly what happened between
2.5.0 and 2.5.1: `git log main..develop` reported 24 commits when only 11 were new, and
an already-released `feat:` would have produced 2.6.0 instead of 2.5.1.

The reset avoids it because at the moment of release the two branches hold the same tree
apart from the version files semantic-release just bumped — so `reset --hard origin/main`
discards no work and leaves `develop` an exact continuation of `main`. The next release
then starts from a clean `git log <tag>..develop`.

It does force-push a shared branch, so anyone with an open branch off `develop` needs to
rebase onto the new `develop` afterwards. Worth a heads-up in the release announcement.

### Commit subjects are the release notes

Every commit that reaches `main` came from a PR squash-merged into `develop`, and GitHub
composes that squash subject from the **PR title**. Commit Lint does not check it — it
validates the commits *inside* a PR, not the subject produced at merge time. A
non-conventional PR title therefore yields a commit that contributes nothing to the
version and appears nowhere in the release notes.

Two 2.5.1 changes were lost this way — `Fix/run python code…` (#237) and
`Security/fac skill…` (#238), the second a security fix. Title PRs into `develop` as
though the title were the commit message, because it becomes one:

```
fix: apply return_variables as a filter in run_python_code
```

## Change Log Files

Frappe reads `frappe_assistant_core/change_log/v2/vX_Y_Z.md` files to show the "What's New" dialog in the UI after users upgrade. These are written manually before merging to main (same as Frappe and ERPNext).

**File path**: `frappe_assistant_core/change_log/v{major}/v{major}_{minor}_{patch}.md`

**Format**:
```markdown
## Version X.Y.Z

### Features
- **Feature name** — short description

### Fixes
- **Fix name** — short description

### Improvements
- **Improvement name** — short description
```

For hotfixes, include the change log file in the hotfix branch before merging to main.

## Hotfix Flow

For urgent fixes that can't wait for the next release:

1. Branch from `main`: `git checkout -b hotfix/fix-description main`
2. Fix and commit using conventional format: `fix: description`
3. Raise PR targeting `main` (not `develop`)
4. After merge: semantic-release auto-creates the patch release
5. Merge `main` back into `develop`: `git checkout develop && git merge main`

## CI Pipeline

| Workflow | Trigger | What it does |
|----------|---------|-------------|
| CI (`ci.yml`) | Push to `main`, PRs | Full test suite on Frappe v15 (Python 3.12) AND v16 (Python 3.14) |
| Linters (`linter.yml`) | PRs | Pre-commit hooks + Frappe semgrep rules + pip-audit |
| Commit Lint (`commitlint.yml`) | PRs | Validates conventional commit format |
| Release (`release.yml`) | Push to `main` | Semantic-release: auto-version, tag, GitHub Release |
| Stale (`stale.yml`) | Daily | Auto-closes issues after 30+7 days of inactivity |
| Welcome (`welcome.yml`) | First issue/PR | Greets first-time contributors |

## Auto-Generated Release Notes

The release body is generated by `@semantic-release/release-notes-generator` from
**commit subjects**, grouped by conventional-commit type. Anything without a recognised
prefix is omitted entirely — see "Merging develop into main" above.

`.github/release.yml` below is a *separate* mechanism: it groups merged PRs by label and
applies only to GitHub's own "Generate release notes" button, which this flow does not
use. Labels are still worth setting — they organise the notes if someone regenerates them
by hand — but they do not affect what semantic-release publishes.

`.github/release.yml` groups merged PRs by label:

| Category | Labels |
|----------|--------|
| New Features | `feature`, `enhancement` |
| Security | `security` |
| Bug Fixes | `bug`, `fix` |
| Improvements | `improvement`, `refactor`, `performance` |
| Documentation | `documentation`, `docs` |
| Other Changes | everything else |

PRs with `skip-changelog` label are excluded from release notes.

Label your PRs before merging so auto-generated notes are organized correctly.

## PR Checklist

- [ ] Commit messages follow conventional commit format
- [ ] Target `develop` branch (or `main` for hotfixes)
- [ ] Code passes linters: `pre-commit run --all-files`
- [ ] Tests pass: `bench --site <site> run-tests --app frappe_assistant_core`
- [ ] Run `bench migrate` if adding/modifying DocTypes
- [ ] Add migration patch for settings changes (never use `after_migrate`)
- [ ] PR title is a valid conventional-commit subject — it becomes the squash commit, and Commit Lint does not check it

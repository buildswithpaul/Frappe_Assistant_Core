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
| `refactor:` | PATCH | `refactor: extract auth logic to mixin` |
| `feat!:` | MAJOR (2.3.2 -> 3.0.0) | `feat!: remove STDIO bridge support` |
| `docs:` | No release | `docs: update OAuth setup guide` |
| `chore:` | No release | `chore: update dev dependencies` |
| `ci:` | No release | `ci: add Python 3.14 to test matrix` |
| `test:` | No release | `test: add plugin toggle tests` |
| `style:` | No release | `style: fix import order` |

## Release Flow (Automated)

Releases are fully automated via `semantic-release` (same toolchain as Frappe and ERPNext).

1. Merge feature/bug/improvement PRs into `develop`
2. When ready to release: merge `develop` into `main` (via PR or direct merge)
3. **Automatic**: semantic-release runs on push to `main` and:
   - Detects version bump from commit messages
   - Updates `pyproject.toml` and `frappe_assistant_core/__init__.py`
   - Commits, tags, and pushes
   - Creates GitHub Release with auto-generated notes
4. Merge `main` back into `develop`: `git checkout develop && git merge main`

No manual version bumping, tagging, or release creation needed.

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

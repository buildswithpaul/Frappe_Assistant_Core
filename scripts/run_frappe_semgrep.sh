#!/usr/bin/env bash
# Run semgrep with the same rule sources CI uses (.github/workflows/linter.yml):
#   - frappe/semgrep-rules (cloned into a cache dir, updated weekly)
#   - r/python.lang.correctness  (semgrep registry)
#
# Invoked from .pre-commit-config.yaml. Receives changed files as positional
# args from pre-commit; passes them through to semgrep.
set -euo pipefail

CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/frappe-semgrep-rules"
RULES_REPO="https://github.com/frappe/semgrep-rules.git"
STALE_AFTER_DAYS=7

# Clone on first run, refresh if older than STALE_AFTER_DAYS.
if [[ ! -d "$CACHE_DIR/.git" ]]; then
  echo "Cloning Frappe semgrep rules into $CACHE_DIR..." >&2
  git clone --depth 1 "$RULES_REPO" "$CACHE_DIR" >&2
elif [[ -n "$(find "$CACHE_DIR" -maxdepth 0 -mtime +$STALE_AFTER_DAYS 2>/dev/null)" ]]; then
  echo "Refreshing Frappe semgrep rules in $CACHE_DIR..." >&2
  git -C "$CACHE_DIR" pull --ff-only --quiet >&2 || true
  touch "$CACHE_DIR"
fi

# If pre-commit handed us no files (e.g. manual `pre-commit run`), fall back
# to scanning the whole repo so the dev still gets coverage.
if [[ "$#" -eq 0 ]]; then
  exec semgrep scan --error --quiet \
    --config "$CACHE_DIR/rules" \
    --config "r/python.lang.correctness"
fi

exec semgrep scan --error --quiet \
  --config "$CACHE_DIR/rules" \
  --config "r/python.lang.correctness" \
  "$@"

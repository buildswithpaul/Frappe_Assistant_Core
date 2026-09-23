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

# Drop anything .semgrepignore excludes. Semgrep applies that file only when
# it discovers targets itself; a path named on the command line is scanned
# regardless. Without this the hook reports findings that CI — which scans the
# whole repo — does not, and the two disagree about the same commit.
# Literal paths only, which is all .semgrepignore holds here.
IGNORED=()
if [[ -f .semgrepignore ]]; then
  while IFS= read -r line; do
    line="${line%%#*}"
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    [[ -n "$line" ]] && IGNORED+=("$line")
  done < .semgrepignore
fi

TARGETS=()
for target in "$@"; do
  skip=""
  for ignored in ${IGNORED+"${IGNORED[@]}"}; do
    [[ "$target" == "$ignored" ]] && skip=1 && break
  done
  [[ -z "$skip" ]] && TARGETS+=("$target")
done

# Every changed file was excluded — nothing left to scan.
[[ "${#TARGETS[@]}" -eq 0 ]] && exit 0

exec semgrep scan --error --quiet \
  --config "$CACHE_DIR/rules" \
  --config "r/python.lang.correctness" \
  "${TARGETS[@]}"

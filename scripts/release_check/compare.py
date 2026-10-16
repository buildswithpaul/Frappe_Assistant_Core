"""Compare two release-check results files; exit 1 when any question went correct -> incorrect.

python scripts/release_check/compare.py results/old.json results/new.json
"""

import json
import sys
from pathlib import Path

from scoring import regressions


def load_results(path: str) -> list:
    data = json.loads(Path(path).read_text())
    return data["results"] if isinstance(data, dict) else data


def verdict(old_row, new_row) -> str:
    if old_row is None:
        return "new"
    if new_row is None:
        return "REGRESSION (not asked)" if old_row["correct"] else "dropped"
    if old_row["correct"] and not new_row["correct"]:
        return "REGRESSION"
    if not old_row["correct"] and new_row["correct"]:
        return "fixed"
    return "same"


def mark(row, key) -> str:
    if row is None:
        return "-"
    value = row.get(key)
    return "yes" if value is True else "no" if value is False else "-" if value is None else str(value)


def print_table(old: list, new: list) -> None:
    old_by_id, new_by_id = {r["id"]: r for r in old}, {r["id"]: r for r in new}
    ids = list(dict.fromkeys([r["id"] for r in old] + [r["id"] for r in new]))
    width = max([len(i) for i in ids] + [8])
    print(f"{'question':<{width}}  old  new  cited(old>new)  secs(old>new)  result")
    for question_id in ids:
        o, n = old_by_id.get(question_id), new_by_id.get(question_id)
        seconds = ">".join(f"{r['wall_seconds']:.0f}" if r and "wall_seconds" in r else "-" for r in (o, n))
        cited = ">".join(mark(r, "cited") for r in (o, n))
        print(
            f"{question_id:<{width}}  {mark(o, 'correct'):<3}  {mark(n, 'correct'):<3}  "
            f"{cited:<14}  {seconds:<13}  {verdict(o, n)}"
        )


def main(argv: list) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    old, new = load_results(argv[1]), load_results(argv[2])
    print_table(old, new)
    regressed = regressions(old, new)
    if regressed:
        print(f"\n{len(regressed)} regression(s): {', '.join(regressed)}")
        return 1
    print("\nNo regressions.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

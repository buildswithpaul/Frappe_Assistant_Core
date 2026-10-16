"""Ask the release-check questions through FAC Chat with one fixed model and score the answers.

    python scripts/release_check/run.py --site realistic.test --profile realistic \\
        --url http://localhost:8000 --model <model_id> --out results/<version>.json

Questions go over HTTP to the site's real web workers (so the Socket.IO relay runs exactly as it does
for the SPA); expected answers are read in-process from --site, and (with --ar-site) AR Turn Usage from the FAC
Cloud site, so the script needs the bench Python and `sites/` as the working directory. Credentials come from the environment:
RELEASE_CHECK_API_KEY and RELEASE_CHECK_API_SECRET (a user's API key and secret).

--dry-run lists what would be asked and connects to nothing.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from scoring import citation_text, is_cited, is_non_answer, score_mentions, score_top_n, score_total

HERE = Path(__file__).resolve().parent
CLIENT_TYPE = "release_check"
BLOCKED_AFTER_SECONDS = 60
REPLY_TIMEOUT_SECONDS = 300
POLL_SECONDS = 2
USAGE_WAIT_SECONDS = 10
REQUEST_TIMEOUT_SECONDS = 30
API = "/api/method/frappe_assistant_core.chat.api."


def load_questions(profile: str) -> list:
    questions = json.loads((HERE / "questions.json").read_text())
    return [question for question in questions if question["site"] == profile]


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--site", help="Bench site name (required unless --dry-run)")
    parser.add_argument("--profile", required=True, choices=["realistic", "large"], help="Question set")
    parser.add_argument("--model", required=True, help="Model id, the same for every question")
    parser.add_argument("--out", required=True, help="Results file, e.g. results/3.2.0.json")
    parser.add_argument("--url", default="http://localhost:8000", help="Site URL the chat requests go to")
    parser.add_argument(
        "--ar-site",
        help="FAC Cloud (assistant_runtime) site on the same bench; its AR Turn Usage fills tool_calls, "
        "credits and input_tokens. Without it they are null.",
    )
    parser.add_argument("--sites-path", default=os.environ.get("FRAPPE_SITES_PATH"))
    parser.add_argument(
        "--timeout", type=int, default=REPLY_TIMEOUT_SECONDS, help="Seconds to wait per reply"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="List the questions, model and output; connect to nothing"
    )
    return parser.parse_args(argv)


def print_dry_run(args, questions: list) -> None:
    print(f"DRY RUN: nothing is asked, no site is contacted.\n  site: {args.site or '(not given)'}")
    print(
        f"  profile: {args.profile}\n  model: {args.model}\n  client_type: {CLIENT_TYPE}\n  out: {args.out}"
    )
    print(f"  ar_site: {args.ar_site or '(none: tool_calls, credits and input_tokens will be null)'}")
    print(f"  {len(questions)} question(s):")
    for question in questions:
        print(f"    {question['id']} [{question['expect']['kind']}]: {question['question']}")


def expected_for(question: dict):
    """Compute the expected answer in-process from the site's data (expected.py)."""
    import expected

    value = getattr(expected, question["expect"]["source"])()
    if question["expect"]["kind"] == "top_n":
        return [name for name, _ in value]
    return value


def correct_for(question: dict, answer: str, expected_value) -> bool:
    kind = question["expect"]["kind"]
    if kind == "total":
        return score_total(answer, expected_value)
    if kind == "top_n":
        return score_top_n(answer, expected_value)
    return score_mentions(answer, expected_value)


class ChatClient:
    """FAC Chat over HTTP with API-key auth (no CSRF token needed)."""

    def __init__(self, url: str, key: str, secret: str, timeout: int):
        import requests

        self.base, self.timeout = url.rstrip("/"), timeout
        self.http = requests.Session()
        self.http.headers["Authorization"] = f"token {key}:{secret}"

    def _call(self, method: str, name: str, **params):
        field = "data" if method == "POST" else "params"
        response = self.http.request(
            method, self.base + API + name, timeout=REQUEST_TIMEOUT_SECONDS, **{field: params}
        )
        response.raise_for_status()
        return response.json()["message"]

    def create_session(self) -> str:
        return self._call("POST", "create_session")["session_id"]

    def send(self, session_id: str, message: str, model_id: str) -> None:
        self._call(
            "POST",
            "send_message",
            session_id=session_id,
            message=message,
            model_id=model_id,
            client_type=CLIENT_TYPE,
        )

    def wait_for_reply(self, session_id: str):
        """Poll the history for the assistant reply; None on timeout.

        Returns a row with content, or one the turn ended without content (errored / aborted), so a
        failed turn is reported at once instead of after the whole timeout.
        """
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            messages = self._call("GET", "get_session_history", session_id=session_id)["messages"]
            replies = [m for m in messages if m["role"] == "assistant"]
            finished = [
                m for m in replies if (m.get("content") or "").strip() or m.get("errored") or m.get("aborted")
            ]
            if finished:
                return finished[-1]
            time.sleep(POLL_SECONDS)
        return None


def fetch_usage(session_ids: list) -> dict:
    """session_id -> tool_calls, credits, input_tokens summed over the turn's cycles, from AR Turn Usage.

    Runs on the FAC Cloud (assistant_runtime) site, where AR writes one row per cycle keyed by FAC's
    session_id. A session with no row (yet) is left out.
    """
    import frappe

    usage = {}
    deadline = time.monotonic() + USAGE_WAIT_SECONDS
    while True:
        # a new snapshot per read: the rows are written by another process after the reply
        frappe.db.rollback()
        rows = frappe.get_all(
            "AR Turn Usage",
            filters={"session_id": ["in", session_ids], "client_type": CLIENT_TYPE},
            fields=["session_id", "tool_calls", "credits", "tokens_input"],
        )
        usage = {}
        for row in rows:
            entry = usage.setdefault(row.session_id, {"tool_calls": 0, "credits": 0.0, "input_tokens": 0})
            entry["tool_calls"] += int(row.tool_calls or 0)
            entry["credits"] = round(entry["credits"] + float(row.credits or 0), 6)
            entry["input_tokens"] += int(row.tokens_input or 0)
        if len(usage) == len(session_ids) or time.monotonic() >= deadline:
            return usage
        time.sleep(POLL_SECONDS)


NO_USAGE = {"tool_calls": None, "credits": None, "input_tokens": None}


def ask(client: ChatClient, question: dict, model: str, expected_value) -> dict:
    """One question -> one result row. Any failure is recorded as `error`, never raised."""
    started = time.monotonic()
    row = {"id": question["id"], "session_id": None, "answer": "", "correct": False, "cited": False}
    reply, error = None, None
    try:
        row["session_id"] = client.create_session()
        client.send(row["session_id"], question["question"], model)
        reply = client.wait_for_reply(row["session_id"])
        if not is_non_answer(reply):
            row["answer"] = reply["content"]
            row["correct"] = correct_for(question, row["answer"], expected_value)
            row["cited"] = is_cited(citation_text(row["answer"], reply.get("tool_calls")), question["cite"])
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    wall = time.monotonic() - started
    row.update(NO_USAGE)
    row.update(
        {
            "wall_seconds": round(wall, 1),
            "blocked_over_60s": wall > BLOCKED_AFTER_SECONDS,
            "errored": bool(reply and reply.get("errored")),
            "aborted": bool(reply and reply.get("aborted")),
            "timed_out": error is None and reply is None,
            "error": error,
        }
    )
    return row


def write_results(args, results: list) -> None:
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "model": args.model,
        "site": args.site,
        "profile": args.profile,
        "client_type": CLIENT_TYPE,
        "ar_site": args.ar_site,
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "results": results,
    }
    out.write_text(json.dumps(document, indent=2) + "\n")


def connect(site: str, sites_path):
    import frappe
    from site_common import resolve_sites_path

    frappe.init(site, sites_path=resolve_sites_path(sites_path, site))
    frappe.connect()
    return frappe


def main(argv=None) -> int:
    args = parse_args(argv)
    questions = load_questions(args.profile)
    if args.dry_run:
        print_dry_run(args, questions)
        return 0
    key, secret = os.environ.get("RELEASE_CHECK_API_KEY"), os.environ.get("RELEASE_CHECK_API_SECRET")
    if not (args.site and key and secret):
        raise SystemExit(
            "--site, RELEASE_CHECK_API_KEY and RELEASE_CHECK_API_SECRET are required unless --dry-run"
        )

    # phase 1: expected answers, read from the site's own data (the script never writes)
    frappe = connect(args.site, args.sites_path)
    try:
        expected_values = {question["id"]: expected_for(question) for question in questions}
    finally:
        frappe.destroy()

    # phase 2: ask over HTTP; the file is rewritten after every question so a late failure keeps the rest
    client = ChatClient(args.url, key, secret, args.timeout)
    results = []
    for question in questions:
        print(f"asking {question['id']} ...", flush=True)
        results.append(ask(client, question, args.model, expected_values[question["id"]]))
        row = results[-1]
        print(f"  correct={row['correct']} cited={row['cited']} {row['wall_seconds']}s error={row['error']}")
        write_results(args, results)

    # phase 3: usage from the FAC Cloud site, when given
    if args.ar_site:
        frappe = connect(args.ar_site, args.sites_path)
        try:
            usage = fetch_usage([r["session_id"] for r in results if r["session_id"]])
        finally:
            frappe.destroy()
        for row in results:
            row.update(usage.get(row["session_id"], NO_USAGE))
        write_results(args, results)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

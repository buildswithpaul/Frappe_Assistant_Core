# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Check that the web server can carry FACO.

A chat holds its web request open for the whole stream. Under gunicorn's default sync
workers every chat occupies a whole worker, so a handful of people chatting starves the
rest of the site. This reads the flags the running gunicorn master was started with and
compares the request slots it gives against the number of people expected to chat at once.
"""

import os

import frappe
import psutil
from frappe import _

RECOMMENDED_FIX = "--worker-class gthread --threads 8"
DEFAULT_EXPECTED_CHATTERS = 10

# Each chat needs one slot for its stream and one for the rest of that person's requests.
SLOTS_PER_CHATTER = 2

_GUNICORN_DEFAULTS = {"worker_class": "sync", "workers": 1, "threads": 1, "timeout": 30}
_OPTION_NAMES = {
    "-w": "workers",
    "--workers": "workers",
    "--threads": "threads",
    "-k": "worker_class",
    "--worker-class": "worker_class",
    "-t": "timeout",
    "--timeout": "timeout",
    "--graceful-timeout": "graceful_timeout",
}
_INT_OPTIONS = {"workers", "threads", "timeout", "graceful_timeout"}


def _is_gunicorn(argv: list[str]) -> bool:
    return any(os.path.basename(arg) == "gunicorn" for arg in argv[:3])


def _option_values(argv: list[str]) -> dict:
    found = {}
    index = 0
    while index < len(argv):
        arg = argv[index]
        name, has_value, value = arg.partition("=")
        key = _OPTION_NAMES.get(name)
        if key and not has_value and index + 1 < len(argv):
            value = argv[index + 1]
            index += 1
            has_value = True
        if key and has_value:
            try:
                found[key] = int(value) if key in _INT_OPTIONS else value
            except ValueError:
                pass
        index += 1
    return found


def parse_gunicorn_cmdline(argv: list[str]) -> dict | None:
    """Return the worker settings in a gunicorn command line, or None if it is not gunicorn."""
    if not _is_gunicorn(argv):
        return None
    parsed = {**_GUNICORN_DEFAULTS, **_option_values(argv)}
    # gunicorn's own rule: threads > 1 turns the sync class into gthread.
    if parsed["worker_class"] == "sync" and parsed["threads"] > 1:
        parsed["worker_class"] = "gthread"
    return parsed


def read_web_server_config() -> dict:
    """Read how the web server running this request was started."""
    config = {"worker_class": None, "workers": None, "threads": None, "timeout": None}
    try:
        parsed = parse_gunicorn_cmdline(psutil.Process(os.getppid()).cmdline())
    except (psutil.Error, OSError):
        parsed = None
    if parsed:
        return {
            **config,
            **{key: parsed[key] for key in config},
            "source": "gunicorn",
        }

    workers = frappe.conf.get("gunicorn_workers")
    timeout = frappe.conf.get("http_timeout")
    if workers or timeout:
        return {**config, "workers": workers, "timeout": timeout, "source": "conf"}
    return {**config, "source": "unknown"}


def assess(config: dict, expected_chatters: int) -> dict:
    """Judge whether the web server config can carry `expected_chatters` people chatting at once."""
    required_slots = SLOTS_PER_CHATTER * expected_chatters
    result = {
        "status": "unknown",
        "slots": None,
        "required_slots": required_slots,
        "reasons": [],
        "fix": None,
    }
    worker_class = config.get("worker_class")
    workers, threads = config.get("workers"), config.get("threads")
    if config.get("source") != "gunicorn" or not (worker_class and workers and threads):
        return result

    result["slots"] = workers * threads
    if worker_class == "sync":
        result["reasons"].append(
            _(
                "Web server uses sync workers, so each chat holds a whole worker. Run gunicorn with {0}."
            ).format(RECOMMENDED_FIX)
        )
    elif result["slots"] < required_slots:
        result["reasons"].append(
            _(
                "Web server has {0} request slots; FACO needs at least {1} for {2} people chatting at once. Run gunicorn with {3}."
            ).format(result["slots"], required_slots, expected_chatters, RECOMMENDED_FIX)
        )

    result["status"] = "warning" if result["reasons"] else "ok"
    result["fix"] = RECOMMENDED_FIX if result["reasons"] else None
    return result


def get_expected_chatters() -> int:
    configured = frappe.db.get_single_value("FAC Chat Settings", "expected_concurrent_chatters")
    return int(configured or DEFAULT_EXPECTED_CHATTERS)


def server_setup_report() -> dict:
    config = read_web_server_config()
    return {**config, **assess(config, get_expected_chatters())}


@frappe.whitelist(methods=["GET"])
def get_server_setup() -> dict:
    """The web server's worker setup and whether it can carry FACO."""
    frappe.only_for("System Manager")
    return server_setup_report()

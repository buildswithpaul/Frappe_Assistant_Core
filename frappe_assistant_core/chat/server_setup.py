# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Check that the web server can carry FACO.

The browser's chat request returns at once and a relay thread holds the stream, but a turn
still brings a stream of short requests: the chat's own polling, AR's MCP callbacks into the
site, and the person's page loads. Gunicorn's default sync workers serve one request at a time,
so those queue behind each other. This reads the flags the running gunicorn master was started
with (GUNICORN_CMD_ARGS included) and compares the request slots they give against the number of
people expected to chat at once. A config file (-c) can set anything, so it reads as unknown;
async classes (gevent, eventlet, uvicorn) have no slot limit to judge and read as ok.
"""

import os
import shlex

import frappe
import psutil
from frappe import _

RECOMMENDED_FIX = "--worker-class gthread --threads 8"
DEFAULT_EXPECTED_CHATTERS = 10

# Each chat needs one slot for AR's MCP callbacks and one for the rest of that person's requests.
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
    "-c": "config",
    "--config": "config",
}
_INT_OPTIONS = {"workers", "threads", "timeout", "graceful_timeout"}
# The classes whose request capacity is workers x threads. Others (gevent, eventlet, uvicorn)
# multiplex connections inside a worker, so slots cannot be judged from these flags.
_THREAD_BOUND_CLASSES = {"sync", "gthread"}


def _is_gunicorn(argv: list[str]) -> bool:
    return any(os.path.basename(arg) == "gunicorn" for arg in argv[:3])


def _split_option(arg: str) -> tuple[str, str | None]:
    """Split `--opt=v`, `-w4` and `-k=v` into (option, attached value)."""
    if arg.startswith("--"):
        name, has_value, value = arg.partition("=")
        return name, value if has_value else None
    if arg.startswith("-") and len(arg) > 2:
        return arg[:2], arg[2:].lstrip("=")
    return arg, None


def _option_values(argv: list[str]) -> dict:
    found = {}
    index = 0
    while index < len(argv):
        name, value = _split_option(argv[index])
        key = _OPTION_NAMES.get(name)
        if key and value is None and index + 1 < len(argv):
            index += 1
            value = argv[index]
        if key and value is not None:
            try:
                found[key] = int(value) if key in _INT_OPTIONS else value
            except ValueError:
                pass
        index += 1
    return found


def parse_gunicorn_cmdline(argv: list[str], env_args: str | None = None) -> dict | None:
    """Return the worker settings of a gunicorn master, or None if `argv` is not gunicorn.

    `env_args` is the master's GUNICORN_CMD_ARGS; gunicorn applies it under the command line.
    A config file may set anything not given as a flag, so with one present the missing
    values are None rather than gunicorn's defaults.
    """
    if not _is_gunicorn(argv):
        return None
    found = {**_option_values(shlex.split(env_args or "")), **_option_values(argv)}
    defaults = {} if "config" in found else _GUNICORN_DEFAULTS
    parsed = {key: found.get(key, defaults.get(key)) for key in _GUNICORN_DEFAULTS}
    # gunicorn's own rule: threads > 1 turns the sync class into gthread.
    if parsed["worker_class"] == "sync" and (parsed["threads"] or 1) > 1:
        parsed["worker_class"] = "gthread"
    return parsed


def _master_environ_args(process: psutil.Process) -> str | None:
    try:
        return process.environ().get("GUNICORN_CMD_ARGS")
    except (psutil.Error, OSError):
        return None


def read_web_server_config() -> dict:
    """Read how the web server running this request was started."""
    config = {"worker_class": None, "workers": None, "threads": None, "timeout": None}
    try:
        master = psutil.Process(os.getppid())
        parsed = parse_gunicorn_cmdline(master.cmdline(), _master_environ_args(master))
    except (psutil.Error, OSError):
        parsed = None
    if parsed:
        return {**config, **parsed, "source": "gunicorn"}

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
    if config.get("source") != "gunicorn" or not worker_class:
        return result
    if worker_class not in _THREAD_BOUND_CLASSES:
        result["status"] = "ok"
        return result
    if not (workers and threads):
        return result

    result["slots"] = workers * threads
    if worker_class == "sync":
        result["reasons"].append(
            _(
                "Web server uses sync workers, which serve one request at a time, so chat polling, MCP callbacks and page loads queue behind each other. Run gunicorn with {0}."
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

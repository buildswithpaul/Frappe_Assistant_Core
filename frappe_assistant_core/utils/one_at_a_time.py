# Copyright (C) 2025 Paul Clinton
# SPDX-License-Identifier: AGPL-3.0-or-later
"""One run at a time of a long write step (a chart add or replace, the masters an import creates).

FAC Cloud calls a tool again when its answer is slow to come (live, 2026-11-19): a chart replace of
108 s was started twice more while it ran, and the repeats failed with "Cannot delete ... as it has
child nodes", which is all the chat showed of a replace that had worked. While a step runs, a second
call of it says so and does nothing.
"""

from contextlib import contextmanager

import frappe
from frappe import _
from frappe.utils import now_datetime

# A run that dies without releasing (a killed worker) frees the step after this long.
LOCK_SECONDS = 15 * 60


class StillRunning(Exception):
    """The same step is running from an earlier call."""

    def result(self) -> dict:
        return {"success": False, "still_running": True, "error": str(self)}


def _lock_key(kind: str, key: str) -> str:
    return frappe.cache.make_key(f"fac_one_at_a_time:{kind}:{key}")


@contextmanager
def one_at_a_time(kind: str, key: str):
    """Run the block only when no other call runs ``kind`` for ``key``; raise StillRunning otherwise.
    The step is free again once this call's work is committed or rolled back."""
    lock = _lock_key(kind, key)
    started = now_datetime().strftime("%H:%M:%S")
    # the key is the site's own (make_key), and only a raw SET can take it when it is free (nx)
    if not frappe.cache.set(lock, started, nx=True, ex=LOCK_SECONDS):  # nosemgrep
        since = frappe.safe_decode(frappe.cache.get(lock) or b"") or _("a moment ago")  # nosemgrep
        raise StillRunning(
            _(
                "This step is still running from an earlier call (started {0}), so nothing was started "
                "again. Don't call it again and don't tell the user it failed: wait a minute, then check "
                "the result (call the same tool again once: when the earlier run has finished, it says "
                "what that run did)."
            ).format(since)
        )

    def release():
        frappe.cache.delete(lock)

    if frappe.flags.in_test:
        # tests never commit: free the step at once
        try:
            yield
        finally:
            release()
        return
    try:
        yield
    except BaseException:
        release()
        raise
    frappe.db.after_commit.add(release)
    frappe.db.after_rollback.add(release)

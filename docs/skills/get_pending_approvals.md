# How to Use get_pending_approvals

## Overview

The `get_pending_approvals` tool lists open Workflow Actions addressed to the current user, by permitted role or directly by user. Use it for approval queues, not for ToDos or Notifications.

Results are limited to documents the user can open. A document hidden from the user by a User Permission does not appear and is not counted, so `total_pending` reflects only what the user may see.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `doctype` | string | No | Only this DocType (e.g. `Purchase Order`) |
| `limit` | integer | No | Maximum pending actions to return (default 50, max 200) |
| `include_actions` | boolean | No | Include available actions (Approve, Reject, ...) per document (default true) |

## Best Practices

1. **Act with `run_workflow`** — use the returned `available_actions` names exactly.
2. **Filter by `doctype`** on large queues, and set `include_actions` to false for speed.
3. **Treat the list as the user's view** — hidden documents are skipped before the limit is applied, up to a scan cap of 1000 actions, so very large queues of hidden items can return fewer than `limit` rows.

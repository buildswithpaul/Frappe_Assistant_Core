# How to Use get_pending_approvals

## Overview

The `get_pending_approvals` tool lists open Workflow Actions addressed to the current user, by permitted role or directly by user. Use it for approval queues, not for ToDos or Notifications.

Results are limited to documents the user can open. A document hidden from the user by a User Permission does not appear and is not counted, so `total_pending` reflects only what the user may see.

A document whose only step left is a cancel (for example an approved, submitted Purchase Order) is not pending approval, so it is skipped even though Frappe keeps its Workflow Action open. Each document appears once.

`total_pending` counts every pending document, up to 200, and matches the count on the FAC Chat home page. When it is larger than `limit`, the result also carries `listed`: report the total, and say you are showing the newest `listed`.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `doctype` | string | No | Only this DocType (e.g. `Purchase Order`) |
| `limit` | integer | No | Maximum documents to list (default 50, max 200); `total_pending` still counts up to 200 |
| `include_actions` | boolean | No | Include available actions (Approve, Reject, ...) per document (default true) |

## Best Practices

1. **Act with `run_workflow`** — use the returned `available_actions` names exactly.
2. **Filter by `doctype`** on large queues, and set `include_actions` to false for speed.
3. **Treat the list as the user's view** — hidden documents are skipped before the limit is applied, up to a scan cap of 1000 actions, so very large queues of hidden items can return fewer than `limit` rows.

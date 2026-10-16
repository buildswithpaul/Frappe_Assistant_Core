# How to Use add_crm_activity

## Overview

Adds a note, a follow-up task or a call log to a Frappe CRM lead or deal, linked so it shows on the
record's Notes, Tasks or Calls tab — what CRM's own "New note / task / call" dialogs create.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `doctype` | string | **Yes** | `CRM Lead` or `CRM Deal` |
| `name` | string | **Yes** | The record name |
| `kind` | string | **Yes** | `note`, `task` or `call` |
| `title` | string | note, task | Note or task title |
| `content` | string | No | Note text, task description, or what the call covered (saved as the call's note) |
| `due_date` | string | No | Task due, `YYYY-MM-DD HH:MM:SS` |
| `priority` | string | No | Task priority: Low, Medium (default), High |
| `assigned_to` | string | No | Task assignee; defaults to the user |
| `direction` | string | No | Call: Outgoing (default) or Incoming |
| `duration_seconds` | integer | No | Call length in seconds |
| `our_phone`, `their_phone` | string | No | Call numbers when the user's profile or the record has none |

## Response

`{"success": true, "kind", "created", "record", "link"}` or `{"success": false, "error"}`.

## Tips

- One call per thing the user asked: "log the call, add a note and a task" is three calls.
- A call log needs both phone numbers; when the tool says one is missing, ask the user for it.
- Never use `create_document` or a Desk `ToDo` for these.

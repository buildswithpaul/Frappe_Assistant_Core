# How to Use sandbox_reference

## Overview

The `sandbox_reference` tool lists the names a Server Script can use, read from the sandbox of this site's Frappe version, plus the rules scripts run under. It calls nothing and changes nothing. It needs the System Manager role.

Use it before writing a Server Script, instead of guessing which `frappe.*` functions exist. Frappe v15 and v16 differ, and the list comes from the version this site runs.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `prefix` | string | No | Only names under this dotted prefix, for example `frappe.db` |
| `limit` | integer | No | Most names to return. Default 200, maximum 500 |

## Reading the result

- `names`: sorted dotted names, for example `frappe.db.get_value`, including builtins such as `len` and `str`. A name in the list is available to the script; a name that is missing is not. Per-request data (`form_dict`, `args`, `response`, `session`, `request`) is listed by name only, never by its keys.
- `truncated`: `true` when more names matched than `limit`. Narrow with `prefix` or raise `limit`.
- `not_in_doctype_event`: the listed names that exist in the sandbox but are removed in DocType Event scripts (`frappe.db.commit`, `frappe.db.rollback`, `frappe.db.add_index`). Do not use them there.
- `rules`: what scripts may and may not do, such as SELECT-only `frappe.db.sql`, no `import`, and what each script type receives.

## Best Practices

1. **Look up before you write** — check each `frappe.*` call you plan to use against the list.
2. **Narrow with a prefix** — `frappe.db` or `frappe.utils` is faster to read than the full list.
3. **Build the script Disabled** — switch it on once it is ready, then read `recent_errors` for what it caused.

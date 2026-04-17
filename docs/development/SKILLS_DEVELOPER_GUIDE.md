# Skills — Developer Guide

This guide is for authors of Frappe apps who want to ship **skills** — markdown knowledge documents that Frappe Assistant Core surfaces to LLM clients as MCP Resources. If you want to teach the LLM how to use your app's tools or describe a multi-step workflow, a skill is the right vehicle.

If you're looking at how to **create tools** in your own Frappe app, see [EXTERNAL_APP_DEVELOPMENT.md](EXTERNAL_APP_DEVELOPMENT.md). If you want to create skills through the UI rather than shipping them with an app, see the [Skills User Guide](../guides/SKILLS_USER_GUIDE.md).

---

## What is a skill?

A skill is a markdown document that is exposed to MCP clients as a resource at `fac://skills/<skill-id>`. LLM clients (Claude Desktop, Claude Web, MCP Inspector, etc.) discover skills via the MCP `resources/list` call and fetch individual skill content via `resources/read`.

Two kinds of skills:

- **Tool Usage** — teaches the LLM how to use one specific MCP tool well. Linked to a tool name via the `linked_tool` field; when Assistant Core Settings is in `replace` mode the tool's description is shortened and the LLM is pointed at the skill URI.
- **Workflow** — describes a multi-step procedure that may involve several tools. Not linked to any single tool.

Skills are stored as `FAC Skill` DocType rows. When your app registers a skill through the hook described below, the row is marked `is_system=1` with `source_app=<your_app>` and becomes part of the app's lifecycle — re-synced on every `bench migrate` and removed when your app is uninstalled.

---

## The `assistant_skills` hook

Add an `assistant_skills` list to your app's `hooks.py`:

```python
# your_app/your_app/hooks.py

assistant_skills = [
    {
        "app": "your_app",
        "manifest": "data/assistant_skills.json",
        "content_dir": "data/skills",
    },
]
```

Each entry is a dict with three keys:

| Key | Required | Meaning |
|---|---|---|
| `app` | yes | Your app's module name. Used to scope skills for cleanup on uninstall. Must match the app name Frappe knows it by. |
| `manifest` | yes | Path to the manifest JSON file, **relative to your app's Python package directory**. Resolved internally via `frappe.get_app_path(app)`. |
| `content_dir` | no | Directory holding the markdown content files referenced in the manifest. Also relative to the app's package dir. Omit only if every manifest entry sets `content_file` to an empty string (rare). |

`bench migrate` processes every `assistant_skills` entry from every installed app. See [`_install_app_skills`](../../frappe_assistant_core/utils/migration_hooks.py) at `utils/migration_hooks.py:660-812`.

You can register multiple entries if you prefer to split your skills across several manifest files (for example one per feature area).

---

## The manifest JSON

The manifest is a flat JSON array of skill objects. Canonical example: [`frappe_assistant_core/data/system_skills.json`](../../frappe_assistant_core/data/system_skills.json).

```json
[
  {
    "skill_id": "list-documents-usage",
    "title": "How to Use list_documents",
    "description": "Searching and listing Frappe documents with filters, field selection, ordering, and response format",
    "skill_type": "Tool Usage",
    "linked_tool": "list_documents",
    "status": "Published",
    "visibility": "Public",
    "content_file": "list_documents.md"
  }
]
```

### Field reference

| Field | Required | Type | Default (hook-installed) | Notes |
|---|---|---|---|---|
| `skill_id` | yes | string | — | Must match `^[a-z0-9_-]+$`. Globally unique across all apps. Used as the MCP resource URI suffix (`fac://skills/<skill_id>`). |
| `title` | yes | string | — | Human-readable name shown in MCP clients. |
| `description` | yes | string | — | One-line description. Appears in `resources/list` and, under `replace` skill-mode, is the short description the LLM sees for the linked tool. Keep it under ~200 characters. |
| `content_file` | yes | string | — | Filename of the markdown content, relative to `content_dir`. If the file is missing the skill is **skipped with a warning** — it is never installed with empty content. |
| `skill_type` | no | `"Tool Usage"` \| `"Workflow"` | `"Workflow"` | **Note:** the hook-based default is Workflow, unlike the UI default which is Tool Usage. Set this explicitly in your manifest. |
| `linked_tool` | no | string | `null` | MCP tool name (e.g. `"list_documents"`). Required in practice for Tool Usage skills — used to wire up `replace` skill-mode. The DocType controller warns (does not error) if a Tool Usage skill has no `linked_tool`. |
| `status` | no | `"Draft"` \| `"Published"` \| `"Deprecated"` | `"Published"` | Only Published skills appear in `resources/list` for non-owners. |
| `visibility` | no | `"Public"` \| `"Shared"` \| `"Private"` | `"Public"` | Public + Published is visible to every user. `"Shared"` additionally requires a `shared_with_roles` table on the DocType — hook-installed skills cannot set this, so use Public for app-bundled skills that all users should see. |
| `category` | no | string | `null` | Link to a `Prompt Category` record name. Useful for grouping in the admin UI. |

**Fields set once and never overwritten on re-migrate:** `owner_user` (always `"Administrator"` for hook-installed skills) and `is_system` (always `1`). All other fields are re-synced from the manifest on every `bench migrate`, so evolving your metadata is safe.

---

## Markdown content conventions

The markdown content is the actual teaching material. It is what gets loaded into the LLM's context when the client fetches `resources/read`. It should be dense — every line should teach something the LLM couldn't guess from the tool's JSON schema.

Use the FAC-bundled skills as references: [`docs/skills/list_documents.md`](../skills/list_documents.md), [`docs/skills/create_document.md`](../skills/create_document.md), [`docs/skills/extract_file_content.md`](../skills/extract_file_content.md).

Recommended structure for a Tool Usage skill:

```markdown
# How to Use <tool_name>

## When to use this tool
One paragraph describing what the tool is for and when to prefer it over alternatives.

## Parameters

| Name | Type | Required | Description |
|---|---|---|---|
| ... | ... | ... | ... |

## Examples

### Example 1 — Common case
```json
{ ... }
```
Expected response:
```json
{ ... }
```

### Example 2 — Less obvious case
...

## Common pitfalls
- ...
- ...

## Related tools
- `other_tool` — when to reach for it instead
```

Target **under ~5 KB** per skill. Longer than that is a signal to split (e.g. split "how to filter" and "how to paginate" into two skills). Workflow skills can run longer when they describe a genuinely multi-step process.

---

## Worked example — `acme_billing` app

Suppose your app `acme_billing` exposes a tool `generate_invoice` via `assistant_tools` (see [EXTERNAL_APP_DEVELOPMENT.md](EXTERNAL_APP_DEVELOPMENT.md)), and you want to ship a usage skill for it.

### File layout

```
apps/acme_billing/
├── acme_billing/
│   ├── hooks.py
│   ├── data/
│   │   ├── assistant_skills.json
│   │   └── skills/
│   │       └── generate_invoice_usage.md
│   └── ...
└── pyproject.toml
```

### 1. `hooks.py`

```python
# acme_billing/hooks.py

app_name = "acme_billing"
app_title = "Acme Billing"
# ... other hooks ...

assistant_skills = [
    {
        "app": "acme_billing",
        "manifest": "data/assistant_skills.json",
        "content_dir": "data/skills",
    },
]
```

### 2. `acme_billing/data/assistant_skills.json`

```json
[
  {
    "skill_id": "acme-generate-invoice-usage",
    "title": "How to Use generate_invoice",
    "description": "Create an Acme invoice from a Sales Order, including line-item overrides, due dates, and currency handling",
    "skill_type": "Tool Usage",
    "linked_tool": "generate_invoice",
    "status": "Published",
    "visibility": "Public",
    "content_file": "generate_invoice_usage.md"
  }
]
```

Note the `acme-` prefix on `skill_id` — skill IDs are globally unique, so namespace yours to avoid collisions with other apps.

### 3. `acme_billing/data/skills/generate_invoice_usage.md`

```markdown
# How to Use generate_invoice

## When to use this tool
Use `generate_invoice` to produce an Acme invoice from an existing Sales Order. The
tool copies line items and currency from the order by default; pass `line_overrides`
only when you need to change quantities or discounts.

## Parameters

| Name | Type | Required | Description |
|---|---|---|---|
| `sales_order` | string | yes | Name of the Sales Order document. |
| `due_date` | string (YYYY-MM-DD) | no | Defaults to today + customer's payment terms. |
| `line_overrides` | list[dict] | no | Per-line `{item_code, qty, discount_pct}`. |

## Examples

### Straight copy from Sales Order
```json
{"sales_order": "SO-0042"}
```

### Early due date with a 10 % discount on one line
```json
{
  "sales_order": "SO-0042",
  "due_date": "2025-04-01",
  "line_overrides": [{"item_code": "WIDGET-A", "discount_pct": 10}]
}
```

## Common pitfalls
- The Sales Order must be Submitted (`docstatus=1`). Draft orders are rejected.
- `line_overrides` only accepts item codes that already exist on the order — it
  cannot add new lines. Use `update_document` on the invoice afterwards for that.
- Currency is inherited from the Sales Order and cannot be changed here.
```

### 4. Install

```bash
bench --site <your-site> migrate
```

Look for this line in the output:

```
App skills: 1 created, 0 updated, 0 removed
```

If the content file is missing, you'll see a warning instead and the skill will be skipped.

---

## Lifecycle

| Event | What happens |
|---|---|
| `bench migrate` (first time) | Creates `FAC Skill` row with `is_system=1`, `source_app="acme_billing"`, `owner_user="Administrator"`. |
| `bench migrate` (subsequent) | Re-syncs `title`, `description`, `status`, `visibility`, `skill_type`, `linked_tool`, `category`, `content` from the manifest. `owner_user` and `is_system` are preserved. |
| Skill removed from manifest | Row is deleted on the next `bench migrate`. Log: `Removed obsolete app skill: <skill_id> (from acme_billing)`. See [`migration_hooks.py:712-726`](../../frappe_assistant_core/utils/migration_hooks.py). |
| `bench uninstall-app acme_billing` | Every `FAC Skill` with `source_app="acme_billing"` is deleted via the `before_app_uninstall` hook. See [`migration_hooks.py:550-578`](../../frappe_assistant_core/utils/migration_hooks.py). |
| User tries to delete a system skill from the UI | Rejected. System skills can only be removed by the owning app. If the app has been uninstalled, the skill becomes orphaned and the UI allows deletion. See [`fac_skill.py:60-78`](../../frappe_assistant_core/assistant_core/doctype/fac_skill/fac_skill.py). |

---

## Testing your skills

After `bench migrate`, verify the skill is installed and reachable.

### Check the DocType directly

```bash
bench --site <your-site> console
```

```python
>>> import frappe
>>> frappe.get_all("FAC Skill", filters={"source_app": "acme_billing"},
...                fields=["skill_id", "title", "status", "is_system"])
[{'skill_id': 'acme-generate-invoice-usage',
  'title': 'How to Use generate_invoice',
  'status': 'Published',
  'is_system': 1}]
```

### Check the MCP `resources/list` call

```python
>>> from frappe_assistant_core.api.handlers.resources import handle_resources_list
>>> result = handle_resources_list()
>>> [r for r in result["resources"] if "acme" in r["uri"]]
[{'uri': 'fac://skills/acme-generate-invoice-usage',
  'name': 'How to Use generate_invoice',
  'description': 'Create an Acme invoice from a Sales Order, ...',
  'mimeType': 'text/markdown'}]
```

### Check a live client

In Claude Desktop (or MCP Inspector) the skill should appear in the resource list. Select it to see the markdown you shipped.

---

## Gotchas

- **Skill IDs** must match `^[a-z0-9_-]+$`. No uppercase, no dots, no slashes. Namespace yours with an app-specific prefix.
- **Paths in the manifest and `content_dir` are relative to the app's Python package directory.** `frappe.get_app_path("acme_billing")` returns `apps/acme_billing/acme_billing`, so `"manifest": "data/skills.json"` resolves to `apps/acme_billing/acme_billing/data/skills.json`. Absolute paths are not accepted.
- **Missing content files are skipped silently (with a warning in the migration log).** The skill row is not created. Check the log after migrate if you expect a skill and it isn't there.
- **System skills cannot be deleted from the UI** while the owning app is installed. Remove the entry from your manifest and run `bench migrate`, or uninstall the app.
- **Do not set `shared_with_roles` via the manifest** — the loader ignores it. If you need role-scoped visibility for an app-bundled skill, create it with `visibility: "Public"` and rely on the user's tool-access permissions instead, or let a System Manager edit the skill post-install to switch to Shared.
- **`status: "Draft"` in a manifest** is legal but unusual — the skill is installed but hidden from everyone except the `Administrator` user (the owner). Use it only for skills you're still iterating on.
- **`skill_type` default is `"Workflow"`** when installed via hook, not `"Tool Usage"`. Always set it explicitly for Tool Usage skills.

---

## Related documentation

- [Skills User Guide](../guides/SKILLS_USER_GUIDE.md) — creating skills through the FAC Admin UI
- [External App Tool Development](EXTERNAL_APP_DEVELOPMENT.md) — shipping MCP tools from your own app
- [Technical Documentation](../architecture/TECHNICAL_DOCUMENTATION.md) — `SkillManager`, caching, MCP bindings
- [Architecture](../architecture/ARCHITECTURE.md) — where the skills subsystem fits in the overall design

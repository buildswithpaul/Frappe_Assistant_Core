# Skills User Guide

**Skills** in Frappe Assistant Core (FAC) are markdown knowledge documents that teach the LLM how to use your tools and workflows effectively. This guide walks you through creating, publishing, and sharing skills through the FAC Admin UI.

If you want to ship skills **with your own Frappe app** (so they install automatically via `bench migrate`), see the [Skills Developer Guide](../development/SKILLS_DEVELOPER_GUIDE.md) instead.

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Creating a Skill](#creating-a-skill)
4. [Skill Types](#skill-types)
5. [Visibility and Sharing](#visibility-and-sharing)
6. [Publishing Workflow](#publishing-workflow)
7. [Linking to a Tool](#linking-to-a-tool)
8. [Skill Mode — Supplementary vs Replace](#skill-mode--supplementary-vs-replace)
9. [Best Practices](#best-practices)
10. [Analytics](#analytics)
11. [What NOT to Put in a Skill](#what-not-to-put-in-a-skill)

---

## Overview

A skill is a piece of markdown content that the LLM can fetch on demand via the MCP `resources/read` call. Unlike a tool description (which the LLM sees in every `tools/list` response), a skill is fetched only when the LLM decides it needs deeper guidance — so you can afford to put rich examples, pitfalls, and worked cases into it without blowing up token budgets on every request.

Skills come in two flavours:

| Type | Purpose | Linked to a tool? |
|---|---|---|
| **Tool Usage** | Teach the LLM how to use one specific MCP tool well. | Yes, via the `linked_tool` field. |
| **Workflow** | Describe a multi-step procedure that may span several tools. | No. |

Every skill gets a stable URI of the form `fac://skills/<skill-id>` and is discoverable via `resources/list`.

### Key concepts

| Concept | Description |
|---|---|
| **Skill ID** | URL-safe unique identifier, e.g. `sales-pipeline-review`. |
| **Content** | Markdown body — the actual teaching material. |
| **Status** | Draft, Published, or Deprecated. Only Published skills are visible to other users. |
| **Visibility** | Private, Shared (by role), or Public. |
| **Linked Tool** | MCP tool name — only meaningful for Tool Usage skills. |
| **Category** | Optional link to a Prompt Category for grouping. |

---

## Quick Start

1. Open **FAC Admin** at `/app/fac-admin` and switch to the **Skills** tab.
2. Click **New Skill**.
3. Fill in Skill ID, Title, Description, and Content (markdown).
4. Choose **Skill Type** (Tool Usage or Workflow) and, for Tool Usage, the **Linked Tool** name.
5. Set Status to **Published** when you're ready to share.
6. Choose **Visibility** — Public for everyone, Shared for specific roles, Private for just you.
7. Save.

The skill is now surfaced to MCP clients for every user permitted to see it.

---

## Creating a Skill

From the FAC Admin page (`/app/fac-admin`), the Skills tab shows a searchable, filterable list of every skill you can see. Search is by title or skill ID; filters narrow by **Skill Type** (Tool Usage / Workflow) and **Status** (Draft / Published / Deprecated).

Click **New Skill** to open the form. You can also open the DocType form directly at `/app/fac-skill/new`.

### Fields

The FAC Skill form is grouped into five sections.

#### Basic Information

| Field | Required | Notes |
|---|---|---|
| **Skill ID** | yes | Must be unique across all skills. Must match `^[a-z0-9_-]+$` — lowercase letters, digits, hyphens, underscores. Example: `sales-pipeline-review`. You cannot change it after save (well, you can, but existing MCP URIs will break). |
| **Title** | yes | Human-readable name. Shown in MCP clients and in the admin list. |
| **Status** | yes | Draft (default) / Published / Deprecated. See [Publishing Workflow](#publishing-workflow). |
| **Skill Type** | no | Tool Usage (default) / Workflow. |
| **Category** | no | Optional Prompt Category link. Purely for organization. |
| **System Skill** / **Source App** | — | Read-only. Set automatically when a skill is installed via an app's `assistant_skills` hook. You cannot edit or delete system skills from the UI while the owning app is installed. |

#### Description

| Field | Required | Notes |
|---|---|---|
| **Description** | yes | One-line description. Shown in MCP `resources/list` and, under the `replace` skill mode, shown to the LLM as the short description for the linked tool. Keep it under ~200 characters. |

#### Skill Content

| Field | Required | Notes |
|---|---|---|
| **Content** | yes | Full markdown body. This is the document the LLM will receive when it fetches `resources/read`. |

#### Linked Tool (only visible when Skill Type = Tool Usage)

| Field | Required | Notes |
|---|---|---|
| **Linked Tool** | no (but strongly recommended) | The MCP tool name this skill teaches. Example: `list_documents`. Must match the registered tool name exactly. If you leave it empty the form will warn but save anyway. |

#### Organization & Analytics

| Field | Notes |
|---|---|
| **Use Count** | Read-only. Increments each time an MCP client fetches the skill content via `resources/read`. |
| **Last Used** | Read-only. Timestamp of the most recent fetch. |

#### Sharing & Permissions

| Field | Notes |
|---|---|
| **Visibility** | Private / Shared / Public. Default Public. See [Visibility and Sharing](#visibility-and-sharing). |
| **Owner** | Defaults to the current user. Only System Managers can change it. |
| **Shared With Roles** | Only shown when Visibility = Shared. A table of role names that can access the skill when it's Published. **Required** if you pick Shared. |

### Who can create skills?

Create permission is granted by default to **System Manager**, **Assistant Admin**, **Assistant User**, and the **All** role (for skills the user will own). Edit and delete permissions follow the row's ownership + visibility rules.

---

## Skill Types

### Tool Usage

A Tool Usage skill teaches the LLM how to use one specific MCP tool. Always set `linked_tool` to the tool name.

Use this type when:
- Your tool has non-obvious parameter combinations
- There's a common pitfall users keep running into
- You need to demonstrate 2–3 worked examples that the input schema alone can't convey

The built-in examples in [`docs/skills/`](../skills/) (bundled with FAC itself) all follow this pattern — see `list_documents.md`, `create_document.md`, `extract_file_content.md` for reference.

### Workflow

A Workflow skill describes a multi-step procedure that involves multiple tools or decision points. There's no `linked_tool` — workflows stand on their own.

Use this type when:
- The LLM needs to orchestrate several tools in a specific order
- Domain context matters: "first verify the customer is active, then check credit limit, then create the invoice"
- You're documenting a business process rather than a single tool

---

## Visibility and Sharing

Skills have three visibility settings that combine with the status to decide who sees what.

### Visibility × Status — who can see the skill?

| Visibility | Status | Owner sees it? | Other users see it? |
|---|---|---|---|
| Private | Draft | Yes | No |
| Private | Published | Yes | No |
| Shared | Draft | Yes | No |
| Shared | Published | Yes | Yes, if they have one of the `shared_with_roles` |
| Public | Draft | Yes | No |
| Public | Published | Yes | Yes, all users |
| any | Deprecated | Yes | Same as Published — still visible, flagged as deprecated |

Additional rules:

- **System Manager** always sees all skills regardless of visibility.
- **System skills** (installed via an app's `assistant_skills` hook) are visible to every user when Published, regardless of their visibility field.
- A skill's **owner** always sees their own skill even when it's Draft.

The enforcement lives in two places: row-level at the DocType layer ([`utils/permissions.py:135-180`](../../frappe_assistant_core/utils/permissions.py)) and in-memory when serving MCP `resources/list` ([`api/handlers/resources.py:46-92`](../../frappe_assistant_core/api/handlers/resources.py)).

### When to use each visibility

- **Private** — drafts, personal notes, experiments you're not ready to share.
- **Shared** — team- or role-specific guidance (e.g. a Finance-only workflow for month-end close). Pick the roles carefully — anyone with the role can read the skill.
- **Public** — organization-wide guidance that every user of the assistant should benefit from.

---

## Publishing Workflow

The `status` field moves the skill through its lifecycle.

1. **Draft** — only the owner can see it. Use this while writing. Drafts do **not** appear in MCP `resources/list` for anyone other than the owner.
2. **Published** — visible per the visibility rules above. Shows up in `resources/list`.
3. **Deprecated** — still visible (so existing clients don't break) but flagged as outdated. Use when you've written a replacement and want to signal "prefer the other one."

To publish, either:
- Open the skill form and change Status to Published, then Save.
- From the FAC Admin → Skills list, toggle the publish checkbox on the row.

Unpublishing (Published → Draft) immediately hides the skill from everyone except the owner.

---

## Linking to a Tool

For a Tool Usage skill, `Linked Tool` is the single most important field — it's how the LLM connects the skill to the tool it teaches.

- The value must match a registered MCP tool name exactly (e.g. `list_documents`, not `List Documents`).
- Only **one Published Tool Usage skill per tool** is used to drive the `replace` skill mode. If you have multiple, the first one returned by the query wins — keep it to one per tool.
- A Workflow skill can mention tools by name in its content but does not use the `linked_tool` field.

---

## Skill Mode — Supplementary vs Replace

Assistant Core Settings has a **Skill Mode** setting that controls how skills interact with `tools/list`. There are two modes:

### Supplementary (default)

Tool descriptions in `tools/list` are unchanged. Skills appear as independent MCP resources that the LLM can discover via `resources/list` and fetch via `resources/read` when it wants deeper guidance.

This is the safe default: no tool-description changes, no risk of breaking existing clients. Use it when you're just starting to add skills or when your MCP clients don't advertise strong Resources support.

### Replace

For every tool that has a linked Published skill, the tool's description in `tools/list` is replaced with a short template:

```
<tool_name>: <skill description>. Detailed guidance: fac://skills/<skill-id>
```

This is a **token-optimization** strategy: the tool listing becomes much shorter, and the LLM is pointed at the skill URI for the details. It's effective when:
- You have many tools with rich descriptions
- Token budget in `tools/list` is a measurable problem
- Your MCP clients reliably follow resource URIs

Tools without a linked Published skill keep their original descriptions under both modes.

The implementation lives in [`mcp/server.py:303-334`](../../frappe_assistant_core/mcp/server.py) and pulls the tool → skill map from [`api/handlers/resources.py:215-229`](../../frappe_assistant_core/api/handlers/resources.py).

Change modes in **Assistant Core Settings** → **Skill Mode**.

---

## Best Practices

### Structure

For a Tool Usage skill, use this shape:

```markdown
# How to Use <tool_name>

## When to use this tool
One paragraph — what the tool is for, when to prefer it over alternatives.

## Parameters

| Name | Type | Required | Description |
|---|---|---|---|
| ... | ... | ... | ... |

## Examples

### Common case
```json
{ ... }
```

### Edge case
```json
{ ... }
```

## Common pitfalls
- ...

## Related tools
- `other_tool` — when to use instead
```

### Content rules

- **One-sentence purpose up front.** The LLM often reads only the first section before deciding whether to continue.
- **Every line should teach something.** If a line just restates the JSON schema, cut it — the LLM already has the schema from `tools/list`.
- **Include 2–3 realistic examples** with expected outputs. Examples carry more weight than prose.
- **Call out pitfalls explicitly.** A "Common pitfalls" section with 3–5 bullets is one of the highest-value parts of a skill.
- **Aim for under ~5 KB.** Longer than that is a signal the skill should be split (for example, separate "how to filter" from "how to paginate"). Workflow skills can run longer when the process genuinely needs it.
- **Write for the LLM, not for humans.** Short paragraphs, dense tables, explicit constraints. Skip marketing language.

### Content density

Look at the bundled skill [`docs/skills/list_documents.md`](../skills/list_documents.md) as a reference for density — almost every line teaches either a parameter behaviour, a filter syntax, or a gotcha.

---

## Analytics

Two read-only fields track skill usage:

- **Use Count** — incremented each time an MCP client fetches the skill content via `resources/read`. Note that `resources/list` does **not** increment this.
- **Last Used** — timestamp of the most recent fetch.

Use analytics to:
- Find unused skills that are adding noise to `resources/list` without paying their way
- Identify popular skills worth polishing further
- Spot workflows the team actually reaches for vs. ones you thought they would

The counter update happens in [`SkillManager.increment_usage`](../../frappe_assistant_core/api/handlers/resources.py).

---

## What NOT to Put in a Skill

- **Don't duplicate the tool's JSON schema.** The LLM already has the schema from `tools/list`. A skill should add colour — examples, pitfalls, workflow context — not restate parameter types.
- **Don't put secrets, API keys, or credentials.** Published skills are visible to every user allowed by their visibility rule. Treat skill content as readable by any employee.
- **Don't put time-sensitive data.** Skills are static markdown. If something needs to be "as of last Tuesday," it belongs in a tool response, not a skill.
- **Don't write long-form prose.** The LLM benefits from density, not elegance. Short paragraphs, dense tables, explicit constraints.
- **Don't cross-link to internal docs behind a VPN.** If the LLM can't reach a URL, citing it is worse than useless.

---

## Related documentation

- [Skills Developer Guide](../development/SKILLS_DEVELOPER_GUIDE.md) — shipping skills with your Frappe app
- [Prompt Templates User Guide](prompt-templates.md) — the other user-generated content primitive in FAC
- [Plugin Management Guide](PLUGIN_MANAGEMENT_GUIDE.md) — enabling / disabling entire tool categories
- [Architecture Overview](../architecture/ARCHITECTURE.md) — where skills fit in the overall design

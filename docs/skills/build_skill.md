# Building Skills

## Overview

A **skill** is a knowledge document that you load on demand. Skills exist because your training data doesn't include this workspace's conventions, this customer's process, or the exact shape of a tool's arguments.

Skills are stored as `FAC Skill` documents **on the user's own site**, created with `create_document`. They reach you through a two-stage mechanism, and understanding it is the whole job:

1. **Always in your system prompt:** every accessible skill's `title` and `description`. Nothing else.
2. **Only when you ask:** the full `content`, fetched by calling `get_skill(skill_id)`.

So `description` is the entire discovery surface. If it doesn't make you reach for the skill at the right moment, the content might as well not exist.

## When to build one

Build a skill when the user says:
- "create a skill for this", "remember how to do this", "document this process"
- "every time someone asks X, do Y"
- "you got that wrong — here's how it actually works here"

**Don't** build one when:
- They want reusable *text to send* → that's a **prompt template**. Call `get_skill("build-prompt-template")`.
- They're telling you something about themselves or a one-off preference → that's memory, not a skill.
- The knowledge is generic. A skill explaining what a Sales Invoice is wastes context on every turn. Skills earn their place by being **specific to this workspace**.

## Workflow

1. **Establish the trigger.** Ask, or work out, *when* you should reach for this. That answer becomes the description, so settle it before writing anything.
2. **Write the content.** The procedure, the field names, the gotchas — the things that are wrong or missing in your priors.
3. **Create it** with `create_document`.
4. **Confirm.** Tell the user it's live on their next message, and what phrasing will trigger it.

## Creating the document

```json
{
  "doctype": "FAC Skill",
  "data": {
    "skill_id": "monthly-close-checklist",
    "title": "Monthly Close Checklist",
    "description": "Use when closing the books for a month, running month-end, or asked why a period won't close.",
    "skill_type": "Workflow",
    "status": "Published",
    "visibility": "Private",
    "content": "# Monthly Close Checklist\n\n## Overview\n..."
  }
}
```

## Field reference

| Field | Required | Notes |
|-------|----------|-------|
| `skill_id` | **Yes** | Lowercase letters, numbers, `_`, `-` only. Unique site-wide. Kebab-case is the house style. |
| `title` | **Yes** | Shown in your system prompt. A short noun phrase. |
| `description` | **Yes** | The trigger. See below — this is the field that matters most. |
| `content` | **Yes** | Full markdown. What you get back from `get_skill`. |
| `skill_type` | No | `Tool Usage` (default) or `Workflow`. |
| `linked_tool` | No | For `Tool Usage`: the MCP tool name, e.g. `create_document`. |
| `status` | No | Defaults to `Draft` — **set `Published`** or only the owner sees it. |
| `visibility` | No | `Public` is the doctype default. **Pass `Private` explicitly** unless sharing was requested. |
| `category` | No | Link to an existing `Prompt Category`. |

Never set `is_system` or `source_app`. They mark app-shipped skills, they're read-only, and skills carrying them are pruned by `bench migrate` when they fall out of their app's manifest. A user-created skill leaves both blank and therefore survives migrations — which is what you want.

## Writing the description

This is the part that decides whether the skill ever fires. You are writing a **trigger**, not a summary.

Describe the *situation that should make you open it*, in the words that situation shows up in. Lead with "Use when…".

| | |
|---|---|
| ❌ | "Information about our invoicing process." |
| ✅ | "Use when creating or correcting a customer invoice, or when asked why an invoice was rejected." |
| ❌ | "Deployment documentation." |
| ✅ | "Use when deploying to staging or production, or when a release fails and needs rolling back." |

The bad versions describe the *document*. The good ones describe the *moment*. Include the words a user would actually type — if the team says "month-end" rather than "period close", the description says "month-end".

Keep it to one or two sentences. It's in your context on every single turn.

## Skill type and linked_tool

- **`Tool Usage`** — teaches one specific tool. Set `linked_tool` to the exact tool name. This is the shape of the 20-odd skills shipped with FAC.
- **`Workflow`** — a multi-step procedure spanning several tools, or knowledge with no single tool behind it. Leave `linked_tool` empty.

Choosing `Tool Usage` without a `linked_tool` saves fine but emits a warning. If there's no single tool, it's a `Workflow`.

## Writing the content

You are the reader. Write what *you* would need, not what a human onboarding doc would say.

A structure that works:

```markdown
# <Title>

## Overview          — what this is, in two or three sentences
## When to use       — and explicitly when NOT to
## Workflow          — numbered steps
## Reference         — field names, tool arguments, exact values
## Gotchas           — what goes wrong, and the symptom
## Anti-patterns     — mistakes worth naming
```

What makes a skill worth its tokens:

- **Concrete over abstract.** Real DocType names, real field names, a real example payload.
- **The failure modes.** "This saves successfully but silently does nothing when X" is the highest-value sentence you can write.
- **Corrections to your priors.** If the obvious approach is wrong here, lead with that.
- **Negative space.** "Don't use this for X" prevents more errors than another example.

Aim for 50–200 lines. The whole thing arrives as one tool result, so a 600-line skill is an expensive read. If it's sprawling, split it into two skills with distinct triggers.

## Status and visibility

Default to **`Published` + `Private`**. Live immediately for the person who asked; invisible to everyone else.

`visibility` defaults to `Public` on this DocType, so **omitting the field publishes to the entire workspace.** Always pass it explicitly. A `Public` skill changes every colleague's system prompt — only when asked, and say so when you do it. `Shared` also needs `shared_with_roles` or the save fails.

New skills are picked up on your **next message** — the skill catalog is rebuilt every turn. No cache to clear, nothing to restart.

## Editing an existing skill

```json
{"doctype": "FAC Skill", "filters": {"skill_id": ["like", "%close%"]},
 "fields": ["name", "skill_id", "title", "status", "visibility", "is_system"]}
```

Then `update_document` on the returned `name`.

If `is_system` is `1`, it's shipped by an app. Editing it works, but `bench migrate` overwrites your changes from the app's manifest. To customise a system skill durably, create a new skill with a different `skill_id` instead, and tell the user why.

## Anti-patterns

- **A description that summarises.** The single most common failure. It reads fine and never fires.
- **Documenting general knowledge.** You already know what a Sales Order is. Write down what's different *here*.
- **Publishing workspace-wide by default.** `visibility` defaults to `Public`. Pass `Private`.
- **One giant skill.** Two triggers means two skills.
- **Writing it and not saying how to trigger it.** Close by telling the user what to say to make it fire.

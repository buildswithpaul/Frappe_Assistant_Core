# Building Prompt Templates

## Overview

A **Prompt Template** is a reusable, parameterised prompt that the *user* invokes from the `/` slash menu in chat. They pick it, fill in the arguments, and the rendered text becomes their message.

You are the author, never the caller. There is no tool that "runs" a template — building one hands the user a shortcut they trigger themselves later.

Templates are stored as `Prompt Template` documents **on the user's own site**, created with `create_document`. They belong to whoever asked for them.

## When to build one

Build a template when the user says:
- "templatise this", "save this as a template", "make this reusable"
- "I ask this every month" / "I keep typing this out"
- "make a `/standup` command" or similar

**Don't** build one when:
- They asked a one-off question — just answer it
- The prompt has no variable parts — a template with zero arguments is a saved paragraph, which is fine but say so rather than inventing fake parameters
- They want the *assistant* to know something permanently → that's a **skill**, not a template. Templates are text the user sends; skills are knowledge you load. Call `get_skill("build-skill")`.

## Workflow

1. **Find the variable parts.** Take the prompt the user has in mind and ask which bits change between uses — a date range, a department, a customer. Those become arguments; everything else is fixed text.
2. **Draft the template content.** Write the prompt as you'd want to receive it, with `{{ placeholders }}` where the variables go.
3. **Declare every placeholder** in the `arguments` table. Names must match exactly.
4. **Create it** with `create_document`.
5. **Confirm** by telling the user its name and how to reach it: type `/` in chat and pick it by title.

## Creating the document

```json
{
  "doctype": "Prompt Template",
  "data": {
    "prompt_id": "monthly_sales_review",
    "title": "Monthly Sales Review",
    "description": "Analyse sales performance for a given month and territory.",
    "template_content": "Review sales performance for {{ month }} in the {{ territory }} territory.\n\nCover:\n1. Total revenue vs the prior month\n2. Top 5 customers by value\n3. Any orders still unbilled\n\n{% if include_forecast %}Finish with a forecast for next month.{% endif %}",
    "rendering_engine": "Jinja2",
    "status": "Published",
    "visibility": "Private",
    "arguments": [
      {
        "argument_name": "month",
        "display_label": "Month",
        "argument_type": "string",
        "is_required": 1,
        "description": "Month to review, e.g. 'March 2025'"
      },
      {
        "argument_name": "territory",
        "display_label": "Territory",
        "argument_type": "select",
        "is_required": 1,
        "allowed_values": "North, South, East, West",
        "default_value": "North"
      },
      {
        "argument_name": "include_forecast",
        "display_label": "Include forecast",
        "argument_type": "boolean",
        "is_required": 0,
        "default_value": "0"
      }
    ]
  }
}
```

## Field reference

| Field | Required | Notes |
|-------|----------|-------|
| `prompt_id` | **Yes** | Lowercase letters, numbers, `_`, `-` only. Must be unique site-wide. Snake_case reads best. |
| `title` | **Yes** | What the user sees in the slash menu. Keep it short and scannable. |
| `description` | **Yes** | One line explaining what it does. Shown beside the title. |
| `template_content` | **Yes** | The prompt text with placeholders. |
| `rendering_engine` | No | `Jinja2` (default), `Format String`, or `Raw`. |
| `status` | No | Defaults to `Draft` — **set `Published` explicitly** or it won't appear for anyone but the author. |
| `visibility` | No | `Private` (default), `Shared`, `Public`. |
| `category` | No | Link to a `Prompt Category`. Only use one that exists — check with `list_documents` first. |
| `arguments` | No | Child table, one row per placeholder. |

Never set `is_system`, `source_app`, `use_count`, `last_used`, `version_number`, or `owner_user` — they're managed by the system, and `owner_user` defaults to the requesting user.

## Argument reference

| Field | Notes |
|-------|-------|
| `argument_name` | **Must exactly match the placeholder.** Valid Python identifier. |
| `display_label` | Human-readable label on the input form. |
| `argument_type` | `string`, `number`, `boolean`, `select`, `multiselect`, `date`, `datetime`, `link`, `json` |
| `is_required` | `1` blocks rendering if the user leaves it blank. |
| `default_value` | Applied when the user omits an optional argument. Always a string, even for numbers and booleans. |
| `description` | Help text under the input. Worth writing — it's the only guidance the user gets. |
| `allowed_values` | **Comma-separated string**, not an array. Only for `select` / `multiselect`. |
| `validation_regex` | Optional pattern, matched against the value. |
| `min_length` / `max_length` | `string` type only. |

## Placeholder rules — read this before you save

The validator scans `template_content` for placeholders and compares them against your declared arguments. **It only recognises `{{ name }}` and `{{ name | filter }}`.**

That means these are invisible to it:

```jinja
{% if include_forecast %}...{% endif %}      ← condition variable not detected
{{ customer.name }}                          ← dotted path not detected
{% for row in items %}...{% endfor %}        ← loop variable not detected
```

A variable used *only* inside a `{% %}` block will not be flagged as undeclared — and if you never declare it, the user is never asked for it, so it renders empty or the template fails at use time. **Declare every variable you reference, including ones that appear only in conditions and loops.**

Equally important: **mismatches produce warnings, not errors.** The document saves successfully with an orange "Template uses undefined arguments" message. A successful `create_document` result is *not* proof the template is correct. Re-read your own template and confirm every variable has a matching argument row before you tell the user it's ready.

## Rendering engines

- **Jinja2** (default) — `{{ var }}` plus `{% if %}` / `{% for %}`. Use this unless you have a reason not to.
- **Format String** — Python `str.format()`, so placeholders are `{var}` with single braces. No conditionals.
- **Raw** — no substitution at all. Arguments are pointless here; use it for fixed boilerplate.

Don't mix dialects. A `{var}` inside a Jinja2 template renders as literal `{var}`.

## Status and visibility

Default to **`Published` + `Private`**. That makes the template immediately usable by the person who asked for it, and invisible to everyone else.

`Public` (whole workspace) and `Shared` (specific roles) change what *other people* see in their slash menu. Only set them when the user explicitly asks to share, and say plainly what you're about to do. `Shared` additionally requires `shared_with_roles` — without it the save fails.

A `Draft` template is visible only to its owner. That's occasionally what you want ("let me try this first"), but say so, because it's easy to forget to publish later.

## Editing an existing template

Find it, then update it — don't create a near-duplicate:

```json
{"doctype": "Prompt Template", "filters": {"prompt_id": ["like", "%sales%"]},
 "fields": ["name", "prompt_id", "title", "status", "visibility"]}
```

Then `update_document` on the returned `name`. To replace the `arguments` table, pass the full list — child tables are replaced wholesale, not merged, so omitting a row deletes it.

Editing `template_content`, `rendering_engine`, or any argument bumps `version_number` automatically and shows the user a version-increment notice. That's expected.

## Anti-patterns

- **Inventing arguments.** If the prompt doesn't vary, it doesn't need parameters. Three arguments the user always fills the same way is worse than none.
- **Burying the instruction.** The rendered text is what the assistant receives. Write it as a clear instruction, not as a description of an instruction.
- **A template that only you could use.** The user picks these from a menu with no context. If the title and argument labels don't make sense cold, rewrite them.
- **Leaving it in Draft silently.** If you didn't publish, say so.
- **Claiming success on a warning.** See the placeholder rules above.

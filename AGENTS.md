# Working on Frappe Assistant Core

Notes for coding agents (Claude Code, Codex, and friends) and for humans who want the
short version. [Contributing.md](Contributing.md) covers setup, licensing and how to get
help; this file covers the things that are **not** guessable from reading the code, and
that have actually broken pull requests here.

It deliberately says nothing about PEP 8, docstrings or writing tests. You already know
that. What follows is what this codebase will punish you for not knowing.

FAC is a Frappe app that exposes a Frappe/ERPNext site to AI assistants over MCP, plus
an optional in-site chat experience (FAC Chat). It is AGPL-3.0.

---

## Testing

```bash
# ✅ the only invocations that work — Frappe needs bench context
bench --site <site> run-tests --app frappe_assistant_core
bench --site <site> run-tests --module frappe_assistant_core.tests.test_document_tools
bench --site <site> run-tests --module <dotted.module> --test <test_method_name>

# ❌ these fail or mislead — no Frappe init, no DB connection
pytest tests/
python -m pytest
python test_file.py
```

**`run-tests` prints one summary per category.** A run emits a separate
`Ran N tests … OK` block for integration tests and for unit tests. Reading only the first
block — or only the last — tells you half the story. Check every block before claiming a
suite is green.

**Subclass `BaseAssistantTest`** (`frappe_assistant_core/tests/base_test.py`), not
`FrappeTestCase` directly, and never a plain `unittest.TestCase`. `BaseAssistantTest`
wraps Frappe's test case to guarantee the transaction is rolled back. A plain
`unittest.TestCase` gets no rollback, so **it writes to your development database and
leaves the rows behind.**

**Some tests skip without ERPNext.** A run with ~45 skips on a site without ERPNext
installed is expected, not a failure.

### A green test is not evidence

The most common way a change breaks this repo is a test that **builds the state it needs
instead of getting it the way production does.** The construction makes the code path
reachable, and reachability is often the thing that is broken.

**Prove your test fails before it passes.** Put the bug back, run, confirm red, restore:

```bash
# re-introduce the bug (sed -i '' on macOS, sed -i on Linux), then:
bench --site <site> run-tests --module <module>   # MUST be red here
git checkout -- <file>                            # restore the fix
```

Say in the PR that you did this. It is the single cheapest way to avoid shipping a test
that guards nothing.

**If a test has to manufacture state, justify it in a comment** — one line saying how
production reaches that state. If you cannot write that sentence, the test is fiction:

```python
# ❌ installation never enables chat, so every assertion below tested an impossible state
frappe.db.set_single_value("Assistant Core Settings", "enable_fac_chat", 1)
```

**A mocked boundary proves nothing about the real one.** `MagicMock()` accepts any
attribute, so a call to a method that does not exist passes. Use
`patch(..., autospec=True)` or `create_autospec(...)` so a missing or renamed method
raises instead of silently returning a Mock.

---

## Before you commit

```bash
pip install pre-commit
pre-commit install
pre-commit install --hook-type commit-msg
```

Pre-commit runs what CI runs: ruff (import sort, lint, format), the Frappe semgrep rules,
commitlint, `pip-audit`, and the usual whitespace/AST/JSON/YAML checks. If you skip the
hooks, CI will find the same problems more slowly.

**Commit messages are linted** (`@commitlint/config-conventional`):

- Conventional subject — `fix(tools): …`, `feat(chat): …`, `perf(mcp): …`.
- Body lines **≤ 100 characters**. Prose wrapped by your editor will fail; prefer
  `git commit -F <file>` for anything long.
- **Merge commits are linted too.** `Merge develop into my-branch` is rejected for having
  no type and no subject. Give merge commits a conventional subject as well.

---

## Pull requests

- **Target `develop`, never `main`,** and rebase or merge `develop` in before you ask for
  review.
- **One concern per PR.** A branch carrying several unrelated commits is hard to review and
  usually ends up blocked on the weakest one.
- **A PR that conflicts with `develop` gets no CI at all.** GitHub builds `pull_request`
  runs from the merge ref, so when that cannot be computed, the test, linter and
  commitlint workflows are never created — only head-ref checks such as CodeQL report. The
  PR then *reads* green while nothing ran. Check before you trust it:

  ```bash
  gh pr view <N> --json mergeable,headRefOid
  ```

  An absent check is not a passing check.

- **CI runs newer Frappe than your bench probably does.** The matrix installs the current
  tip of `version-15` (Python 3.12) and `version-16` (Python 3.14), which can be many
  minor releases ahead of a local checkout. A test that asserts Frappe's own behaviour can
  pass locally and fail in CI for that reason alone. Read the CI result before calling a
  change done.

---

## Frappe patterns this repo enforces

Some of these are checked by the semgrep rules; all of them have caused real bugs here.

```python
# ✅ always declare the methods, type the params, translate user-facing text
@frappe.whitelist(methods=["POST"])
def my_endpoint(doctype: str, filters: dict | None = None):
    return frappe.get_all(doctype, filters=filters)
```

- **A missing `methods=` turns a write into a silent no-op.** Frappe rolls back a GET
  request, so the handler appears to succeed and the write disappears.
- **No raw SQL.** Use `frappe.get_all`, `frappe.db.get_value`, `frappe.db.count` or
  `frappe.qb`. Raw SQL also bypasses User Permissions, which is a security bug, not a
  style one.
- **`frappe.get_all` never checks permissions, and you cannot ask it to.** It overwrites
  `ignore_permissions=True` internally, so passing `False` is silently discarded. Use
  `frappe.get_list` when the result reaches a user, or check access yourself.
- **Never `frappe.db.commit()` in a whitelisted endpoint** — Frappe commits for you.
  Background jobs *do* need an explicit commit.
- **Wrap user-facing strings in `_()`**, including `frappe.throw(_("…"))`.
- **DocType-level permission ≠ document-level permission.** Check both. A document-level
  denial raises `frappe.PermissionError` **with no message** — the reason is in
  `frappe.flags.error_message`, so `str(exc)` is empty.

### Traps around settings and install state

- **A Single DocType field does not read its declared default.** A `Check` field declared
  `"default": "1"` reads back `0` on any site whose `tabSingles` row already existed.
  Probe the value; do not trust the schema JSON. New defaults need the schema default,
  an `after_install` seeder **and** a migration patch.
- **FAC Chat is off on every fresh install.** `enable_fac_chat` defaults to `0` and
  nothing enables it during `after_install`; only the `toggle_chat` admin action does. So
  a code path gated on `is_chat_enabled()` never runs at install time, and `/copilot/`
  raises `PageDoesNotExistError` until an administrator switches chat on.
- **Clear caches after changing a DocType**: `bench clear-cache && bench restart`.

### Vue components (FAC Chat frontend)

`frappe_assistant_core/chat/frontend/` is a Vue 3 app, and the Desk widget is built from the same components.

- **Keep a component to about 400 lines** (template, script and style together), and split it once it passes 500.
- **Group a complex feature in a sub-directory**, as `components/settings/billing/`, `settings/users/` and
  `layout/` do.
- **The parent is a thin orchestrator:** state, layout and wiring of its sub-components. Each sub-component owns
  its template, scoped styles and pure helper functions.
- **Props down, events up.** Data flows down through props; actions come back up through emits.
- Example: `settings/BillingSettings.vue` is the tabbed container, with `billing/BillingHero.vue`,
  `billing/BillingTabs.vue`, `billing/PlansTab.vue` and `billing/SettingsTab.vue` as its parts.

---

## Where things live

| Path | What |
|---|---|
| `frappe_assistant_core/plugins/*/tools/` | the MCP tools, one file per tool, grouped by plugin (`core`, `data_science`, `faco`, `visualization`) |
| `frappe_assistant_core/core/` | `BaseTool`, the tool registry, security config |
| `frappe_assistant_core/mcp/` | the MCP server and the JSON-RPC request handling |
| `frappe_assistant_core/api/` | whitelisted HTTP endpoints, including the MCP endpoint |
| `frappe_assistant_core/chat/` | FAC Chat: backend APIs, DocTypes and the Vue frontend |
| `frappe_assistant_core/assistant_core/` | DocTypes and the FAC Admin Desk page |
| `frappe_assistant_core/patches/` | migration patches, registered in `patches.txt` |
| `frappe_assistant_core/tests/` | tests, plus `base_test.py` |
| `docs/skills/` | per-tool reference the assistant itself reads |

A new tool subclasses `BaseTool`, lives under the right plugin's `tools/`, and gets a
matching page in `docs/skills/`. If you change a tool's behaviour, update that page in the
same pull request — it is what the model is told about the tool, so a stale page is a
behaviour bug.

**FAC Cloud is not an inside caller.** It reaches this site over the same
`fac_endpoint.handle_mcp` URL as Claude Desktop — `chat/api/auth.py` registers that URL
with it. So a tool that only FAC Cloud can satisfy is otherwise offered to every client
and fails for them; the faco plugin's browser tools used to hang for 30 seconds that way.
A plugin keeps its tools to FAC Cloud by overriding `BasePlugin.is_fac_cloud_only()`, and
`utils/mcp_caller.py` recognises FAC Cloud by the OAuth client its bearer token belongs
to — never by anything the client says about itself. Put such a filter at the endpoint,
not in the tool registry: the registry answers "what may this *user* access", which FAC
Chat's own preferences UI asks over a session cookie.

**Never enable or disable a plugin from a test.** `PluginPersistence.save_plugin_state`
calls `frappe.db.commit()`, so the toggle escapes the test rollback and permanently
changes the site it ran against.

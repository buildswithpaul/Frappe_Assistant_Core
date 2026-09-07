# Frappe Assistant Core

> Talk to your ERPNext site. FAC lets Claude, ChatGPT, and other
> MCP-ready LLMs work directly with your invoices, customers, stock,
> workflows, and custom apps — inside your ERPNext permissions, with
> every call logged.

[![Version](https://img.shields.io/github/v/release/buildswithpaul/Frappe_Assistant_Core?label=version)](https://github.com/buildswithpaul/Frappe_Assistant_Core/releases)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](https://pypi.org/project/frappe-assistant-core)
[![License](https://img.shields.io/badge/license-AGPL--3.0-green)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-2025--06--18-orange)](https://modelcontextprotocol.io)
[![Tools](https://img.shields.io/badge/tools-24-brightgreen)](https://docs.assistantcore.cloud/api/tool-reference)
[![Docs](https://img.shields.io/badge/docs-assistantcore.cloud-blue)](https://docs.assistantcore.cloud)

[![CI](https://github.com/buildswithpaul/Frappe_Assistant_Core/actions/workflows/ci.yml/badge.svg)](https://github.com/buildswithpaul/Frappe_Assistant_Core/actions/workflows/ci.yml)
[![Frappe Cloud](https://img.shields.io/badge/Frappe%20Cloud-Marketplace-blue)](https://cloud.frappe.io/marketplace/apps/frappe_assistant_core)
[![Stars](https://img.shields.io/github/stars/buildswithpaul/Frappe_Assistant_Core?style=social)](https://github.com/buildswithpaul/Frappe_Assistant_Core/stargazers)
[![Forks](https://img.shields.io/github/forks/buildswithpaul/Frappe_Assistant_Core?style=social)](https://github.com/buildswithpaul/Frappe_Assistant_Core/network/members)
[![Sponsors](https://img.shields.io/github/sponsors/buildswithpaul?logo=github)](https://github.com/sponsors/buildswithpaul)

---

## New in FAC 3.0: FAC Chat

FAC 3.0 introduces **FAC Chat** — an opt-in, in-Frappe AI chat assistant
powered by our managed **Assistant Runtime SaaS**.

FAC now offers two ways to use it:

- **BYO-LLM (MCP server, free)** — the original FAC. Connect any
  MCP-ready LLM client (Claude Desktop, Cursor, ChatGPT desktop, etc.)
  to your Frappe data over MCP. You bring the LLM, you pay your own
  LLM bill, nothing leaves your stack. Ships enabled by default.
- **FAC Chat (in-Frappe chat UI, SaaS)** — opt-in. A native chat
  widget on every Desk page plus a full-screen SPA at `/copilot`,
  powered exclusively by our managed FAC Cloud. One
  subscription covers LLM access across providers, conversation
  memory, RAG, and workflow automation. Ships **disabled by default**.

The split is intentional: BYO-LLM keeps the existing free MCP path
untouched; FAC Chat is the managed experience for teams that want the
chat inside Frappe without wiring up their own LLM keys. See
[FAC Chat](#fac-chat) below for full details.

---

## What you get

Once FAC is installed, your team can ask an LLM for things they'd
normally do by hand:

> *"Show me overdue invoices from our top five customers."*
>
> *"Update this lead's status to Qualified and set next action date to
> Monday."*
>
> *"Run the monthly revenue report and summarise the top movers."*
>
> *"How much stock of SKU-1234 do we have across all warehouses?"*

Behind that simple interaction, FAC exposes **24 built-in tools** for
the things your team does every day — document CRUD, search, reports,
workflows, analytics, file extraction, and dashboards. Admins can
publish **Skills** (reusable instructions that teach the LLM how to
handle a specific job) and **Prompt Templates** (saved starting points
users can pick from the admin UI) so answers stay consistent and use
the right reports. The LLM authenticates over **OAuth 2.0** as a real
ERPNext user, so it only sees data that user can already see in the
desk. Every call is recorded in the **Assistant Audit Log**.

It's a Frappe app, so developers can extend the toolset from their own
Frappe apps through a hook — your data model, your business logic,
scoped per your app.

Your data stays in your site. You control which LLM connects.

---

## Quick start

Two install paths depending on how you run Frappe.

### On Frappe Cloud (recommended)

1. Go to your site's **Apps** tab in the Frappe Cloud dashboard.
2. Find **Frappe Assistant Core** in the marketplace and click **Install**.
3. Frappe Cloud installs and migrates the app for you.

Marketplace: <https://cloud.frappe.io/marketplace/apps/frappe_assistant_core>

### On self-hosted bench

```bash
cd frappe-bench
bench get-app https://github.com/buildswithpaul/Frappe_Assistant_Core
bench --site <your-site> install-app frappe_assistant_core
```

### Connect your LLM

Once installed, the same four steps work for any MCP-compatible client.
Example shown for Claude Desktop:

1. Go to **Desk → FAC Admin** and copy the **MCP Endpoint URL**.
2. In **Claude Desktop → Settings → Connectors → Add Custom Connector**,
   paste the URL and click **Add**.
3. Click **Connect**, log in with your ERPNext account, and authorize.
4. Ask Claude something — for example, *"List all customers created this
   month."*

For ChatGPT, Claude Web, and MCP Inspector walkthroughs, see the
[Quick Start](https://docs.assistantcore.cloud/getting-started/quick-start) on the docs site.

---

## FAC Chat

**FAC Chat is an opt-in, SaaS-powered chat experience that ships inside
FAC.** Where the MCP server lets external LLM clients (Claude Desktop,
Cursor, ChatGPT desktop) talk to your Frappe data with your own LLM
keys, FAC Chat brings the conversation inside Frappe itself — a widget
on every Desk page and a full-screen SPA at `/copilot` — powered by
our managed **Assistant Runtime** subscription.

### Two ways to use FAC

| Option | What it is | LLM | Cost | Where the chat lives |
|---|---|---|---|---|
| **BYO-LLM (MCP server)** | The original FAC. Exposes Frappe data over MCP to any MCP-ready client. | You bring your own (Anthropic, OpenAI, Gemini, Bedrock, etc.) | Free. You pay your own LLM bill. | In your external MCP client (Claude Desktop, Cursor, etc.). No chat UI inside Frappe. |
| **FAC Chat (SaaS)** | In-Frappe chat widget + `/copilot` SPA. Streaming, tool use, attachments, history, memory, RAG, workflows. | Managed by Assistant Runtime. One subscription, multiple providers. | Subscription required. Sign up flow runs inside the chat UI. | Inside Frappe Desk. |

These are **mutually exclusive at the chat layer**: the in-Frappe chat
UI is only available through Assistant Runtime. There is no BYO-LLM
path for FAC Chat — if you want to bring your own LLM, use the MCP
server.

Both options share the same plugin registry, the same
`Assistant Audit Log`, and the same OAuth-based authentication.
Enabling FAC Chat does NOT change anything for your MCP clients — both
can run side by side.

### Enabling FAC Chat

1. Go to **Assistant Core Settings → FAC Chat tab**.
2. Toggle **Enable FAC Chat** to ✓ and save.
3. Run `bench restart`.

A discovery banner on the Desk landing page will also walk admins
through enabling chat — it appears once per admin and can be dismissed.

After enabling:
- The chat widget appears in the corner of Frappe Desk pages.
- The full-screen SPA is reachable at `/copilot`.
- The first time a user opens chat, they walk through a one-time
  onboarding that registers the tenant with Assistant Runtime and
  links it to a subscription.

### What FAC Chat is NOT

- It is **not required** for MCP server users. Skip it entirely if
  Claude Desktop or another MCP client is your only access pattern —
  the free MCP path keeps working exactly as before.
- It is **not a BYO-LLM frontend**. The in-Frappe chat UI talks only
  to Assistant Runtime. If you want to bring your own LLM keys, the
  MCP server is the path for that.
- It does **not change** FAC's tool catalog. The same 24 built-in
  tools are available to MCP clients and to FAC Chat alike.
- It does **not store conversations off-site without consent**.
  Conversation history lives in your Frappe database; only the LLM
  request payload (messages + tool call results) is forwarded to
  Assistant Runtime to generate the next response.

---

## Skills and Prompt Templates

FAC gives you two ways to shape what the LLM does with your data.

**Skills** are reusable instructions you give the LLM — stored as
`FAC Skill` documents inside your site. Each skill has a `skill_id`,
a description, and markdown content describing how to handle a specific
task using the available tools. The LLM lists skills on connect and
pulls them on demand, so every time someone asks about, say, the
monthly sales close, the answer is consistent and uses the right
reports.

**Prompt Templates** are saved starting points for the *user's* side
of the conversation — Jinja-templated prompts with typed arguments
(dropdowns, dates, booleans). Authors publish them from the admin page;
users pick one, fill in the arguments, and the rendered prompt is sent
to the LLM. Use them for frequently-asked analyses like "Sales
Analysis", "Manufacturing Analysis", or your own industry-specific
workflows.

Both live in Frappe, so they're version-controlled with your site,
shareable across users, and can be shipped by external Frappe apps
through the `assistant_skills` hook.

---

## Tools at a glance

FAC ships 24 tools across four plugins: **Core** (Frappe operations),
**Data Science** (Python execution, analytics, file extraction),
**Visualization** (dashboards and charts), and **Custom Tools** (the
registry for tools contributed by external apps).

| Category | Tools |
|---|---|
| Documents | `get_document`, `list_documents`, `create_document`, `update_document`, `delete_document`, `submit_document` |
| Search | `search`, `search_documents`, `search_doctype`, `search_link`, `fetch` |
| Reports | `report_list`, `report_requirements`, `generate_report` |
| Approvals | `get_pending_approvals`, `run_workflow` |
| Schema | `get_doctype_info` |
| Analytics | `run_python_code`, `run_database_query`, `analyze_business_data` |
| Files | `extract_file_content` |
| Dashboards | `create_dashboard`, `create_dashboard_chart`, `list_user_dashboards` |

Full specification for each tool is in the
[Tool Reference](https://docs.assistantcore.cloud/api/tool-reference).

---

## Schema access is live

FAC reads your schema from Frappe's metadata API at the moment a tool is
called. It keeps no schema copy of its own — no snapshot table, no
embedded or vector index of your data model, and no sync command. There
is nothing to re-run and no staleness window to reason about.

In practice that means:

- **Custom DocTypes, Custom Fields, and Property Setters are visible on
  the next tool call.** Create a field in the desk and the LLM sees it
  immediately. `get_doctype_info` returns custom fields merged inline
  with standard fields, along with child-table field definitions, Link
  targets, and the DocType's permission rules.
- **Renames, added options, and changed labels take effect the same
  way** — they come from the same live metadata read.
- **Permissions are evaluated per call against the requesting user**,
  never snapshotted. FAC asks Frappe on each call, so a role change
  applies as soon as Frappe applies it.

FAC does cache a few operational things — whether the server is
enabled, the MCP and OAuth endpoint URLs, and dashboard/health
statistics. None of them describe your schema or your data.

If you reach FAC through another product that embeds or orchestrates it,
that layer may maintain its own schema cache with its own refresh
behaviour. Staleness seen through a wrapper is worth tracing there
first; FAC itself has no such step.

Implementation details are in
[Architecture Overview](docs/internals/INTERNALS.md#schema-access).

---

## Extend with your own tools

If you have a Frappe app and want the LLM to reach into it, use the
`assistant_tools` hook in your app's `hooks.py`. This is the recommended
path — tools travel with the app, survive upgrades, and stay scoped to
your data model. The same pattern works for Skills via the
`assistant_skills` hook.

If you need to modify core FAC behaviour instead, write an internal
plugin.

See the [External App Development guide](docs/development/EXTERNAL_APP_DEVELOPMENT.md)
for the hook contract, and the
[Plugin Development guide](docs/development/PLUGIN_DEVELOPMENT.md) for
internal plugins.

---

## Authentication & security

FAC uses OAuth 2.0 with PKCE for LLM connections — the LLM never sees
the user's Frappe password. Every tool call is scoped to the calling
user's Frappe and ERPNext roles and permissions: if the user cannot
read a DocType in the desk, they cannot read it through the LLM either.
Every call is logged to `Assistant Audit Log` with caller, tool,
arguments, and result status, so admins always have a full record of
what the LLM did.

For setup and advanced configuration:

- [OAuth Setup Guide](https://docs.assistantcore.cloud/getting-started/oauth/setup-guide)
- [Code Execution Security](https://docs.assistantcore.cloud/guides/code-execution-security)
- [MCP StreamableHTTP Guide](https://docs.assistantcore.cloud/internals/mcp-streamable-http)

---

## Documentation

**📚 Full docs are at [docs.assistantcore.cloud](https://docs.assistantcore.cloud)**

Common entry points:

- [Installation](https://docs.assistantcore.cloud/getting-started/installation) — Frappe Cloud one-click + self-hosted bench
- [Quick Start](https://docs.assistantcore.cloud/getting-started/quick-start) — connect Claude Desktop in 5 minutes
- [OAuth Setup Guide](https://docs.assistantcore.cloud/getting-started/oauth/setup-guide) — production OAuth configuration
- [Tool Reference](https://docs.assistantcore.cloud/api/tool-reference) — every built-in tool
- [API Reference](https://docs.assistantcore.cloud/api/reference) — MCP and OAuth protocol surface
- [Architecture](https://docs.assistantcore.cloud/internals/architecture) — how FAC is put together
- [Changelog](https://docs.assistantcore.cloud/reference/changelog) — release notes

For contributors editing this repo, see [`docs/development/`](docs/development/) and [Contributing.md](Contributing.md).

---

## Sponsor and professional services

Frappe Assistant Core is built and maintained in the open. If it saves
your team time, please consider sponsoring ongoing maintenance and new
features on [GitHub Sponsors](https://github.com/sponsors/buildswithpaul)
— recurring or one-time contributions.

Professional implementation, customization, training, and enterprise
support are delivered by our official services partner
[Promantia](https://promantia.com). Reach them at
[ai-support@promantia.com](mailto:ai-support@promantia.com), or register
your project at
<https://erp.promantia.in/fac-registration/new>. Full details in
[COMMERCIAL.md](COMMERCIAL.md).

The software itself remains completely free and open source under
AGPL-3.0. Professional services are optional.

---

## License

AGPL-3.0 — see [LICENSE](LICENSE).

For dual-licensing, new partnerships, or sponsorship inquiries, contact
<jypaulclinton@gmail.com>.

## Contributing

Contributions welcome. See [Contributing.md](Contributing.md) for the
pull-request workflow and coding standards.

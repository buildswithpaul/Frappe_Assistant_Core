# Frappe Assistant Core

> Infrastructure that connects LLMs to ERPNext. Tools, skills, prompt
> templates, and OAuth — packaged as a Frappe app so any MCP-compatible
> LLM can work with your ERPNext data, under your existing permissions
> and audit trail.

[![Version](https://img.shields.io/github/v/release/buildswithpaul/Frappe_Assistant_Core?label=version)](https://github.com/buildswithpaul/Frappe_Assistant_Core/releases)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](https://pypi.org/project/frappe-assistant-core)
[![License](https://img.shields.io/badge/license-AGPL--3.0-green)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-2025--06--18-orange)](https://modelcontextprotocol.io)
[![Tools](https://img.shields.io/badge/tools-24-brightgreen)](docs/api/TOOL_REFERENCE.md)

[![CI](https://github.com/buildswithpaul/Frappe_Assistant_Core/actions/workflows/ci.yml/badge.svg)](https://github.com/buildswithpaul/Frappe_Assistant_Core/actions/workflows/ci.yml)
[![Frappe Cloud](https://img.shields.io/badge/Frappe%20Cloud-Marketplace-blue)](https://cloud.frappe.io/marketplace/apps/frappe_assistant_core)
[![Stars](https://img.shields.io/github/stars/buildswithpaul/Frappe_Assistant_Core?style=social)](https://github.com/buildswithpaul/Frappe_Assistant_Core/stargazers)
[![Forks](https://img.shields.io/github/forks/buildswithpaul/Frappe_Assistant_Core?style=social)](https://github.com/buildswithpaul/Frappe_Assistant_Core/network/members)
[![Sponsors](https://img.shields.io/github/sponsors/buildswithpaul?logo=github)](https://github.com/sponsors/buildswithpaul)

---

## What you get

Frappe Assistant Core (FAC) is infrastructure that connects Large Language
Models to ERPNext. It runs inside your Frappe site as a regular app and
bundles everything needed to let an LLM work with your business data:

- **Tools** — 24 built-in operations (document CRUD, search, reports,
  workflows, analytics, file extraction, dashboards) that the LLM can
  invoke over the [Model Context Protocol](https://modelcontextprotocol.io).
- **Skills** — reusable, markdown-authored instructions stored in Frappe
  that teach the LLM how to handle specific tasks consistently.
- **Prompt Templates** — Jinja-templated prompts with typed arguments,
  published from the admin UI.
- **OAuth 2.0 / OIDC** — authentication for MCP clients with Dynamic
  Client Registration and PKCE.
- **Plugin system** — so internal code and external Frappe apps can ship
  their own tools and skills.
- **Admin UI and audit log** — one page to manage everything, and a full
  record of every LLM call.

Install it one-click from the
[Frappe Cloud Marketplace](https://cloud.frappe.io/marketplace/apps/frappe_assistant_core),
or via `bench get-app` on a self-hosted deployment.

For **business users**: ask Claude about sales figures, customers, stock
levels, pending approvals, or anything else you can see in your ERPNext
desk. Claude reads the live database, constrained to your own roles and
permissions.

For **developers**: add tools or skills from your own Frappe app with a
couple of hook entries — your data model, your business logic, scoped
per your app.

What it does **not** do: data does not leave your server unless your LLM
provider fetches it through MCP. This is not a "send your ERP to OpenAI"
service — you control which LLM connects, and each call is authenticated
to a real Frappe user.

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

Once installed:

1. Go to **Desk → FAC Admin** and copy the **MCP Endpoint URL**.
2. In **Claude Desktop → Settings → Connectors → Add Custom Connector**,
   paste the URL and click **Add**.
3. Click **Connect**, log in with your Frappe account, and authorize.
4. Ask Claude something — for example, *"List all customers created this
   month."*

For ChatGPT, Claude Web, or MCP Inspector instructions, see the
[Getting Started guide](docs/getting-started/GETTING_STARTED.md).

---

## Skills (new in v2.4.0)

Skills are reusable instructions you give your LLM — stored as `FAC Skill`
documents inside Frappe. Each skill has a `skill_id`, a description, and
markdown content describing how to handle a specific task with the available
tools.

For example, a skill called `monthly-sales-report` can teach the LLM which
reports to run, which filters to apply, and how to present the output —
so every time someone asks *"give me the monthly sales report"*, the
answer is consistent and uses the right data sources.

Authors publish skills from **Desk → FAC Skill**. Published skills become
discoverable MCP resources, so the LLM can list them and pull them on
demand. External Frappe apps can ship their own skills through the
`assistant_skills` hook — tools and skills travel with the app.

---

## Tools at a glance

FAC ships with 24 tools across the core plugin plus the data-science and
visualization plugins:

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
[Tool Reference](docs/api/TOOL_REFERENCE.md).

---

## Extend with your own tools

If you have a Frappe app and want the LLM to reach into it, use the
`assistant_tools` hook in your app's `hooks.py`. This is the recommended
path — tools travel with the app, survive upgrades, and stay scoped to
your data model.

If you need to modify core FAC behaviour instead, write an internal plugin.

See the [External App Development guide](docs/development/EXTERNAL_APP_DEVELOPMENT.md)
for the hook contract, and the
[Plugin Development guide](docs/development/PLUGIN_DEVELOPMENT.md) for
internal plugins.

---

## Authentication & security

FAC uses OAuth 2.0 with PKCE for LLM connections — the LLM never sees the
user's Frappe password. Every tool call is scoped to the calling user's
ERPNext roles and permissions: if the user cannot read a DocType in the
Frappe UI, they cannot read it through the LLM either. Every call is
logged to `Assistant Audit Log` with caller, tool, arguments, and result
status, so admins always have a full record of what the LLM did.

For setup and advanced configuration:

- [OAuth Setup Guide](docs/getting-started/oauth/oauth_setup_guide.md)
- [Code Execution Security](docs/guides/CODE_EXECUTION_SECURITY.md)
- [MCP StreamableHTTP Guide](docs/architecture/MCP_STREAMABLEHTTP_GUIDE.md)

---

## Documentation

- [Getting Started](docs/getting-started/GETTING_STARTED.md) — full setup walkthrough, including Claude Desktop and ChatGPT
- [OAuth Quick Start](docs/getting-started/oauth/oauth_quick_start.md) — OAuth setup in 2 minutes
- [Tool Reference](docs/api/TOOL_REFERENCE.md) — every tool, arguments, return format
- [API Reference](docs/api/API_REFERENCE.md) — MCP endpoints and OAuth APIs
- [Architecture](docs/architecture/ARCHITECTURE.md) — system design and plugin internals
- [External App Development](docs/development/EXTERNAL_APP_DEVELOPMENT.md) — add tools from your own Frappe app
- [Full documentation index](docs/README.md) — everything else

---

## Sponsor and professional services

Frappe Assistant Core is built and maintained in the open. If it saves your
team time, please consider sponsoring ongoing maintenance and new features
on [GitHub Sponsors](https://github.com/sponsors/buildswithpaul) —
recurring or one-time contributions.

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

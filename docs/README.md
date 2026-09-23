# Frappe Assistant Core — Repository Documentation

> **User documentation has moved to [docs.assistantcore.cloud](https://docs.assistantcore.cloud).**
>
> If you're installing FAC, configuring OAuth, calling the MCP API, or looking for the tool reference, start there.

## What lives in this folder

This directory contains documentation that ships **with the code** — either because contributors editing FAC need it close at hand, or because the docs *are* the artefact (the bundled skill markdowns).

### Development guides — for people editing FAC

- **[DEVELOPMENT_GUIDE.md](development/DEVELOPMENT_GUIDE.md)** — local dev setup, code style, debugging
- **[PLUGIN_DEVELOPMENT.md](development/PLUGIN_DEVELOPMENT.md)** — write an internal plugin
- **[EXTERNAL_APP_DEVELOPMENT.md](development/EXTERNAL_APP_DEVELOPMENT.md)** — register tools from your own Frappe app via the `assistant_tools` hook
- **[SKILLS_DEVELOPER_GUIDE.md](development/SKILLS_DEVELOPER_GUIDE.md)** — ship markdown skills via the `assistant_skills` hook
- **[TEST_CASE_CREATION_GUIDE.md](development/TEST_CASE_CREATION_GUIDE.md)** — test patterns and conventions
- **[OAUTH_CORS_CONFIGURATION.md](development/OAUTH_CORS_CONFIGURATION.md)** — CORS configuration for browser-based MCP clients (development only)
- **[PRE_COMMIT_SETUP.md](development/PRE_COMMIT_SETUP.md)** — local pre-commit hook setup
- **[RELEASE_GUIDE.md](development/RELEASE_GUIDE.md)** — release and versioning workflow

### Bundled skill content

The [`skills/`](skills/) folder holds the markdown bodies of the FAC Skills that ship with the app — one file per MCP tool, each one teaching the LLM how to use that tool well. They pair with the manifest at [`frappe_assistant_core/data/system_skills.json`](../frappe_assistant_core/data/system_skills.json) (which lists the `skill_id`, `linked_tool`, and `content_file` for each entry).

These files live in the repo (not on the docs site) because they are versioned alongside the tool code — when a tool's signature changes, its skill markdown changes in the same commit.

## Looking for something else?

| You want to… | Go to |
|---|---|
| Install FAC | [docs.assistantcore.cloud/getting-started/installation](https://docs.assistantcore.cloud/getting-started/installation) |
| Connect Claude Desktop / ChatGPT | [Quick Start](https://docs.assistantcore.cloud/getting-started/quick-start) |
| Configure OAuth | [OAuth Setup Guide](https://docs.assistantcore.cloud/getting-started/oauth/setup-guide) |
| Browse the tool catalogue | [Tool Reference](https://docs.assistantcore.cloud/api/tool-reference) |
| Read release notes | [Changelog](https://docs.assistantcore.cloud/reference/changelog) |
| Report a bug or request a feature | [GitHub Issues](https://github.com/buildswithpaul/Frappe_Assistant_Core/issues) |
| Sponsor ongoing development | [GitHub Sponsors](https://github.com/sponsors/buildswithpaul) |

## Contributing

See [`Contributing.md`](../Contributing.md) at the repository root.

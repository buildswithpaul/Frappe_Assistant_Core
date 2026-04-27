# Developer Tools Plugin

## Overview

The Developer Tools plugin extends Frappe Assistant Core from a data-layer assistant into a development assistant. It provides generic filesystem operations that allow the AI to create Frappe apps, write code files (Script Reports, custom modules, etc.), and read existing code — all through MCP tools.

This plugin bridges the gap where users need complex Script Reports, custom server-side logic, or other code artifacts that currently require a developer to write manually.

### Key Design Principles

- **Generic tools, not per-doctype tools** — The tools operate on files and directories, not on specific Frappe DocTypes. The AI decides what content to write based on the user's request.  
- **Custom apps only** — Write operations are restricted to custom apps. Standard apps (frappe, erpnext, hrms, etc.) are protected from modification.  
- **Python APIs, not bench CLI** — All operations use Frappe's Python APIs internally (e.g., `frappe.installer.install_app()`), making the plugin compatible with both self-hosted installations and Frappe Cloud.  
- **System Manager only** — All tools require the System Manager role due to the sensitive nature of filesystem operations.  
- **Inline syntax validation** — `write_file` automatically validates Python and JSON files after writing and reports errors immediately so the AI can self-correct.

---

## Plugin Architecture

```
plugins/developer_tools/
├── __init__.py
├── plugin.py                  # DeveloperToolsPlugin(BasePlugin)
└── tools/
    ├── __init__.py            # Shared security helpers
    ├── ensure_app.py          # EnsureApp — create custom Frappe apps
    ├── write_file.py          # WriteFile — write files to custom apps (with syntax validation)
    ├── read_file.py           # ReadFile — read files from any app
    ├── list_app_files.py      # ListAppFiles — browse app directories
    └── describe_app.py        # DescribeApp — full app structure tree for LLM context
```

### Tools Summary

| Tool | Purpose | Read/Write | Protected App Check |
| :---- | :---- | :---- | :---- |
| `ensure_app` | Create a new Frappe app non-interactively | Write | Yes — cannot overwrite standard apps |
| `write_file` | Write content to a file in a custom app (validates syntax) | Write | Yes — blocks writes to standard apps |
| `read_file` | Read a file from any Frappe app | Read | No — reading standard apps is allowed |
| `list_app_files` | List files/directories in any app | Read | No — listing standard apps is allowed |
| `describe_app` | Get complete app structure tree with context | Read | No — can describe any app |

---

## Deployment Strategies: Self-Hosted vs Frappe Cloud

### The Problem with Fra ppe Cloud

Frappe Cloud uses Docker containers. When you upgrade or redeploy a bench:

- A **new container** is built from the `apps.json` manifest  
- Only apps listed in `apps.json` (with git repos) survive  
- Any app created locally on the filesystem **gets wiped**

This means `ensure_app` creating a local-only app works perfectly for self-hosted but is **ephemeral on Frappe Cloud**.

### Two-Strategy Approach

The Developer Tools plugin uses a **dual strategy** based on the deployment environment:

#### Strategy 1: Filesystem (Self-Hosted) — Full Capability

On self-hosted installations, the tools write directly to the filesystem:

```
ensure_app → write_file → bench migrate → Standard Script Report on disk
```

**Advantages:**

- Full Python capabilities (unrestricted imports, any library)  
- Better performance (compiled once, cached)  
- Version-controllable via git  
- Full Frappe module system integration

**Use when:** Self-hosted, development environments, or when the user has a git repo backing the custom app.

#### Strategy 2: Database (Frappe Cloud) — Persistent but Restricted

On Frappe Cloud (or when persistence across rebuilds is required), the AI should use existing FAC tools to create **database-stored artifacts** instead:

| Artifact | Filesystem Tool | Database Alternative | Survives Rebuild? |
| :---- | :---- | :---- | :---- |
| Script Report | `write_file` (4 files) | `create_document` (Report DocType, `is_standard="No"`) | DB: Yes, FS: No |
| Server Script | `write_file` (.py) | `create_document` (Server Script DocType) | DB: Yes, FS: No |
| Client Script | `write_file` (.js) | `create_document` (Client Script DocType) | DB: Yes, FS: No |
| Print Format | `write_file` (.html) | `create_document` (Print Format, `custom_format=1`) | DB: Yes, FS: No |
| Web Form scripts | `write_file` | `create_document` (Web Form, `client_script` field) | DB: Yes, FS: No |

**Database-stored code limitations:**

- Executed via `safe_exec()` with RestrictedPython — no arbitrary imports  
- Only Frappe-whitelisted utilities available (frappe.db, frappe.utils, json, etc.)  
- Slower execution (compiled on each run, not cached)  
- No access to external Python libraries

**Use when:** Frappe Cloud, production environments where persistence matters more than capability.

### How the AI Should Decide

The AI should ask or detect the environment:

```
User: "Create a Script Report for customer outstanding"

AI decision tree:
├─ Is this self-hosted / development?
│  └─ YES → Use filesystem tools (ensure_app + write_file)
│           Full Python, better performance, git-trackable
│
└─ Is this Frappe Cloud / needs to survive rebuilds?
   └─ YES → Does the report need external libraries or complex imports?
      ├─ NO → Use create_document (Report DocType, is_standard="No")
      │        Stored in DB, persists across rebuilds
      └─ YES → Use filesystem tools BUT warn the user:
               "This report uses libraries not available in safe_exec.
                It will work now but won't survive a Frappe Cloud rebuild.
                Consider backing it up to a git repo."
```

### Future: Git-Backed Custom App

The ideal long-term solution for Frappe Cloud is for `ensure_app` to:

1. Create the app locally  
2. Initialize a git repository  
3. Push to a configured remote (GitHub/GitLab)  
4. Add the repo URL to the bench's `apps.json`

This way the custom app survives rebuilds because Frappe Cloud pulls it from the git repo. This is not in the initial scope but is the natural evolution.

---

## Security Model

### Path Sandboxing

All file paths accepted by the tools are **relative to the bench `apps/` directory**. The tool resolves the full path internally and validates it:

```
User provides:  "fac_custom_code/fac_custom_code/my_module/report/my_report/my_report.py"
Tool resolves:  "/home/user/frappe-bench/apps/fac_custom_code/fac_custom_code/my_module/report/my_report/my_report.py"
```

**Security checks applied to every path:**

1. **Symlink resolution** — Uses `os.path.realpath()` (not `os.path.abspath()`) to resolve symlinks. This prevents symlink-escape attacks where a symlink inside `apps/` points to `/etc/` or another sensitive directory.  
2. **Boundary check** — The resolved path must start with the `apps/` directory. Any path traversal (e.g., `../../etc/passwd`) is rejected.  
3. **Null byte rejection** — Paths containing null bytes are rejected to prevent null byte injection.  
4. **Depth limit** — Paths with more than 10 directory levels are rejected as a sanity check.

### Protected App Blocklist

Write operations (`write_file`, `ensure_app`) check the target app name against a blocklist of standard Frappe ecosystem apps:

```py
PROTECTED_APPS = {"frappe", "erpnext", "hrms", "payments", "india_compliance", "lending", "education"}
```

Read operations (`read_file`, `list_app_files`, `describe_app`) do **not** enforce this blocklist. The AI needs to read standard app code to understand patterns and generate correct code.

### Permission Model

All Developer Tools require the **System Manager** role. This is enforced via an explicit role check at the start of each tool's `execute()` method, rather than through the `requires_permission` DocType mechanism (since there is no single DocType to gate on).

| Tool | Required Role | Rationale |
| :---- | :---- | :---- |
| `ensure_app` | System Manager | Creates apps, modifies apps.txt, runs install\_app |
| `write_file` | System Manager | Writes to filesystem |
| `read_file` | System Manager | Reads source code from filesystem |
| `list_app_files` | System Manager | Exposes filesystem structure |
| `describe_app` | System Manager | Exposes full app structure |

---

## Tool Details

### 1\. `ensure_app` — Create a Custom Frappe App

Creates a new Frappe app non-interactively if it doesn't already exist, and installs it on the current site. This is the first tool the AI should call before writing any code files.

#### How It Works

The standard `bench new-app` command is interactive — it prompts for app title, publisher, email, etc. The `ensure_app` tool bypasses this by:

1. **Scaffolding the app directory structure programmatically** — It reuses the template strings from `frappe.utils.boilerplate` (`hooks_template`, `init_template`, `pyproject_template`, `patches_template`) but fills in the values from the tool's input parameters instead of interactive prompts.  
     
2. **Registering the app with Frappe** — After creating the files:  
     
   - Adds the app name to `sites/apps.txt` (how Bench discovers apps)  
   - Calls `frappe.installer.install_app(app_name)` which:  
     - Creates Module Def documents in the database  
     - Syncs DocTypes from JSON files  
     - Marks all patches as complete  
     - Runs any `after_install` hooks

#### Directory Structure Created

```
apps/{app_name}/
├── {app_name}/
│   ├── __init__.py              # __version__ = "0.0.1"
│   ├── hooks.py                 # App metadata and configuration
│   ├── modules.txt              # Module list (one entry: app title)
│   ├── patches.txt              # Migration patches (empty sections)
│   ├── {app_title_scrubbed}/    # Default module directory
│   │   └── __init__.py
│   ├── templates/
│   │   ├── __init__.py
│   │   └── pages/
│   │       └── __init__.py
│   ├── templates/includes/
│   ├── config/
│   │   └── __init__.py
│   ├── public/
│   │   ├── css/
│   │   ├── js/
│   │   └── .gitkeep
│   └── www/
└── pyproject.toml               # Python package metadata
```

#### Input Parameters

| Parameter | Type | Default | Description |
| :---- | :---- | :---- | :---- |
| `app_name` | string | `"fac_custom_code"` | Snake\_case app name. Must match `^[a-z][a-z0-9_]*$` |
| `app_title` | string | Title-cased app\_name | Human-readable title |
| `app_description` | string | `"Custom code generated by Frappe Assistant"` | App description |

#### Return Value

```json
{
    "success": true,
    "app_name": "fac_custom_code",
    "app_path": "/home/user/frappe-bench/apps/fac_custom_code",
    "already_existed": false,
    "message": "App 'fac_custom_code' created and installed on site"
}
```

If the app already exists and is valid:

```json
{
    "success": true,
    "app_name": "fac_custom_code",
    "already_existed": true,
    "message": "App 'fac_custom_code' already exists"
}
```

#### Why a Default App Name?

The default app name `fac_custom_code` provides a single, predictable location for all AI-generated code. This simplifies:

- **Discovery** — Users know where to find AI-generated code  
- **Maintenance** — One app to manage, update, or remove  
- **Backup** — One directory to back up for custom code

---

### 2\. `write_file` — Write Code to the Filesystem

The core tool of the plugin. Writes content to a file within a custom Frappe app's directory structure. Creates intermediate directories as needed. **Automatically validates syntax for Python and JSON files.**

#### How It Works

1. Validates the path is within `apps/` and not targeting a protected app  
2. Creates any missing parent directories (e.g., for `report/my_report/my_report.py`, creates the `report/my_report/` directories)  
3. Writes the content to the file  
4. Sets appropriate file permissions (0o644 for files, 0o755 for directories)  
5. **Runs syntax validation** based on file extension (see below)

#### Inline Syntax Validation

After writing the file, `write_file` automatically validates its syntax based on the file extension. The file is **always written** (so the AI can inspect and fix it), but the validation result is included in the response.

| Extension | Validation Method | What It Catches |
| :---- | :---- | :---- |
| `.py` | `ast.parse(content)` | Syntax errors, indentation errors, invalid Python |
| `.json` | `json.loads(content)` | Malformed JSON, trailing commas, missing brackets |
| `.js` | *None (deferred)* | JS errors surface in the browser console |
| Other | *None* | No validation for HTML, CSS, txt, etc. |

**Why `ast.parse()` and not `py_compile`?**

- `ast.parse()` is pure parsing — it catches syntax errors without needing to write a `.pyc` file  
- It works on content strings directly (no temp file needed)  
- It's part of Python's stdlib with zero overhead

**Example response with validation error:**

```json
{
    "success": true,
    "file_path": "fac_custom_code/fac_custom_code/reports/report/my_report/my_report.py",
    "bytes_written": 1234,
    "created_new": true,
    "validation": {
        "valid": false,
        "language": "python",
        "error": "SyntaxError: unexpected indent (line 42, col 8)",
        "line": 42,
        "col": 8
    }
}
```

**Example response when validation passes:**

```json
{
    "success": true,
    "file_path": "...",
    "bytes_written": 1234,
    "created_new": true,
    "validation": {
        "valid": true,
        "language": "python"
    }
}
```

The AI can then use `read_file` to see the exact file content and `write_file` again with corrected code. This creates a self-correcting loop without human intervention.

#### Why No Separate Update Tool?

Updating an existing file uses the same `read_file` → `write_file(overwrite=true)` flow:

1. AI calls `read_file` to get current content  
2. AI modifies the content in its context  
3. AI calls `write_file` with `overwrite=true` to write the full file back

This is the same pattern used by every AI coding assistant (Cursor, Claude Code, GitHub Copilot). A separate "update" or "patch" tool adds complexity without meaningful benefit. If large-file partial edits become a bottleneck later, a `patch_file` tool (old\_string/new\_string replacement) can be added.

#### Input Parameters

| Parameter | Type | Default | Description |
| :---- | :---- | :---- | :---- |
| `file_path` | string | *required* | Path relative to `apps/` directory |
| `content` | string | *required* | File content to write (max 1MB) |
| `overwrite` | boolean | `true` | Whether to overwrite existing files |

#### Return Value

```json
{
    "success": true,
    "file_path": "fac_custom_code/fac_custom_code/custom_reports/report/my_report/my_report.py",
    "bytes_written": 1234,
    "created_new": true,
    "validation": {
        "valid": true,
        "language": "python"
    }
}
```

#### Example: Creating a Script Report

A Script Report requires 4 files. The AI would call `write_file` four times:

**1\. Report JSON metadata:**

```
file_path: "fac_custom_code/fac_custom_code/custom_reports/report/sales_summary/sales_summary.json"
content: {
    "doctype": "Report",
    "name": "Sales Summary",
    "report_name": "Sales Summary",
    "ref_doctype": "Sales Invoice",
    "report_type": "Script Report",
    "is_standard": "Yes",
    "module": "Custom Reports",
    "roles": [{"role": "Accounts User"}]
}
```

**2\. Python controller:**

```
file_path: "fac_custom_code/fac_custom_code/custom_reports/report/sales_summary/sales_summary.py"
content:
    import frappe

    def execute(filters=None):
        columns = [
            {"label": "Customer", "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 200},
            {"label": "Total", "fieldname": "total", "fieldtype": "Currency", "width": 150}
        ]
        data = frappe.db.sql("""
            SELECT customer, SUM(grand_total) as total
            FROM `tabSales Invoice`
            WHERE docstatus = 1
            GROUP BY customer
            ORDER BY total DESC
        """, as_dict=True)
        return columns, data
```

**3\. JavaScript filters:**

```
file_path: "fac_custom_code/fac_custom_code/custom_reports/report/sales_summary/sales_summary.js"
content:
    frappe.query_reports["Sales Summary"] = {
        filters: [
            {
                fieldname: "from_date",
                label: __("From Date"),
                fieldtype: "Date",
                default: frappe.datetime.add_months(frappe.datetime.get_today(), -1)
            },
            {
                fieldname: "to_date",
                label: __("To Date"),
                fieldtype: "Date",
                default: frappe.datetime.get_today()
            }
        ]
    };
```

**4\. Python init file:**

```
file_path: "fac_custom_code/fac_custom_code/custom_reports/report/sales_summary/__init__.py"
content: ""  (empty)
```

After writing these files, the user (or a future automation) would run `bench migrate` or clear cache to make the report visible in Frappe.

---

### 3\. `read_file` — Read Code from the Filesystem

Reads file contents from any Frappe app's directory. Essential for the AI to inspect existing code patterns before generating new code.

#### How It Works

1. Validates the path is within `apps/` (but does NOT check the protected app blocklist — reading is safe)  
2. Verifies the target is a regular file (not a directory, device, or socket)  
3. Checks file size (max 5MB)  
4. Reads and returns content, truncated to `max_lines` if the file is large

#### Input Parameters

| Parameter | Type | Default | Description |
| :---- | :---- | :---- | :---- |
| `file_path` | string | *required* | Path relative to `apps/` directory |
| `max_lines` | integer | `500` | Maximum number of lines to return |

#### Return Value

```json
{
    "success": true,
    "file_path": "erpnext/erpnext/stock/report/stock_analytics/stock_analytics.py",
    "content": "import frappe\n...",
    "lines": 150,
    "truncated": false,
    "size_bytes": 4521
}
```

#### Typical Use Case

The AI reads an existing Script Report from erpnext to understand the pattern, then generates a similar report for the user's custom requirement:

```
Step 1: read_file("erpnext/erpnext/stock/report/stock_analytics/stock_analytics.py")
Step 2: read_file("erpnext/erpnext/stock/report/stock_analytics/stock_analytics.js")
Step 3: Understand the pattern
Step 4: write_file(...) to create a new report following the same pattern
```

---

### 4\. `list_app_files` — Browse App Directory Structure

Lists files and directories within a Frappe app. Helps the AI understand the existing structure before creating new files.

#### How It Works

1. Validates the path is within `apps/`  
2. Lists directory contents using `os.listdir()` or `os.walk()` (for recursive listing)  
3. Filters out noise directories: `__pycache__`, `.git`, `node_modules`, `.egg-info`  
4. Optionally filters by glob pattern (e.g., `*.py`)

#### Input Parameters

| Parameter | Type | Default | Description |
| :---- | :---- | :---- | :---- |
| `path` | string | `""` | Directory path relative to `apps/`. Empty \= list all apps |
| `pattern` | string | *none* | Glob pattern filter (e.g., `"*.py"`, `"*.json"`) |
| `recursive` | boolean | `false` | List recursively (max 5 levels deep) |
| `max_results` | integer | `200` | Maximum entries to return |

#### Return Value

```json
{
    "success": true,
    "path": "fac_custom_code/fac_custom_code",
    "entries": [
        {"name": "__init__.py", "type": "file", "size": 42},
        {"name": "hooks.py", "type": "file", "size": 1024},
        {"name": "custom_reports", "type": "dir", "size": 0},
        {"name": "public", "type": "dir", "size": 0}
    ],
    "total": 4,
    "truncated": false
}
```

---

### 5\. `describe_app` — Full App Structure Tree for LLM Context

Provides the AI with a complete, structured view of a Frappe app's directory tree — similar to the Unix `tree` command but optimized for LLM consumption. This is the tool the AI should call first when it needs to understand an app's layout before making changes.

#### Why This Tool Exists

`list_app_files` is good for browsing one directory at a time, but the AI often needs a **full picture** of an app's structure in a single call — which modules exist, where reports live, what DocTypes are defined, etc. Without this, the AI would need multiple sequential `list_app_files` calls, wasting tool calls and context.

`describe_app` gives the AI everything it needs in one shot to:

- Know where to place new files (correct module, correct subdirectory)  
- Avoid creating duplicate modules or reports  
- Understand the app's conventions (naming patterns, module organization)  
- Provide informed suggestions ("You already have a `reports` module — should I add the new report there?")

#### How It Works

1. Validates the app exists in `apps/`  
2. Walks the app's directory tree (up to configurable depth)  
3. Filters out noise: `__pycache__`, `.git`, `node_modules`, `.egg-info`, `.pyc` files  
4. Generates a hierarchical tree structure  
5. Optionally annotates files with metadata (size, type classification)  
6. Parses `modules.txt` to identify registered modules  
7. Detects Frappe artifacts (DocTypes, Reports, Pages) from directory conventions

#### Input Parameters

| Parameter | Type | Default | Description |
| :---- | :---- | :---- | :---- |
| `app_name` | string | *required* | App name (e.g., `"fac_custom_code"`, `"erpnext"`) |
| `max_depth` | integer | `4` | Maximum directory depth to traverse |
| `include_metadata` | boolean | `true` | Include file sizes and artifact type annotations |

#### Return Value

```json
{
    "success": true,
    "app_name": "fac_custom_code",
    "app_title": "Fac Custom Code",
    "modules": ["Fac Custom Code"],
    "tree": "fac_custom_code/\n├── __init__.py\n├── hooks.py\n├── modules.txt\n├── patches.txt\n├── fac_custom_code/\n│   ├── __init__.py\n│   └── report/\n│       └── sales_summary/\n│           ├── __init__.py\n│           ├── sales_summary.json  [Report]\n│           ├── sales_summary.py    [Script Report Controller]\n│           └── sales_summary.js    [Report Filters]\n├── public/\n│   └── .gitkeep\n└── templates/\n    └── pages/",
    "summary": {
        "modules": 1,
        "doctypes": 0,
        "reports": 1,
        "pages": 0,
        "total_files": 12
    }
}
```

#### Artifact Detection

The tool recognizes Frappe directory conventions and annotates them:

| Directory Pattern | Detected As | Annotation |
| :---- | :---- | :---- |
| `*/doctype/*/` | DocType | `[DocType]` on .json, `[Controller]` on .py |
| `*/report/*/` | Report | `[Report]` on .json, `[Script Report Controller]` on .py |
| `*/page/*/` | Page | `[Page]` on .json |
| `*/print_format/*/` | Print Format | `[Print Format]` on .html |
| `*/workspace/` | Workspace | `[Workspace]` on .json |

#### Example Output (Tree Format)

```
fac_custom_code/
├── __init__.py (27 B)
├── hooks.py (1.2 KB)
├── modules.txt (16 B)
├── patches.txt (89 B)
├── fac_custom_code/                    ── Module: "Fac Custom Code"
│   ├── __init__.py
│   ├── doctype/
│   │   └── custom_setting/
│   │       ├── custom_setting.json     [DocType]
│   │       ├── custom_setting.py       [Controller]
│   │       └── __init__.py
│   └── report/
│       ├── sales_summary/
│       │   ├── sales_summary.json      [Report]
│       │   ├── sales_summary.py        [Script Report Controller]
│       │   ├── sales_summary.js        [Report Filters]
│       │   └── __init__.py
│       └── customer_aging/
│           ├── customer_aging.json      [Report]
│           ├── customer_aging.py        [Script Report Controller]
│           ├── customer_aging.js        [Report Filters]
│           └── __init__.py
├── config/
│   └── __init__.py
├── public/
│   ├── css/
│   ├── js/
│   └── .gitkeep
└── templates/
    ├── __init__.py
    └── pages/
        └── __init__.py
```

#### Comparison: `describe_app` vs `list_app_files`

| Aspect | `list_app_files` | `describe_app` |
| :---- | :---- | :---- |
| Scope | Single directory | Full app tree |
| Output | Flat list of entries | Hierarchical tree \+ annotations |
| Context | Browsing, searching | Understanding full app structure |
| Use case | "What's in this folder?" | "Show me the whole app layout" |
| When to use | Known path, looking for specific files | Starting a new task, need orientation |

---

## End-to-End Workflow

Here's the complete flow when a user asks the AI to create a Script Report:

```
User: "Create a Script Report that shows top customers by outstanding amount"

AI workflow:
│
├─ 1. ensure_app(app_name="fac_custom_code")
│     → App created (or already exists)
│
├─ 2. describe_app(app_name="fac_custom_code")
│     → Full tree: see modules, existing reports, understand structure
│
├─ 3. read_file("erpnext/erpnext/accounts/report/accounts_receivable/accounts_receivable.py")
│     → Study a similar existing report for patterns
│
├─ 4. write_file(".../__init__.py", content="")
│     → validation: {valid: true}
│
├─ 5. write_file(".../top_customers_outstanding.json", content="{...}")
│     → validation: {valid: true, language: "json"}
│
├─ 6. write_file(".../top_customers_outstanding.py", content="def execute(...)...")
│     → validation: {valid: true, language: "python"}
│     (If syntax error: AI reads error, fixes code, writes again)
│
├─ 7. write_file(".../top_customers_outstanding.js", content="frappe.query_reports[...]...")
│     → No JS validation (errors will surface in browser)
│
└─ 8. AI tells user: "Report created. Run 'bench migrate' or clear cache to see it."
```

---

## Frappe Cloud Compatibility

### Runtime Compatibility

The Developer Tools plugin is designed to run on Frappe Cloud:

- **No `bench` CLI calls** — All operations use Frappe's Python APIs (`frappe.installer.install_app()`, `frappe.clear_cache()`, etc.)  
- **No subprocess execution** — File operations use Python's built-in `os` and `io` modules  
- **Standard file permissions** — Files are created with 0o644 (readable by the web server)

### Persistence Limitations

On Frappe Cloud, filesystem-created apps and files **do not survive bench upgrades/redeployments** (new Docker container \= clean slate). See the [Deployment Strategies](#deployment-strategies-self-hosted-vs-frappe-cloud) section above for the dual approach.

For Frappe Cloud users who need persistent, complex reports (requiring full Python imports), the recommended path is:

1. Use Developer Tools to create and test locally  
2. Push the custom app to a git repository  
3. Add the git repo URL to the Frappe Cloud bench configuration  
4. The app will then survive redeployments

---

## Future Considerations

### Potential Additional Tools

These tools are not in the initial scope but could be added later:

- **`delete_file`** — Remove a file from a custom app (with safety confirmations)  
- **`create_module`** — Create a new Frappe module within an app (module directory \+ Module Def)  
- **`patch_file`** — Surgical old\_string/new\_string replacements for editing large files without rewriting them entirely  
- **`sync_app`** — Call `frappe.modules.utils.sync_for()` directly to sync DocTypes without a full migrate

### Beyond Script Reports

The same generic tools support creating:

- **Print Formats** — Custom print format HTML/CSS/Jinja files  
- **Workspace pages** — Custom workspace JSON definitions  
- **Custom Python modules** — Utility functions, API endpoints  
- **Fixtures** — Data fixtures for seeding/testing  
- **Patches** — Database migration patches  
- **Page files** — Custom Frappe pages with HTML/JS/CSS  
- **DocTypes** — Custom DocType JSON definitions with controllers

The tools are intentionally generic so that any file-based Frappe artifact can be created without needing a dedicated tool.  

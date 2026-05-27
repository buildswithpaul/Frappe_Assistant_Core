---
name: bench-tools
description: >
  Use this skill whenever the user wants to manage Frappe apps on the bench or export
  fixtures. Trigger on phrases like: "create an app", "install app", "uninstall app",
  "remove app from bench", "list apps", "list sites", "export fixtures", "export custom fields",
  "export property setters", "export server scripts", "export client scripts",
  "what apps do I have", "what sites do I have". This skill documents the exact workflow
  for bench_help and bench_execute tools - always load it before any bench operation.
---

# Frappe Bench Tools Skill

## Overview

Two MCP tools handle all bench and fixture operations:

- bench_help - call this FIRST. Returns all available actions and required parameters.
- bench_execute - executes the actual operation with the given action and parameters.

**Always call `bench_help` before `bench_execute`** if you are unsure what parameters are needed.

---

## Tools and Actions

### bench_help
No parameters needed. Returns the full list of available actions.

```python
bench_help()
# Returns all actions with descriptions and required params
```

### bench_execute
Single tool that handles all operations via the `action` parameter.

| Action | Description | Required Params |
|---|---|---|
| `list_apps` | Lists ALL bench apps AND site-installed apps separately | none |
| `list_sites` | Lists all available sites on this bench | none |
| `create_app` | Creates a new custom Frappe app on bench | `app_name` |
| `install_app` | Installs a bench app onto the current site | `app_name` |
| `uninstall_app` | Removes app from site only - keeps files on bench | `app_name` |
| `remove_app` | Permanently deletes app from bench entirely | `app_name` |
| `export_fixtures` | Exports DocType customizations as fixture JSON to an app | `app_name`, `doctype`, `filters` |

---

## Critical Rules - Read Before Every Operation

### Rule 1 - list_apps returns TWO separate lists
4
```json
{
  "bench_apps": ["app1", "app2", "app3"],   - apps that EXIST on disk
  "site_apps":  ["app1"]                    - apps INSTALLED on current site
}
```

An app can exist on bench but NOT be installed on site. Always show both lists clearly to the user.

### Rule 2 - export_fixtures requires ALL THREE parameters

Tool **fails immediately** if any are missing:
- `app_name` - which app to write fixtures into
- `doctype` - which DocType to export (must be from allowed list below)
- `filters` - which specific records to export (must be specific - never export everything)

**Never call export_fixtures without all three.** Ask user for missing params before calling.

### Rule 3 - Allowed DocTypes for export_fixtures only

| DocType | Filter Fields |
|---|---|
| `Custom Field` | `dt` |
| `Property Setter` | `doc_type`, `field_name` |
| `Client Script` | `dt`, `module` |
| `Server Script` | `name`, `module` |
| `Role` | `name` |
| `Workflow` | `document_type` |
| `Print Format` | `doc_type`, `module` |
| `Notification` | `document_type`, `module` |

If user asks to export any other DocType - inform them it is not supported.

### Rule 4 - remove_app handles FULL cleanup automatically

`remove_app` does everything in order:
1. Uninstalls from site (`frappe.installer.remove_app`)
2. Removes from DB installed_apps
3. pip uninstalls the package
4. Removes from `sites/apps.txt`
5. Deletes the app directory

**No need to call `uninstall_app` before `remove_app`** - it handles everything. Always show confirmation to user before proceeding.

### Rule 5 - create_app does NOT install on site

`create_app` only scaffolds the app directory on bench. It does NOT install it on the site.
After `create_app`, user must explicitly call `install_app` if they want it active on site.

### Rule 6 - Protected apps cannot be touched

These apps are protected and will be blocked:
`frappe`, `erpnext`, `hrms`, `payments`, `frappe_assistant_core`

---

## Exact Filter Formats by DocType

Always use the most specific filters possible. The more specific the filter, the fewer unnecessary records get exported.

### Custom Field
```json
{"dt": "Sales Invoice"}
{"dt": "Purchase Order"}
```

### Property Setter
```json
{"doc_type": "Sales Invoice"}
{"doc_type": "Sales Invoice", "field_name": "max_discount"}
```

### Client Script
```json
{"dt": "Sales Invoice"}
{"module": "Accounts"}
```

### Server Script
```json
{"name": ["in", ["get_reqDate_MR_SPQ", "set_default_time"]]}
{"module": "Accounts"}
```

### Role
```json
{"name": ["in", ["Accounts Manager", "Stock Manager"]]}
```

### Workflow
```json
{"document_type": "Purchase Order"}
```

### Print Format
```json
{"doc_type": "Sales Invoice"}
{"doc_type": "Sales Invoice", "module": "Accounts"}
```

### Notification
```json
{"document_type": "Sales Invoice"}
{"module": "Accounts"}
```

---

## Step-by-Step Workflows

### Check what apps exist on bench vs site
```python
bench_execute(action="list_apps")
# bench_apps = apps that exist on disk
# site_apps  = apps installed and active on current site
```

### Check available sites
```python
bench_execute(action="list_sites")
# Returns all sites that have a site_config.json
```

### Create a new app (bench only, not installed)
```python
bench_execute(action="create_app", app_name="my_custom_app")
# App is created on bench but NOT installed on site
```

### Create app and install on site (two steps)
```python
bench_execute(action="create_app", app_name="my_custom_app")
bench_execute(action="install_app", app_name="my_custom_app")
```

### Install an existing bench app onto site
```python
bench_execute(action="install_app", app_name="my_custom_app")
```

### Uninstall app from site (keep files on bench)
```python
bench_execute(action="uninstall_app", app_name="my_custom_app")
# App files still exist on bench - can reinstall anytime
```

### Remove app completely from bench
```python
bench_execute(action="remove_app", app_name="my_custom_app")
# Uninstalls from site + pip uninstall + deletes directory - PERMANENT
```

### Export Custom Field fixtures
```python
bench_execute(
    action="export_fixtures",
    app_name="my_custom_app",
    doctype="Custom Field",
    filters={"dt": "Sales Invoice"}
)
```

### Export Server Script fixtures by name
```python
bench_execute(
    action="export_fixtures",
    app_name="my_custom_app",
    doctype="Server Script",
    filters={"name": ["in", ["script_one", "script_two"]]}
)
```

### Create app then export fixtures (single user request)
```python
# Step 1
bench_execute(action="create_app", app_name="my_custom_app")
# Step 2
bench_execute(
    action="export_fixtures",
    app_name="my_custom_app",
    doctype="Custom Field",
    filters={"dt": "Sales Invoice"}
)
```

---

## Interaction Rules

1. **"What apps do I have"** - call `list_apps`, show bench_apps and site_apps separately with clear labels
2. **"What sites do I have"** - call `list_sites`
3. **"Create app" without name** - ask for app_name before calling tool
4. **"Install app" without specifying which** - call `list_apps` first, show bench_apps that are NOT in site_apps, ask user to pick
5. **"Export fixtures" without details** - ask for app_name, doctype, and filters before calling - do NOT call tool without all three
6. **"Remove app" without specifying which** - call `list_apps` first, show list, ask which one, then show confirmation
7. **"Remove app"** - always show confirmation warning before proceeding - removal is permanent and cannot be undone
8. **Multi-step request** (e.g. "create app and export fixtures to it") - execute steps sequentially without asking for confirmation between steps

---

## Common Errors and Fixes

### "MISSING REQUIRED PARAMETER: doctype"
**Cause:** Called export_fixtures without specifying DocType.
**Fix:** Always specify doctype. Example: `doctype="Custom Field"`

### "MISSING REQUIRED PARAMETER: filters"
**Cause:** Called export_fixtures without filters.
**Fix:** Always provide specific filters. Example: `filters={"dt": "Sales Invoice"}`

### "Cannot create or overwrite protected app"
**Cause:** Tried to create/remove a protected system app.
**Fix:** Only custom apps can be managed. Protected: frappe, erpnext, hrms, etc.

### "App is not installed on the current site"
**Cause:** Called uninstall_app on an app not currently installed on site.
**Fix:** Check site_apps from list_apps before uninstalling.

### "No module named 'app_name'"
**Cause:** App was deleted from disk but still registered in DB installed_apps (ghost app).
**Fix:** This is automatically cleaned when list_apps is called next time.

### "App already exists"
**Cause:** create_app called with a name that already exists on bench.
**Fix:** Tool returns `already_existed: true` and does nothing - safe to continue.

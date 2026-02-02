# Tool Management System Guide

## Overview

The Tool Management System in Frappe Assistant Core provides administrators with granular control over which AI assistant tools are available to users. This system allows you to:

- **Enable/Disable individual tools** - Control which tools are exposed to the MCP client
- **Configure role-based access** - Restrict specific tools to certain user roles
- **Categorize tools** - Understand tool capabilities through automatic category detection
- **Manage tool visibility** - Hide sensitive or experimental tools from users

## Key Components

### 1. FAC Tool Configuration DocType

Each tool has an individual configuration record that stores:

| Field | Description |
|-------|-------------|
| **Tool Name** | Unique identifier (e.g., `get_document`, `create_document`) |
| **Plugin Name** | The plugin providing this tool (e.g., `core`, `data_science`) |
| **Enabled** | Toggle to show/hide tool from MCP tools/list |
| **Tool Category** | Operation type: `read_only`, `write`, `read_write`, `privileged` |
| **Role Access Mode** | `Allow All` or `Restrict to Listed Roles` |
| **Role Access** | Child table of roles with access (when restricted) |

### 2. Tool Categories

Tools are automatically categorized based on their code analysis:

| Category | Color | Description | Example Tools |
|----------|-------|-------------|---------------|
| **Read Only** | 🟢 Green | Only reads data, no modifications | `get_document`, `list_documents`, `search_documents` |
| **Write** | 🟡 Yellow | Creates or modifies data | `create_document`, `update_document` |
| **Read & Write** | 🔵 Blue | Both reads and modifies data | Mixed operation tools |
| **Privileged** | 🟠 Orange | Elevated access - delete, execute code, run queries | `delete_document`, `run_python_code`, `query_and_analyze` |

### 3. FAC Tool Role Access (Child Table)

When using "Restrict to Listed Roles" mode, this child table specifies which roles can access the tool:

| Field | Description |
|-------|-------------|
| **Role** | Link to Frappe Role |
| **Allow Access** | Checkbox to grant access |

---

## User Guide

### Accessing Tool Management

1. Navigate to **FAC Admin** page (`/app/fac-admin`)
2. Click on the **Tools** tab to see all available tools
3. Or directly access the Tool Configuration list at `/app/fac-tool-configuration`

### Enabling/Disabling Tools

#### From FAC Admin Page

1. Go to **FAC Admin** → **Tools** tab
2. Find the tool you want to toggle
3. Click the **Enable/Disable** toggle
4. Changes take effect immediately

#### From Tool Configuration DocType

1. Navigate to `/app/fac-tool-configuration`
2. Click on the tool you want to configure
3. Toggle the **Enabled** checkbox
4. Click **Save**

#### Bulk Operations

##### From FAC Admin UI

The FAC Admin page provides bulk actions for enabling/disabling multiple tools by category:

1. Go to **FAC Admin** → **Individual Tools** tab
2. In the **Bulk Actions** bar at the top:
   - Select a **Category** (Read Only, Write, Read & Write, Privileged) or leave as "Select Category" for all
   - Optionally select a **Plugin** to filter by plugin
   - Click **Enable** or **Disable** to toggle all matching tools

**Examples:**
- Disable all privileged tools: Select "Privileged" → Click "Disable"
- Enable all read-only tools in core plugin: Select "Read Only" + "Core" → Click "Enable"
- Disable all tools in data_science plugin: Leave category empty + Select "Data Science" → Click "Disable"

##### Using the API - By Tool Names

To enable/disable specific tools by name:

```python
# Using the API
import frappe
from frappe_assistant_core.assistant_core.doctype.fac_tool_configuration.fac_tool_configuration import bulk_toggle_tools

# Disable multiple tools
result = bulk_toggle_tools(
    tool_names=["run_python_code", "query_and_analyze"],
    enabled=False
)
print(result)
# {'success': True, 'total': 2, 'success_count': 2, 'failures': [], 'message': '2 of 2 tools updated'}
```

##### Using the API - By Category

To enable/disable tools by category:

```python
from frappe_assistant_core.api.admin_api import bulk_toggle_tools_by_category

# Enable all read-only tools
result = bulk_toggle_tools_by_category(category="read_only", enabled=True)
# {'success': True, 'total': 12, 'toggled': [...], 'failed': [], 'message': '12 tools enabled'}

# Disable all privileged tools
result = bulk_toggle_tools_by_category(category="privileged", enabled=False)

# Disable all write tools in data_science plugin only
result = bulk_toggle_tools_by_category(
    category="write",
    enabled=False,
    plugin_name="data_science"
)

# Enable all tools in visualization plugin (any category)
result = bulk_toggle_tools_by_category(
    category=None,  # or omit this parameter
    enabled=True,
    plugin_name="visualization"
)
```

**Available Categories:**
- `read_only` - Tools that only read data
- `write` - Tools that create or modify data
- `read_write` - Tools that both read and modify data
- `privileged` - Tools with elevated access (delete, execute code, run queries)

### Configuring Role-Based Access

#### Restricting a Tool to Specific Roles

1. Open the tool configuration (e.g., `/app/fac-tool-configuration/delete_document`)
2. Change **Role Access Mode** to `Restrict to Listed Roles`
3. In the **Role Access** table, add the roles that should have access:
   - Click **Add Row**
   - Select the **Role** (e.g., `System Manager`)
   - Check **Allow Access**
4. Click **Save**

**Example: Restrict `delete_document` to System Manager only**

```
Tool Name: delete_document
Role Access Mode: Restrict to Listed Roles

Role Access:
┌─────────────────┬──────────────┐
│ Role            │ Allow Access │
├─────────────────┼──────────────┤
│ System Manager  │ ✓            │
└─────────────────┴──────────────┘
```

#### Allowing All Users

1. Set **Role Access Mode** to `Allow All`
2. The **Role Access** table will be hidden
3. All users can access the tool (subject to other permission checks)

### Understanding Tool Categories

#### Category Detection Hierarchy

The system uses a multi-layer detection approach (in order of priority):

```
1. Hardcoded Lists (fastest, most reliable)
   └── PRIVILEGED_TOOLS, READ_ONLY_TOOLS, WRITE_TOOLS in tool_category_detector.py

2. AST Code Analysis (automatic)
   └── Parses tool source code looking for perm_type="read", perm_type="write", etc.

3. Default Fallback
   └── If nothing detected → "read_write"
```

#### When Auto-Detection Works

If your tool uses standard Frappe permission patterns, the AST analyzer will detect the category automatically:

```python
# This will be detected as "read_only"
def execute(self, arguments):
    frappe.has_permission("Sales Invoice", perm_type="read")
    # or
    self.validate_document_access("Customer", "CUST-001", perm_type="read")

# This will be detected as "write"
def execute(self, arguments):
    frappe.has_permission("Sales Invoice", perm_type="write")
```

#### When to Use Hardcoded Lists

Add tools to the hardcoded lists in `tool_category_detector.py` when:

| Scenario | Action |
|----------|--------|
| Tool doesn't use `perm_type` in code | Add to hardcoded list |
| AST detection is incorrect | Add to override list |
| Tool does complex/mixed operations | Safer to hardcode |
| Critical tools (delete, execute code) | Always hardcode |

**Location:** `frappe_assistant_core/utils/tool_category_detector.py`

```python
PRIVILEGED_TOOLS = {"delete_document", "run_python_code", ...}
READ_ONLY_TOOLS = {"get_document", "list_documents", ...}
WRITE_TOOLS = {"create_document", "update_document", ...}
```

#### Manual Override via UI

If the auto-detection is incorrect and you don't want to modify code:

1. Open the tool configuration
2. Check **Category Manually Overridden**
3. Select the correct **Tool Category** from the dropdown
4. Click **Save**

The `auto_detected_category` field shows what the system detected, while `tool_category` shows the effective category.

---

## API Reference

### Check Tool Access

```python
from frappe_assistant_core.assistant_core.doctype.fac_tool_configuration.fac_tool_configuration import get_tool_access_status

# Check if current user can access a tool
result = get_tool_access_status("delete_document")
print(result)
# {
#     'tool_name': 'delete_document',
#     'user': 'user@example.com',
#     'has_access': True,
#     'enabled': True,
#     'role_access_mode': 'Allow All',
#     'tool_category': 'privileged'
# }
```

### Toggle a Single Tool

```python
from frappe_assistant_core.assistant_core.doctype.fac_tool_configuration.fac_tool_configuration import toggle_tool

# Disable a tool
result = toggle_tool("run_python_code", enabled=False)
print(result)
# {'success': True, 'tool_name': 'run_python_code', 'enabled': 0, 'message': "Tool 'run_python_code' disabled"}
```

### Bulk Toggle Tools

```python
from frappe_assistant_core.assistant_core.doctype.fac_tool_configuration.fac_tool_configuration import bulk_toggle_tools

# Enable multiple tools
result = bulk_toggle_tools(
    tool_names=["get_document", "list_documents", "search_documents"],
    enabled=True
)
```

### Get Category Information

```python
from frappe_assistant_core.utils.tool_category_detector import get_category_info

info = get_category_info("privileged")
print(info)
# {
#     'label': 'Privileged',
#     'color': 'orange',
#     'icon': 'fa-shield-alt',
#     'description': 'This tool has elevated access - can delete data, execute code, or run database queries'
# }
```

---

## Best Practices

### Security Recommendations

1. **Restrict privileged tools** - Tools like `run_python_code`, `query_and_analyze`, and `delete_document` should be restricted to trusted roles only

2. **Review tool access regularly** - Periodically audit which roles have access to which tools

3. **Use category-based policies** - Consider disabling all `privileged` category tools for non-admin users

4. **Test access changes** - After modifying role access, test with a user in that role to confirm the expected behavior

### Performance Considerations

1. **Cache invalidation** - Tool configuration changes automatically clear relevant caches

2. **Batch operations** - Use `bulk_toggle_tools()` for multiple changes instead of individual calls

3. **Auto-sync on migrate** - New tools are automatically discovered and configured during `bench migrate`

### Common Scenarios

#### Scenario 1: Disable Code Execution for All Non-Admins

```python
# Restrict run_python_code to System Manager only
config = frappe.get_doc("FAC Tool Configuration", "run_python_code")
config.role_access_mode = "Restrict to Listed Roles"
config.role_access = []
config.append("role_access", {"role": "System Manager", "allow_access": 1})
config.save()
```

#### Scenario 2: Enable Only Read Tools for a New Role

```python
# Get all read_only tools
read_only_tools = frappe.get_all(
    "FAC Tool Configuration",
    filters={"tool_category": "read_only"},
    pluck="tool_name"
)

# Configure each to allow the new role
for tool_name in read_only_tools:
    config = frappe.get_doc("FAC Tool Configuration", tool_name)
    config.role_access_mode = "Restrict to Listed Roles"
    config.append("role_access", {"role": "Data Analyst", "allow_access": 1})
    config.append("role_access", {"role": "System Manager", "allow_access": 1})
    config.save()
```

#### Scenario 3: Disable All Visualization Tools

```python
# Get tools from visualization plugin
viz_tools = frappe.get_all(
    "FAC Tool Configuration",
    filters={"plugin_name": "visualization"},
    pluck="tool_name"
)

# Disable all
from frappe_assistant_core.assistant_core.doctype.fac_tool_configuration.fac_tool_configuration import bulk_toggle_tools
bulk_toggle_tools(viz_tools, enabled=False)
```

---

## Troubleshooting

### Tool Not Appearing in MCP tools/list

1. **Check if tool is enabled** - Verify `enabled = 1` in FAC Tool Configuration
2. **Check plugin status** - Ensure the parent plugin is enabled in FAC Plugin Configuration
3. **Check role access** - If using restricted mode, verify your role is in the list
4. **Clear cache** - Run `bench clear-cache` to refresh tool registry

### Tool Access Denied

1. **Check role_access_mode** - Verify it's set correctly
2. **Check role membership** - Ensure user has the required role
3. **Check tool enabled** - Disabled tools always deny access
4. **Check plugin enabled** - Tools from disabled plugins are not accessible

### Category Not Detecting Correctly

1. **Check hardcoded lists** - Some tools are pre-categorized in `tool_category_detector.py`
2. **Use manual override** - Check "Category Manually Overridden" and select the correct category
3. **Check source code** - Ensure `perm_type` is used consistently in the tool's execute method

### Changes Not Taking Effect

1. **Clear caches** - Tool configurations clear caches automatically, but try `bench clear-cache`
2. **Refresh plugin manager** - Use `refresh_plugin_manager()` to reload all tools
3. **Check database** - Verify the change was saved using `frappe.get_doc()`

---

## Integration with Plugin System

Tool Management works in conjunction with the Plugin Management System:

```
┌─────────────────────────────────────┐
│      FAC Plugin Configuration       │
│  (Plugin-level enable/disable)      │
└──────────────────┬──────────────────┘
                   │
                   │ Plugin must be enabled
                   ▼
┌─────────────────────────────────────┐
│      FAC Tool Configuration         │
│  (Tool-level enable/disable)        │
│  (Role-based access control)        │
└──────────────────┬──────────────────┘
                   │
                   │ Tool must be enabled + role access
                   ▼
┌─────────────────────────────────────┐
│         MCP tools/list              │
│  (Final list exposed to client)     │
└─────────────────────────────────────┘
```

**Key Points:**
- If a **plugin is disabled**, all its tools are hidden (regardless of tool configuration)
- If a **tool is disabled**, it's hidden even if the plugin is enabled
- **Role access** is checked after enable/disable status
- **System Manager** always has access to all enabled tools

---

## Automatic Sync on Bench Migrate

When you run `bench migrate`, the system automatically syncs tool and plugin configurations:

### What Happens on Migrate

| Action | Behavior |
|--------|----------|
| **New tool added** | Creates FAC Tool Configuration with `enabled=1` |
| **Tool removed** | Deletes orphan FAC Tool Configuration record |
| **New plugin added** | Creates FAC Plugin Configuration |
| **Plugin removed** | Deletes orphan FAC Plugin Configuration record |
| **Existing configs** | Preserved (user changes are NOT overwritten) |

### Sync Flow

```
bench migrate
    │
    ├── _sync_plugin_configurations()
    │   ├── Discover plugins from /plugins/ directory
    │   ├── Create FAC Plugin Configuration for new plugins
    │   └── Delete orphan configs for removed plugins
    │
    └── _sync_tool_configurations()
        ├── Discover tools from enabled plugins
        ├── Discover external tools from assistant_tools hook
        ├── Create FAC Tool Configuration for new tools
        ├── Auto-detect tool categories
        └── Delete orphan configs for removed tools
```

### External/Custom Tools

Tools from external Frappe apps are discovered via the `assistant_tools` hook:

```python
# your_app/hooks.py
assistant_tools = [
    "your_app.assistant_tools.my_tool.MyTool",
]
```

**Important:** External tools require the `custom_tools` plugin to be enabled:
- External tools are assigned `plugin_name = "custom_tools"`
- If `custom_tools` plugin is disabled, external tools won't load
- The plugin is auto-created on `bench migrate` if it doesn't exist

---

## Version History

| Version | Changes |
|---------|---------|
| **2.2.0** | Initial release of Tool Management System |
| | - FAC Tool Configuration DocType |
| | - FAC Tool Role Access child table |
| | - Automatic category detection |
| | - Role-based access control |
| | - Auto-sync on bench migrate |

---

## Related Documentation

- [Plugin Management Guide](./PLUGIN_MANAGEMENT_GUIDE.md) - Managing plugins
- [Tool Reference](../api/TOOL_REFERENCE.md) - Complete tool documentation
- [Architecture Overview](../architecture/ARCHITECTURE.md) - System architecture
- [Security Framework](../architecture/TECHNICAL_DOCUMENTATION.md#security-framework) - Security details

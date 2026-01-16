# Plugin Management System Guide

## Overview

The Plugin Management System in Frappe Assistant Core provides a modular architecture for organizing AI assistant tools into logical groups that can be enabled or disabled as needed. This system ensures:

- **Atomic state persistence** - Plugin states are stored individually for reliability
- **Multi-worker consistency** - Safe operation in Gunicorn production environments
- **Automatic discovery** - New plugins are detected and configured automatically
- **Clean separation** - Core functionality is always available, optional features can be toggled

## Key Components

### 1. FAC Plugin Configuration DocType

Each plugin has an individual configuration record:

| Field | Description |
|-------|-------------|
| **Plugin Name** | Unique identifier (e.g., `core`, `data_science`, `visualization`) |
| **Display Name** | Human-readable name (e.g., "Core", "Data Science") |
| **Enabled** | Toggle to enable/disable the plugin |
| **Description** | Plugin description |
| **Discovered At** | When the plugin was first discovered |
| **Last Toggled At** | When the plugin was last enabled/disabled |

### 2. Available Plugins

| Plugin | Status | Description | Tools |
|--------|--------|-------------|-------|
| **Core** | Always Enabled | Essential Frappe operations (CRUD, search, metadata) | 19 tools |
| **Data Science** | Optional | Advanced analytics, Python execution, file processing | 4 tools |
| **Visualization** | Optional | Dashboard and chart creation, KPIs | 3 tools |
| **WebSocket** | Optional | Real-time communication (under development) | - |
| **Batch Processing** | Optional | Background bulk operations (under development) | - |

### 3. Plugin Architecture

```
plugins/
├── core/                  # Always enabled
│   ├── plugin.py          # Plugin definition
│   └── tools/             # Core tools
│       ├── document_create.py
│       ├── document_get.py
│       └── ...
├── data_science/          # Optional
│   ├── plugin.py
│   └── tools/
│       ├── analyze_frappe_data.py
│       └── execute_python_code.py
├── visualization/         # Optional
│   ├── plugin.py
│   └── tools/
│       ├── create_dashboard.py
│       └── create_chart.py
└── base_plugin.py         # Base class
```

---

## User Guide

### Accessing Plugin Management

1. Navigate to **FAC Admin** page (`/app/fac-admin`)
2. The **Plugins** section shows all available plugins
3. Or directly access the Plugin Configuration list at `/app/fac-plugin-configuration`

### Enabling/Disabling Plugins

#### From FAC Admin Page

1. Go to **FAC Admin** page
2. Find the plugin in the **Plugins** section
3. Toggle the **Enable/Disable** switch
4. Changes take effect immediately

#### From Plugin Configuration DocType

1. Navigate to `/app/fac-plugin-configuration`
2. Click on the plugin you want to configure
3. Toggle the **Enabled** checkbox
4. Click **Save**

#### Using the API

```python
from frappe_assistant_core.api.admin_api import toggle_plugin

# Enable a plugin
result = toggle_plugin(plugin_name="visualization", enable=True)
print(result)
# {'success': True, 'message': "Plugin 'visualization' enabled."}

# Disable a plugin
result = toggle_plugin(plugin_name="data_science", enable=False)
print(result)
# {'success': True, 'message': "Plugin 'data_science' disabled."}
```

### Viewing Plugin Status

#### Get All Plugin Statistics

```python
from frappe_assistant_core.api.admin_api import get_plugin_stats

stats = get_plugin_stats()
print(stats)
# {
#     'total_plugins': 5,
#     'enabled_plugins': 3,
#     'disabled_plugins': 2,
#     'plugins': [
#         {'name': 'core', 'display_name': 'Core', 'enabled': True, 'tool_count': 19},
#         {'name': 'visualization', 'display_name': 'Visualization', 'enabled': True, 'tool_count': 3},
#         ...
#     ]
# }
```

#### Get Individual Plugin Configuration

```python
import frappe

config = frappe.get_doc("FAC Plugin Configuration", "data_science")
print(f"Plugin: {config.display_name}")
print(f"Enabled: {config.enabled}")
print(f"Last toggled: {config.last_toggled_at}")
```

---

## How It Works

### State Persistence Architecture

Plugin states are stored in the **FAC Plugin Configuration** DocType with individual records per plugin:

```
┌─────────────────────────────────────────────────┐
│            FAC Plugin Configuration             │
├─────────────────────────────────────────────────┤
│ plugin_name: "core"                             │
│ enabled: 1                                      │
│ display_name: "Core"                            │
│ last_toggled_at: 2025-01-14 10:30:00            │
├─────────────────────────────────────────────────┤
│ plugin_name: "visualization"                    │
│ enabled: 0                                      │
│ display_name: "Visualization"                   │
│ last_toggled_at: 2025-01-14 09:15:00            │
├─────────────────────────────────────────────────┤
│ plugin_name: "data_science"                     │
│ enabled: 1                                      │
│ display_name: "Data Science"                    │
│ last_toggled_at: 2025-01-14 08:00:00            │
└─────────────────────────────────────────────────┘
```

**Benefits of this architecture:**
- **Atomic updates** - Single row UPDATE instead of read-modify-write JSON
- **Multi-worker safe** - No race conditions in Gunicorn environments
- **Proper caching** - Works with Frappe's document cache patterns
- **Audit trail** - Built-in `track_changes` for modification history

### Plugin Discovery Flow

```
┌─────────────────────────────┐
│     bench migrate           │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│   PluginDiscovery           │
│   Scans plugins/ directory  │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  _sync_plugin_configurations│
│  Creates missing FAC Plugin │
│  Configuration records      │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│   PluginManager             │
│   Loads enabled plugins     │
│   Registers tools           │
└─────────────────────────────┘
```

### Cache Invalidation

When a plugin is toggled, the following caches are cleared:

1. **Plugin-specific cache** - `fac_plugin_config_{plugin_name}`
2. **All plugins cache** - `fac_plugin_configurations`
3. **Tool registry cache** - `plugin_*`, `tool_registry_*`
4. **Document cache** - Frappe's document cache for the configuration

This ensures all Gunicorn workers see the updated state.

---

## API Reference

### PluginManager Class

```python
from frappe_assistant_core.utils.plugin_manager import get_plugin_manager

pm = get_plugin_manager()

# Get all discovered plugins
discovered = pm.get_discovered_plugins()

# Get enabled plugin names
enabled = pm.get_enabled_plugins()  # Returns Set[str]

# Get all loaded tools from enabled plugins
tools = pm.get_all_tools()  # Returns Dict[str, ToolInfo]

# Enable a plugin
pm.enable_plugin("visualization")

# Disable a plugin
pm.disable_plugin("data_science")

# Refresh all plugins (re-discover and reload)
pm.refresh_plugins()
```

### PluginPersistence Class

```python
from frappe_assistant_core.utils.plugin_manager import PluginPersistence

persistence = PluginPersistence()

# Load enabled plugins from database
enabled_set = persistence.load_enabled_plugins()

# Save a single plugin's state (atomic operation)
persistence.save_plugin_state("visualization", enabled=True)
```

### Admin API Functions

```python
from frappe_assistant_core.api.admin_api import (
    toggle_plugin,
    get_plugin_stats,
    get_all_plugins,
)

# Toggle plugin
toggle_plugin(plugin_name="visualization", enable=True)

# Get statistics
stats = get_plugin_stats()

# Get all plugins with details
plugins = get_all_plugins()
```

---

## Best Practices

### Security Recommendations

1. **Keep core plugin enabled** - Core provides essential document operations
2. **Disable data_science in production** - Unless needed, as it includes `execute_python_code`
3. **Review plugin tools** - Check what tools each plugin provides before enabling

### Performance Considerations

1. **Minimize enabled plugins** - Each plugin adds tools to the registry
2. **Use refresh sparingly** - `refresh_plugins()` reloads all plugins
3. **Rely on auto-sync** - Let `bench migrate` handle new plugin discovery

### Common Scenarios

#### Scenario 1: Production Setup with Minimal Tools

```python
# Enable only core and visualization
from frappe_assistant_core.api.admin_api import toggle_plugin

toggle_plugin("core", True)        # Always enabled anyway
toggle_plugin("visualization", True)
toggle_plugin("data_science", False)
toggle_plugin("websocket", False)
toggle_plugin("batch_processing", False)
```

#### Scenario 2: Development Setup with All Features

```python
# Enable all plugins for development
import frappe

configs = frappe.get_all("FAC Plugin Configuration", pluck="plugin_name")
for plugin in configs:
    frappe.db.set_value("FAC Plugin Configuration", plugin, "enabled", 1)
frappe.db.commit()
```

#### Scenario 3: Check Plugin Health

```python
from frappe_assistant_core.utils.plugin_manager import get_plugin_manager

pm = get_plugin_manager()
plugins = pm.get_discovered_plugins()

for plugin in plugins:
    status = "✓ Enabled" if plugin['loaded'] else "✗ Disabled"
    error = f" (Error: {plugin['validation_error']})" if plugin.get('validation_error') else ""
    print(f"{plugin['display_name']}: {status}{error}")
```

---

## Troubleshooting

### Plugin Not Loading

1. **Check plugin.py exists** - Each plugin needs a `plugin.py` file
2. **Check for syntax errors** - Python errors prevent plugin discovery
3. **Check validation** - Plugin's `validate_environment()` may be failing
4. **Check logs** - Review `frappe.log` for plugin errors

### Plugin Toggle Not Persisting

1. **Check database** - Verify FAC Plugin Configuration record exists
2. **Check cache** - Run `bench clear-cache` and retry
3. **Check worker sync** - In multi-worker, all workers should see the change
4. **Check migration** - Run `bench migrate` to ensure DocType exists

### Tools Not Appearing After Enable

1. **Clear tool registry cache** - Cache may have stale data
2. **Refresh plugin manager** - Use `refresh_plugin_manager()`
3. **Check tool configurations** - Individual tools may be disabled
4. **Check plugin state** - Verify plugin is actually enabled

### Duplicate Plugin Records

This shouldn't happen as `plugin_name` is unique, but if it does:

```python
# Clean up duplicates (keep most recent)
import frappe

duplicates = frappe.db.sql("""
    SELECT plugin_name, COUNT(*) as cnt
    FROM `tabFAC Plugin Configuration`
    GROUP BY plugin_name
    HAVING cnt > 1
""", as_dict=True)

for dup in duplicates:
    # Keep only the most recently modified
    records = frappe.get_all(
        "FAC Plugin Configuration",
        filters={"plugin_name": dup.plugin_name},
        order_by="modified desc"
    )
    for record in records[1:]:  # Skip first (most recent)
        frappe.delete_doc("FAC Plugin Configuration", record.name)
```

---

## Automatic Sync on Bench Migrate

When you run `bench migrate`, the system automatically syncs plugin and tool configurations:

### What Happens on Migrate

| Action | Behavior |
|--------|----------|
| **New plugin discovered** | Creates FAC Plugin Configuration (enabled by default) |
| **Plugin removed** | Deletes orphan FAC Plugin Configuration record |
| **Existing configs** | Preserved (user changes are NOT overwritten) |
| **New tools in plugin** | Creates FAC Tool Configuration for each tool |
| **Tools removed** | Deletes orphan FAC Tool Configuration records |

### Sync Flow

```
bench migrate
    │
    ├── _sync_plugin_configurations()
    │   ├── Scan /plugins/ directory for plugin.py files
    │   ├── Create FAC Plugin Configuration for new plugins
    │   ├── Preserve existing enabled/disabled states
    │   └── Delete orphan configs for removed plugins
    │
    └── _sync_tool_configurations()
        ├── Get tools from all discovered plugins
        ├── Get external tools from assistant_tools hook
        ├── Create FAC Tool Configuration for new tools
        ├── Auto-detect tool categories using AST analysis
        └── Delete orphan configs for removed tools
```

### Orphan Cleanup

When plugins or tools are removed from the codebase:
- Their configuration records are automatically deleted on next `bench migrate`
- This keeps the database clean and avoids confusion
- Log messages indicate what was removed

---

## Migration from Legacy JSON

If you're upgrading from a version that used JSON storage in `Assistant Core Settings`, the migration is automatic:

1. **Run `bench migrate`** - This triggers the migration patch
2. **Verify records** - Check `/app/fac-plugin-configuration` for plugin records
3. **Legacy field preserved** - The old JSON field remains for rollback safety

The migration patch reads the legacy `enabled_plugins_list` JSON and creates individual FAC Plugin Configuration records.

---

## Integration with Tool Management

Plugin Management works in conjunction with the Tool Management System:

```
┌─────────────────────────────────────┐
│      FAC Plugin Configuration       │
│  (Plugin-level enable/disable)      │
└──────────────────┬──────────────────┘
                   │
                   │ Plugin enabled?
                   ▼
┌─────────────────────────────────────┐
│      FAC Tool Configuration         │
│  (Tool-level enable/disable)        │
│  (Role-based access control)        │
└──────────────────┬──────────────────┘
                   │
                   │ Tool enabled + role access?
                   ▼
┌─────────────────────────────────────┐
│         MCP tools/list              │
│  (Final list exposed to client)     │
└─────────────────────────────────────┘
```

**Key Points:**
- **Plugin disabled** → All its tools are hidden
- **Plugin enabled + Tool disabled** → Specific tool hidden
- **Both enabled + Role restricted** → Access depends on user role

---

## Version History

| Version | Changes |
|---------|---------|
| **2.2.0** | Migrated from JSON to FAC Plugin Configuration DocType |
| | - Atomic plugin state updates |
| | - Multi-worker consistency |
| | - Automatic cache invalidation |
| | - Auto-sync on bench migrate |
| **2.0.0** | Initial plugin architecture |
| | - Plugin discovery system |
| | - Enable/disable functionality |

---

## Related Documentation

- [Tool Management Guide](./TOOL_MANAGEMENT_GUIDE.md) - Managing individual tools
- [Plugin Development Guide](../development/PLUGIN_DEVELOPMENT.md) - Creating new plugins
- [Architecture Overview](../architecture/ARCHITECTURE.md) - System architecture
- [Technical Documentation](../architecture/TECHNICAL_DOCUMENTATION.md) - Implementation details

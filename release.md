# Frappe Assistant Core v2.3.1

> Database-backed plugin & tool management with Frappe V16 support

## What's New

This release introduces a robust, database-backed system for managing plugin and tool enable/disable states and access control. It replaces the previous JSON-based approach with new DocTypes for granular, atomic, and multi-worker-safe configuration. Frappe V16 is now officially supported.

---

### Plugin & Tool Management Architecture

#### FAC Plugin Configuration DocType
A new DocType for atomic, database-backed plugin enable/disable control with:
- Audit trail for every state change
- Automatic cache invalidation for multi-worker consistency
- API functions for toggling and querying plugin states programmatically

#### FAC Tool Configuration DocType
A new DocType for per-tool configuration and access control with:
- Enable/disable toggle for individual tools
- Category assignment (`read_only`, `write`, `read_write`, `privileged`)
- Role-based access control via `FAC Tool Role Access` child table
- Automatic tool category detection via AST parsing of tool source code

#### Why This Matters

| Before (JSON) | After (DocType) |
|---|---|
| File-based state, prone to corruption | Atomic database writes |
| No change history | Full audit trail with timestamps and users |
| Stale reads across workers | Cache invalidation ensures consistency |
| Race conditions under load | Database locks prevent conflicts |
| File I/O bottleneck | Scales with your database |

---

### Frappe V16 Support
- Official support for **Frappe V16** alongside V15
- Conditional OAuth settings UI based on Frappe version
- Full backward compatibility with V15 installations

---

### Documentation Updates
- Updated architecture docs describing the new DocType-based configuration system
- Administrator guide for tool and plugin management
- Developer documentation for automatic tool category detection with examples and best practices
- Updated main documentation index for easier navigation

---

### Other Improvements
- Copyright and license headers added to new and updated modules
- Improved state persistence flow: UI → API → DocType → Cache Invalidation → Consistent reads

---

## Upgrade Guide

```bash
cd apps/frappe_assistant_core
git pull
bench --site your-site migrate
```

Migration will automatically:
- Create `FAC Plugin Configuration` records for existing plugins
- Create `FAC Tool Configuration` records for registered tools
- Auto-detect tool categories via AST parsing

---

## Compatibility

| Frappe Version | Supported |
|---|---|
| V15 | Yes |
| V16 | Yes (new) |
| V14 and below | No |

**Python**: >= 3.8

---

## Full Changelog

See [CHANGELOG.md](CHANGELOG.md) for the complete list of changes.

**Full Diff**: [`v2.3.0...v2.3.1`](https://github.com/buildswithpaul/Frappe_Assistant_Core/compare/v2.3.0...v2.3.1)

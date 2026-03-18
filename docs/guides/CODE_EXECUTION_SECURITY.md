# Code Execution Security Guide

This guide explains the security measures in place for the `run_python_code` tool, which allows AI agents to execute Python code in a sandboxed environment.

## Overview

The `run_python_code` tool provides a powerful capability for AI agents to perform data analysis, calculations, and report generation. However, this power comes with significant security risks. This guide documents the safeguards implemented to prevent system crashes and security breaches.

## Resource Limits

### Execution Timeout

**Purpose:** Prevents infinite loops and runaway code from blocking server resources indefinitely.

**How it works:**
- Uses Unix signals (`SIGALRM`) to enforce a wall-clock timeout
- Code execution is terminated after the specified number of seconds
- Default: 30 seconds, Maximum: 300 seconds (5 minutes)

**Configuration:**
```
Assistant Core Settings → Security → Execution Timeout (seconds)
```

**What happens when exceeded:**
```
⏱️ Execution Timeout: Code execution timed out...

💡 Tips to fix this:
   • Reduce the size of data being processed
   • Add early termination conditions to loops
   • Use more efficient algorithms
   • Break complex operations into smaller steps
```

### Memory Limit

**Purpose:** Prevents memory exhaustion attacks that could crash the server or trigger the OOM killer.

**How it works:**
- Uses the `resource` module (`RLIMIT_AS`) to cap virtual memory
- Memory allocation beyond the limit raises a `MemoryError`
- Default: 512 MB, Range: 64-2048 MB

**Configuration:**
```
Assistant Core Settings → Security → Max Memory (MB)
```

**What happens when exceeded:**
```
💾 Memory Limit Exceeded: The code attempted to use more memory than allowed.

Maximum allowed memory: 512 MB

💡 Tips to fix this:
   • Process data in smaller batches
   • Use generators instead of loading all data into memory
   • Delete intermediate variables when no longer needed
   • Use more memory-efficient data structures
```

### CPU Time Limit

**Purpose:** Limits actual CPU processing time (not wall-clock time), preventing CPU-intensive operations from starving other processes.

**How it works:**
- Uses the `resource` module (`RLIMIT_CPU`) to cap CPU time
- Complements wall-clock timeout for CPU-bound operations
- Default: 60 seconds, Range: 1-300 seconds

**Configuration:**
```
Assistant Core Settings → Security → Max CPU Time (seconds)
```

### Recursion Depth Limit

**Purpose:** Prevents stack overflow from deeply recursive code.

**How it works:**
- Temporarily lowers Python's recursion limit during code execution
- Catches `RecursionError` with helpful guidance
- Default: 100, Range: 50-500

**Configuration:**
```
Assistant Core Settings → Security → Max Recursion Depth
```

**What happens when exceeded:**
```
🔄 Recursion Limit Exceeded: The code exceeded the maximum recursion depth.

Maximum recursion depth: 100

💡 Tips to fix this:
   • Convert recursive algorithms to iterative ones
   • Add proper base cases to recursive functions
   • Use tail recursion optimization where possible
   • Check for infinite recursion in your code
```

### Output Truncation

**Purpose:** Prevents memory issues from extremely large output strings.

**How it works:**
- Output (stdout/stderr) is truncated at 1 MB
- Truncation indicator added when limit is reached

**Example truncated output:**
```
... [OUTPUT TRUNCATED - exceeded 1024KB limit. Original size: 5120KB]
```

## Code Security Scanning

Before execution, all code is scanned for dangerous patterns:

### Blocked Operations

| Category | Blocked Patterns | Reason |
|----------|-----------------|--------|
| **SQL Injection** | `DELETE`, `DROP`, `INSERT`, `UPDATE`, `ALTER`, `CREATE`, `TRUNCATE` in db.sql() | Prevents data modification |
| **Code Injection** | `exec()`, `eval()`, `compile()`, `__import__()` | Prevents arbitrary code execution |
| **Framework Tampering** | `setattr(frappe, ...)`, `frappe.local.x = ...` | Prevents framework modification |
| **File System** | `open()`, `file()` | Prevents file access |
| **Network** | `urllib`, `requests`, `socket`, `http` | Prevents network access |
| **User Input** | `input()`, `raw_input()` | Prevents interactive input |

### Read-Only Database

The `db` object provided in the sandbox is a read-only wrapper:

**Allowed operations:**
- `db.sql("SELECT ...")` - Read queries only
- `db.get_value()`, `db.get_all()`, `db.get_list()`
- `db.exists()`, `db.count()`
- Schema inspection: `db.describe()`, `db.get_table_columns()`

**Blocked operations:**
- `db.sql("DELETE ...")`, `db.sql("UPDATE ...")`
- `db.set_value()`, `db.delete()`, `db.insert()`
- Any write operation

## Platform Compatibility

| Feature | Linux | macOS | Windows |
|---------|-------|-------|---------|
| Timeout (SIGALRM) | ✅ | ✅ | ❌ |
| Memory Limit (RLIMIT_AS) | ✅ | ✅ | ❌ |
| CPU Time Limit (RLIMIT_CPU) | ✅ | ✅ | ❌ |
| Recursion Limit | ✅ | ✅ | ✅ |
| Code Security Scan | ✅ | ✅ | ✅ |
| Read-Only Database | ✅ | ✅ | ✅ |

**Note:** On Windows, resource limits (timeout, memory, CPU) are not enforced due to OS limitations. Code security scanning and the read-only database wrapper work on all platforms.

## Configuring Limits

### Via Settings UI

1. Go to **Assistant Core Settings**
2. Navigate to the **Security** tab
3. Adjust the execution limits as needed
4. Save changes (effective immediately for new executions)

### Via Code/API

```python
import frappe

settings = frappe.get_doc("Assistant Core Settings")
settings.code_execution_timeout = 60  # seconds
settings.code_execution_max_memory_mb = 1024  # MB
settings.code_execution_max_cpu_seconds = 120  # seconds
settings.code_execution_max_recursion = 200  # depth
settings.save()
```

### Default Values

| Setting | Default | Minimum | Maximum |
|---------|---------|---------|---------|
| Execution Timeout | 30 sec | 1 sec | 300 sec |
| Max Memory | 512 MB | 64 MB | 2048 MB |
| Max CPU Time | 60 sec | 1 sec | 300 sec |
| Max Recursion | 100 | 50 | 500 |

## Best Practices

### For Administrators

1. **Start with conservative limits** - Begin with defaults and increase only if needed
2. **Monitor audit logs** - Watch for repeated timeout/memory errors
3. **Use prepared reports** - Encourage use of `generate_report` tool for large datasets
4. **Train users** - Educate users about efficient data processing patterns

### For AI Agent Developers

1. **Process data in batches** - Avoid loading entire datasets into memory
2. **Use generators** - Stream data instead of collecting in lists
3. **Add progress indicators** - Print progress for long operations
4. **Test with limits** - Develop with production limits enabled

### Example: Efficient Data Processing

```python
# BAD: Loads all data into memory
all_invoices = tools.get_documents("Sales Invoice", limit=10000)
df = pd.DataFrame(all_invoices["data"])
# Process entire dataset...

# GOOD: Process in batches
batch_size = 500
offset = 0
results = []

while True:
    batch = tools.get_documents(
        "Sales Invoice",
        limit=batch_size,
        start=offset
    )
    if not batch["success"] or not batch["data"]:
        break

    # Process batch
    batch_result = process_batch(batch["data"])
    results.append(batch_result)

    offset += batch_size
    print(f"Processed {offset} records...")

# Combine results
final_result = combine_results(results)
```

## Troubleshooting

### "Execution Timeout" Errors

- Check for infinite loops (while True without break)
- Reduce data volume being processed
- Consider using `generate_report` for complex queries
- Break operation into multiple smaller tool calls

### "Memory Limit Exceeded" Errors

- Avoid creating large lists/DataFrames
- Use generators instead of list comprehensions
- Delete intermediate variables: `del large_variable`
- Process data in smaller batches

### "Recursion Limit Exceeded" Errors

- Convert recursive algorithms to iterative
- Add proper base cases
- Check for circular references in data structures

## Security Audit Trail

All code executions are logged with:

- User who initiated the execution
- Code snippet (truncated for security)
- Execution duration
- Success/failure status
- Error messages (if any)
- Resource usage metrics

View audit logs at: `/app/fac-audit-log`

## Related Documentation

- [Tool Management Guide](./TOOL_MANAGEMENT_GUIDE.md)
- [Plugin Development](../development/PLUGIN_DEVELOPMENT.md)
- [Python Code Orchestration](./PYTHON_CODE_ORCHESTRATION.md)

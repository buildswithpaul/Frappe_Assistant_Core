# How to Use run_python_code

## Overview

The `run_python_code` tool executes Python code in a **heavily sandboxed** environment with built-in data access. This is the preferred tool for analytics — it can fetch data AND analyze it in a single call.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `code` | string | **Yes** | — | Python code (NO import statements) |
| `timeout` | integer | No | 30 | Timeout in seconds (max: 300) |
| `capture_output` | boolean | No | `true` | Capture print output |
| `return_variables` | array | No | — | Variable names to return |
| `data_query` | object | No | — | Pre-fetch data as `data` variable |

## CRITICAL: What Is Actually Available

### Pre-loaded libraries (use directly, NO imports)

| Variable | Library | Works |
|----------|---------|-------|
| `pd` | pandas | Yes |
| `np` | numpy | Yes |
| `frappe` | Frappe framework | Yes |
| `math` | math | Yes |
| `datetime` | datetime module | Yes |
| `json` | json | Yes |
| `re` | re | Yes |
| `random` | random | Yes |
| `statistics` | statistics | Yes |
| `tools` | Data access API | Yes |

### NOT available

- **Plotting / visualization** — matplotlib, seaborn, plotly are NOT available. Plots cannot be rendered back to the caller. For charts and dashboards, use `create_dashboard_chart` and `create_dashboard` tools instead.
- **scipy** — NOT available. Use `statistics` or `np` for basic stats.
- `collections` — NOT pre-loaded. Use `dict` comprehensions or `pd.Series.value_counts()` instead of `Counter`.
- `itertools` — NOT pre-loaded. Use list comprehensions instead.
- `functools` — NOT pre-loaded.
- `operator` — NOT pre-loaded.
- `copy` — NOT pre-loaded. Use `dict(x)` or `list(x)` for shallow copies.

### Blocked built-in functions

- `any()`, `all()` — NOT available. Use `np.any()` / `np.all()` or manual loops.
- `dir()`, `help()`, `vars()`, `globals()`, `locals()` — blocked.
- `eval()`, `exec()`, `compile()` — pattern-blocked.
- `open()`, `input()` — pattern-blocked.
- `hasattr()`, `getattr()` — NOT available.

**Warning:** Security patterns are matched against the ENTIRE code string including comments and strings. Even `# don't use eval()` in a comment will trigger the `eval(` block.

### Import statements are completely blocked

Any `import X` or `from X import Y` will be rejected before execution. Everything must be used via the pre-loaded variable names.

## Date Handling — The #1 LLM Failure Point

### WRONG (will fail):
```python
# datetime.date.today() — FAILS because 'time' module import is blocked internally
today = datetime.date.today()  # NameError or ImportError

# Any import statement — BLOCKED
from datetime import datetime, timedelta  # Rejected
import datetime  # Rejected
```

### CORRECT:
```python
# Use frappe.utils for dates (returns strings in YYYY-MM-DD format)
today = frappe.utils.today()           # "2026-03-21" (string)
now = frappe.utils.now()               # "2026-03-21 02:57:07.981577" (string)
nowdate = frappe.utils.nowdate()       # "2026-03-21" (string)

# Date arithmetic
thirty_days_ago = frappe.utils.add_days(today, -30)    # "2026-02-19"
three_months_ago = frappe.utils.add_months(today, -3)  # "2025-12-21"

# Convert string to date object (when you need .strftime etc)
date_obj = frappe.utils.getdate(today)                 # datetime.date object
formatted = date_obj.strftime("%B %d, %Y")             # "March 21, 2026"

# Date/datetime conversion
dt_obj = frappe.utils.get_datetime("2024-01-15 10:30:00")  # datetime.datetime object

# Date math
days_diff = frappe.utils.date_diff("2024-03-15", "2024-01-01")  # 74

# Month boundaries
first = frappe.utils.get_first_day("2024-03-15")  # "2024-03-01"
last = frappe.utils.get_last_day("2024-03-15")     # "2024-03-31"

# datetime.datetime.now() DOES work (but frappe.utils is preferred)
dt = datetime.datetime.now()  # Works
# datetime.timedelta also works
td = datetime.timedelta(days=7)  # Works

# For pandas timestamp conversion
ts = pd.Timestamp("2024-01-15")
df["date_col"] = pd.to_datetime(df["date_col"])
```

## Built-in `tools` API

A `tools` variable provides data access inside code. Returns simpler dicts than the MCP tools directly.

| Method | Returns |
|--------|---------|
| `tools.get_documents(doctype, filters={}, fields=["*"], limit=100)` | `{success, data, count}` |
| `tools.get_document(doctype, name)` | `{success, data}` |
| `tools.generate_report(report_name, filters={}, format="json")` | `{success, data, columns}` |
| `tools.get_report_info(report_name)` | `{success, columns, filter_guidance}` |
| `tools.list_reports(module=None, report_type=None)` | `{success, reports, count}` |
| `tools.search(query, doctype=None, limit=20)` | `{success, results, count}` |
| `tools.get_doctype_info(doctype)` | `{success, fields, links, is_table, is_submittable}` |

## Common Patterns

### Fetch + analyze in one call
```python
today = frappe.utils.today()
start = frappe.utils.add_months(today, -6)

invoices = tools.get_documents("Sales Invoice",
    filters={"docstatus": 1, "posting_date": [">=", start]},
    fields=["customer_name", "grand_total", "posting_date"], limit=500)

if invoices["success"]:
    df = pd.DataFrame(invoices["data"])
    print(f"Total Revenue: {df['grand_total'].sum()}")
    print("\nTop Customers:")
    top = df.groupby("customer_name")["grand_total"].sum().sort_values(ascending=False).head(10)
    print(top.to_string())
```

### Workaround for missing `any()`/`all()`
```python
# Instead of: any(x > 100 for x in values)
result = np.any(np.array(values) > 100)

# Instead of: all(x > 0 for x in values)
result = np.all(np.array(values) > 0)

# Or with pandas:
result = (df["column"] > 100).any()
result = (df["column"] > 0).all()
```

### Workaround for missing `collections.Counter`
```python
# Instead of: Counter(items)
counts = pd.Series(items).value_counts().to_dict()
```

## Constraints

- **Read-only database** — cannot INSERT/UPDATE/DELETE
- **No file or network access** — completely sandboxed
- **No imports** — all libraries pre-loaded
- **Permission-checked** — respects user permissions
- **Audit-logged** — all executions are tracked
- **Pattern matching on entire code** — avoid words like `eval`, `open`, `input` even in comments

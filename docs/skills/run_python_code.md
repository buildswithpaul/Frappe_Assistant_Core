---
name: run-python-code-usage
description: "Sandboxed Python execution — actual available libraries, date handling pitfalls, frappe.db API, tools API, security restrictions"
---

# How to Use run_python_code

## Overview

The `run_python_code` tool executes Python code in a sandboxed environment.
Use it for analytics — fetch data, run calculations, and analyse results in a single call.
**All tools.* methods and frappe.db.* methods now work reliably inside run_python_code.**

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `code` | string | **Yes** | — | Python code (NO import statements) |
| `timeout` | integer | No | 30 | Timeout in seconds (max: 300) |
| `capture_output` | boolean | No | `true` | Capture print output |
| `return_variables` | array | No | — | Variable names to return values for |
| `data_query` | object | No | — | Pre-fetch records as `data` list variable |

---

## Pre-loaded Libraries — No Imports Needed (All Tested)

| Variable | Library | Status |
|----------|---------|--------|
| `pd` | pandas | ✅ Full DataFrame, groupby, merge, dt accessor |
| `np` | numpy | ✅ Arrays, math |
| `frappe` | Frappe framework | ✅ frappe.utils.*, frappe.db.* |
| `math` | math | ✅ sqrt, floor, ceil, log |
| `json` | json | ✅ dumps, loads |
| `re` | re | ✅ Pattern matching |
| `statistics` | statistics | ✅ mean, median, stdev |
| `random` | random | ✅ random, randint, choice |
| `datetime` | datetime module | ⚠️ Use carefully — see datetime section |
| `tools` | FAC tools API | ✅ All methods now work — see tools section |

### NOT available — these are NOT pre-loaded despite what the tool description says

| Name | Alternative |
|------|-------------|
| `plt` / `matplotlib` | Plots cannot be rendered back — use `create_dashboard_chart` / `create_dashboard` tools |
| `sns` / `seaborn` | Same as above |
| `plotly` (`go`, `px`) | Same as above |
| `scipy` (`stats`) | Use `statistics` or `np` for basic stats |
| `collections` | Use `pd.Series.value_counts()` or plain dicts |
| `itertools` | Use list comprehensions |
| `functools` | Use pandas `.apply()` |
| `operator` | Use inline operators directly (`+`, `>`, etc.) |
| `copy` | Use `list(x)` or `dict(x)` for shallow copy |
| `dir()` | Not available |
| `repr()` | Use `str()` |
| `format()` builtin | Use f-strings: `f"{val:.2f}"` |
| `any()` / `all()` | Use `np.any()` / `df.any()` |

### Confirmed available builtins

`str`, `int`, `float`, `len`, `list`, `dict`, `set`, `tuple`, `range`,
`enumerate`, `zip`, `map`, `filter`, `sorted`, `sum`, `min`, `max`,
`abs`, `round`, `bool`, `type`, `isinstance`, `hasattr`, `getattr`, `print`

---

## tools.* API — All Working (Tested)

All FAC tool methods now work inside `run_python_code`. Data comes back as plain
Python dicts — pass directly to `pd.DataFrame()` with no conversion needed.

### tools.get_documents() ✅

```python
result = tools.get_documents("Lead",
    filters={"status": "Opportunity", "creation": [">=", "2025-01-01"]},
    fields=["name", "status", "lead_owner", "source", "industry"],
    limit=500)

if result['success']:
    df = pd.DataFrame(result['data'])  # data is already plain dicts
    print(df['status'].value_counts().to_string())
```

Filter operators: `=`, `!=`, `>`, `<`, `>=`, `<=`, `in`, `not in`, `like`, `between`

### tools.get_document() ✅

```python
result = tools.get_document("Lead", "CRM-LEAD-2025-00033")
if result['success']:
    doc = result['data']   # plain dict with all 71+ fields
    print(doc['lead_name'], doc['status'], doc['industry'])
```

### tools.generate_report() ✅

```python
result = tools.generate_report("Lead Owner Efficiency",
    filters={"from_date": "2025-04-15", "to_date": "2026-04-15"})

if result['success']:
    df = pd.DataFrame(result['data'])
    # result also has: result['columns'], result['filters_applied']
    print(df.to_string())
```

### tools.list_reports() ✅

```python
result = tools.list_reports(module="CRM")   # or leave module empty for all
if result['success']:
    for r in result['reports']:
        print(r['name'], r['report_type'])
```

### tools.get_report_info() ✅

```python
result = tools.get_report_info("Lead Owner Efficiency")
if result['success']:
    print(result['report_name'])
    print(result['report_type'])
    for col in result.get('columns', []):
        print(col)
```

### tools.get_doctype_info() ✅

```python
result = tools.get_doctype_info("Lead")
if result['success']:
    fields = result['fields']   # list of dicts with fieldname, label, fieldtype, options
    for f in fields:
        print(f['fieldname'], f['fieldtype'])
```

### tools.search() ✅

```python
result = tools.search("Promantia", doctype="Customer", limit=10)
if result['success']:
    for r in result['results']:
        print(r)
```

### data_query parameter ✅

Pass a `data_query` dict as a tool parameter — records arrive as a plain Python
`list` in the `data` variable before your code runs:

```python
# Tool parameter: data_query={"doctype": "Lead", "fields": ["name","status"], "filters": {"status": "Opportunity"}, "limit": 100}
# Inside code:
df = pd.DataFrame(data)   # data is already a list of dicts
print(df.head())
```

---

## frappe.db — All Methods Working (Tested)

### frappe.db.sql() — most powerful, always reliable

```python
today = frappe.utils.today()
start = frappe.utils.add_months(today, -12)

# With values= dict — use %% for DATE_FORMAT format specifiers
rows = frappe.db.sql("""
    SELECT
        DATE_FORMAT(creation, '%%Y-%%m') as month,
        COALESCE(source, 'Unknown') as source,
        status,
        COUNT(*) as cnt
    FROM `tabLead`
    WHERE creation >= %(start)s
    GROUP BY month, source, status
    ORDER BY month ASC
""", values={"start": start}, as_dict=True)

# frappe.db.sql returns frappe._dict — convert to plain dicts for pandas
data = [dict(r) for r in rows]
df = pd.DataFrame(data)
```

> **`%%` vs `%` in DATE_FORMAT:**
> With `values=` dict, use `%%Y-%%m`. Without `values=`, use `%Y-%m`.

### frappe.db.get_all() ✅ (now working)

```python
rows = frappe.db.get_all("Lead",
    filters={"status": "Opportunity", "creation": [">=", "2025-01-01"]},
    fields=["name", "lead_owner", "source", "industry"],
    order_by="creation desc",
    limit=50)
# Returns list of frappe._dict — convert before pandas
df = pd.DataFrame([dict(r) for r in rows])
```

### frappe.get_doc() ✅ (now working)

```python
doc = frappe.get_doc("Lead", "CRM-LEAD-2025-00033")
print(doc.name, doc.status, doc.lead_owner, doc.industry)
# Access child tables
for note in doc.notes:
    print(note.note)
```

### Other frappe.db methods

```python
# Count
n = frappe.db.count("Lead", {"status": "Lead"})                # dict filter → int
n = frappe.db.count("Lead", [["status", "!=", "Converted"]])   # list filter → int
n = frappe.db.count("Lead")                                     # total count

# Single record lookup
owner = frappe.db.get_value("Lead", {"status":"Opportunity"}, "lead_owner")  # → str
name, owner = frappe.db.get_value("Lead", {"status":"Opportunity"}, ["name","lead_owner"])  # → tuple
row = frappe.db.get_value("Lead", {"status":"Opportunity"}, ["name","lead_owner"], as_dict=True)  # → _dict

# Check if exists
name = frappe.db.exists("Lead", "CRM-LEAD-2025-00001")     # → name string or None
name = frappe.db.exists("Lead", {"status": "Converted"})   # → first matching name or None
```

---

## Date Handling — Critical Rules

### datetime is the MODULE, not the class

```python
# Works:
dt = datetime.datetime.now()                               # datetime object
td = datetime.timedelta(days=30)                           # timedelta
dp = datetime.datetime.strptime("2026-01-01", "%Y-%m-%d") # parse string

# FAILS — these call the blocked time module internally:
datetime.date.today()       # "Import of 'time' is not allowed"
datetime.datetime.today()   # "Import of 'time' is not allowed"
dt.strftime('%Y-%m-%d')     # "Import of 'time' is not allowed"
pd.Timestamp.strftime(...)  # "Import of 'time' is not allowed"
```

**strftime is completely blocked.** Use frappe.utils and f-strings instead.

### Use frappe.utils for all date operations

```python
today = frappe.utils.today()              # "2026-04-17" (string)
now   = frappe.utils.now()               # "2026-04-17 12:30:00" (string)
dt    = frappe.utils.now_datetime()      # datetime.datetime object (PREFERRED)

# Arithmetic → YYYY-MM-DD strings
thirty_days_ago  = frappe.utils.add_days(today, -30)
three_months_ago = frappe.utils.add_months(today, -3)

# Period boundaries
first = frappe.utils.get_first_day(today)   # first day of current month → string
last  = frappe.utils.get_last_day(today)    # last day of current month → string

# Difference
diff = frappe.utils.date_diff("2026-04-01", "2026-01-01")  # → 90 (int, days)

# Object conversion
date_obj = frappe.utils.getdate(today)   # → datetime.date

# Type conversions
n = frappe.utils.cint("42")    # → 42
f = frappe.utils.flt("3.14")   # → 3.14
s = frappe.utils.cstr(123)     # → "123"

# BROKEN: frappe.utils.fmt_money() — use f"₹{value:,.0f}" instead
```

### Formatting dates without strftime

```python
dt = frappe.utils.now_datetime()

date_str  = f"{dt.year}-{dt.month:02d}-{dt.day:02d}"   # "2026-04-17"
month_str = f"{dt.year}-{dt.month:02d}"                 # "2026-04"

MONTH = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
month_name = MONTH[dt.month - 1]                         # "Apr"

# Pandas: use .dt.year / .dt.month accessors, NOT .dt.strftime()
df['month'] = (df['date_col'].dt.year.astype(str) + '-' +
               df['date_col'].dt.month.apply(lambda x: f'{x:02d}'))
```

---

## Security Blocks

Blocked before execution by pattern scanning — triggers even in comments.

| Pattern | Error |
|---------|-------|
| `eval(` | Security: Code evaluation not allowed |
| `exec(` | Security: Code execution not allowed |
| `import X` or `from X import` | Import not allowed |
| `.strftime(` | Runtime block via time module |

---

## Full Analytics Template

```python
# 1. Date range
today = frappe.utils.today()
start = frappe.utils.add_months(today, -12)
dt    = frappe.utils.now_datetime()

# 2a. Fetch via tools.get_documents (preferred for full field access)
result = tools.get_documents("Lead",
    filters={"creation": [">=", start]},
    fields=["name", "status", "source", "lead_owner", "creation", "industry"],
    limit=1000)

# 2b. OR fetch via frappe.db.sql for complex queries
rows = frappe.db.sql("""
    SELECT DATE_FORMAT(creation, '%%Y-%%m') as month,
           COALESCE(source, 'Unknown') as source,
           status, COUNT(*) as cnt
    FROM `tabLead`
    WHERE creation >= %(start)s
    GROUP BY month, source, status
""", values={"start": start}, as_dict=True)

# 3. Build DataFrame
# From tools.get_documents — data is already plain dicts:
df = pd.DataFrame(result['data'])

# From frappe.db.sql — must convert frappe._dict:
df = pd.DataFrame([dict(r) for r in rows])

# 4. Quick counts
total = frappe.db.count("Lead", {"creation": [">=", start]})
n_opp = frappe.db.count("Opportunity", {"status": "Open"})

# 5. Analyse and print
print(f"Total leads: {total}")
print(df.groupby("status")["name"].count().sort_values(ascending=False).to_string())
print(f"\nReport: {dt.year}-{dt.month:02d}-{dt.day:02d}")
```

---

## Common Errors and Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `module 'datetime' has no attribute 'today'` | `datetime.today()` — module not class | `frappe.utils.today()` |
| `Import of 'time' is not allowed` | `.strftime()`, `date.today()`, `datetime.today()` | f-strings with `.year/.month/.day` |
| `name 'collections' is not defined` | Not pre-loaded despite docs saying so | `pd.Series.value_counts()` or plain dicts |
| `name 'itertools' is not defined` | Not pre-loaded | List comprehensions |
| `frappe._dict not serializable` | Raw sql rows to pandas | Wrap with `dict(r)` |
| `tuple index out of range` | `frappe.utils.fmt_money()` is broken | `f"₹{value:,.0f}"` |
| `%%Y` vs `%Y` confusion | Wrong escaping in DATE_FORMAT | `%%Y-%%m` with `values=`, `%Y-%m` without |
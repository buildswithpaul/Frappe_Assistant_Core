# run_python_code

Execute custom Python code in a secure sandboxed environment for data analysis, calculations, and complex operations.

## CRITICAL: Read Before Writing Code

### Date/Time Handling - Use Pandas, Not datetime

The sandbox has restrictions that can cause `datetime.date.today()` to fail. **Always use pandas for date operations:**

```python
# CORRECT - Use pandas for all date operations
today = pd.Timestamp.now()
yesterday = today - pd.Timedelta(days=1)
first_of_month = today.replace(day=1)

# For date strings in filters
date_str = today.strftime("%Y-%m-%d")
```

```python
# AVOID - Can cause __import__ errors in sandbox
today = datetime.date.today()      # May fail
delta = datetime.timedelta(days=7) # May fail
```

### Filter Syntax - Use "between" for Date Ranges

```python
# CORRECT - Use "between" operator
filters = {
    "posting_date": ["between", [start_date, end_date]]
}

# WRONG - Duplicate keys, Python keeps only the last one!
filters = {
    "posting_date": [">=", start_date],
    "posting_date": ["<=", end_date]  # This overwrites the first!
}
```

### No Imports Needed

All libraries are pre-loaded. Do NOT write import statements.

---

## When to Use

- **Data analysis** requiring aggregation, filtering, or calculations
- **Complex transformations** that need pandas/numpy operations
- **Multi-source analysis** combining data from multiple DocTypes
- **Custom visualizations** using matplotlib/seaborn
- **Calculations** too complex for standard tools
- **Date-based analysis** like "last month", "this quarter", "year over year"

## Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| code | string | Yes | - | Python code to execute |
| data_query | object | No | - | Query to fetch data (available as `data` variable) |
| timeout | integer | No | 30 | Execution timeout in seconds (1-300) |
| capture_output | boolean | No | true | Capture print output |
| return_variables | array | No | [] | Variable names to return values for |

## Pre-Loaded Libraries

All libraries below are ready to use. **Do NOT use import statements.**

| Alias | Library | Purpose |
|-------|---------|---------|
| `pd` | pandas | Data manipulation, **date/time operations** |
| `np` | numpy | Numerical operations |
| `plt` | matplotlib.pyplot | Plotting |
| `sns` | seaborn | Statistical visualization |
| `frappe` | frappe | Frappe framework |
| `math` | math | Mathematical functions |
| `datetime` | datetime | Available but **use pandas instead** |
| `json` | json | JSON parsing |
| `re` | re | Regular expressions |
| `statistics` | statistics | Statistical functions |
| `random` | random | Random number generation |

**Requires Import (allowed but not pre-loaded):**
```python
from collections import Counter, defaultdict, OrderedDict
from itertools import groupby, chain
from functools import reduce
```

---

## Date and Time Operations

### Getting Current Date/Time

```python
# Current timestamp
now = pd.Timestamp.now()
print(f"Current time: {now}")

# Just the date part
today = pd.Timestamp.now().normalize()  # Midnight today
print(f"Today: {today.strftime('%Y-%m-%d')}")
```

### Date Arithmetic

```python
today = pd.Timestamp.now()

# Subtract days
yesterday = today - pd.Timedelta(days=1)
last_week = today - pd.Timedelta(weeks=1)
last_30_days = today - pd.Timedelta(days=30)

# Add time
tomorrow = today + pd.Timedelta(days=1)
next_week = today + pd.Timedelta(weeks=1)
```

### Getting Month Boundaries

```python
today = pd.Timestamp.now()

# Current month
current_month_start = today.replace(day=1)
# Last day of current month (go to next month day 1, subtract 1 day)
next_month = (today.replace(day=1) + pd.DateOffset(months=1))
current_month_end = next_month - pd.Timedelta(days=1)

# Last month
last_month_end = current_month_start - pd.Timedelta(days=1)
last_month_start = last_month_end.replace(day=1)

# Format for filters
print(f"Last month: {last_month_start.strftime('%Y-%m-%d')} to {last_month_end.strftime('%Y-%m-%d')}")
```

### Quarter and Year Boundaries

```python
today = pd.Timestamp.now()
year = today.year

# Current quarter
quarter = (today.month - 1) // 3 + 1
quarter_start_month = (quarter - 1) * 3 + 1
quarter_start = pd.Timestamp(year=year, month=quarter_start_month, day=1)

# Fiscal year (April start)
if today.month >= 4:
    fiscal_year_start = pd.Timestamp(year=year, month=4, day=1)
else:
    fiscal_year_start = pd.Timestamp(year=year-1, month=4, day=1)

print(f"Quarter start: {quarter_start.strftime('%Y-%m-%d')}")
print(f"Fiscal year start: {fiscal_year_start.strftime('%Y-%m-%d')}")
```

### Using Dates in Filters

```python
today = pd.Timestamp.now()
last_month_start = (today.replace(day=1) - pd.Timedelta(days=1)).replace(day=1)
last_month_end = today.replace(day=1) - pd.Timedelta(days=1)

# Use "between" for date ranges
result = tools.get_documents("Sales Invoice",
    filters={
        "docstatus": 1,
        "posting_date": ["between", [
            last_month_start.strftime("%Y-%m-%d"),
            last_month_end.strftime("%Y-%m-%d")
        ]]
    },
    fields=["customer_name", "grand_total"],
    limit=1000
)
```

---

## Tools API - Fetch Data Inside Code

The `tools` object provides methods to fetch data directly within your Python code. This is the recommended approach for data analysis as it keeps data in the sandbox without passing through the LLM context.

### tools.get_documents()

Fetch multiple documents with filtering.

```python
result = tools.get_documents(
    doctype,           # Required: DocType name
    filters={},        # Optional: Filter criteria
    fields=["*"],      # Optional: Fields to return
    limit=100          # Optional: Max records
)

# Returns: {"success": bool, "data": list, "count": int}
```

### tools.get_document()

Get a single document by name.

```python
result = tools.get_document(doctype, name)

# Returns: {"success": bool, "data": dict}
```

### tools.generate_report()

Execute a Frappe report (handles prepared reports automatically).

```python
result = tools.generate_report(
    report_name,       # Required: Report name
    filters={},        # Optional: Report filters
    format="json"      # Optional: Output format
)

# Returns: {"success": bool, "data": list, "columns": list, "status": str}
```

### tools.get_report_info()

Get report metadata before executing.

```python
result = tools.get_report_info(report_name)

# Returns: {"success": bool, "columns": list, "filter_guidance": list}
```

### tools.list_reports()

List available reports.

```python
result = tools.list_reports(
    module=None,       # Optional: Filter by module
    report_type=None   # Optional: Filter by type
)

# Returns: {"success": bool, "reports": list, "count": int}
```

### tools.search()

Search across Frappe documents.

```python
result = tools.search(query, doctype=None, limit=20)
```

### tools.get_doctype_info()

Get field definitions and metadata.

```python
result = tools.get_doctype_info(doctype)

# Returns: {"success": bool, "fields": list, "links": list}
```

---

## Complete Examples

### Last Month Customer Revenue Analysis

```python
# Calculate last month's date range using pandas
today = pd.Timestamp.now()
first_of_this_month = today.replace(day=1)
last_month_end = first_of_this_month - pd.Timedelta(days=1)
last_month_start = last_month_end.replace(day=1)

# Fetch sales invoices for last month
result = tools.get_documents("Sales Invoice",
    filters={
        "docstatus": 1,
        "posting_date": ["between", [
            last_month_start.strftime("%Y-%m-%d"),
            last_month_end.strftime("%Y-%m-%d")
        ]]
    },
    fields=["customer_name", "grand_total", "outstanding_amount"],
    limit=1000
)

if result["success"] and len(result["data"]) > 0:
    df = pd.DataFrame(result["data"])

    # Handle null values
    df['grand_total'] = df['grand_total'].fillna(0)
    df['outstanding_amount'] = df['outstanding_amount'].fillna(0)

    # Aggregate by customer
    summary = df.groupby("customer_name").agg({
        "grand_total": "sum",
        "outstanding_amount": "sum"
    }).reset_index()

    # Calculate collection rate (safe division)
    summary["collection_rate"] = summary.apply(
        lambda x: (x["grand_total"] - x["outstanding_amount"]) / x["grand_total"] * 100
        if x["grand_total"] > 0 else 0,
        axis=1
    ).round(2)

    # Get top 10
    top_10 = summary.sort_values("grand_total", ascending=False).head(10)

    month_name = last_month_start.strftime("%B %Y")
    print(f"TOP 10 CUSTOMERS FOR {month_name.upper()}:")
    for idx, row in enumerate(top_10.itertuples(), 1):
        print(f"{idx}. {row.customer_name}: ${row.grand_total:,.0f} ({row.collection_rate:.1f}% collected)")
else:
    print("No sales invoices found for last month.")
```

### Year-to-Date vs Last Year Comparison

```python
today = pd.Timestamp.now()
year = today.year

# YTD range
ytd_start = pd.Timestamp(year=year, month=1, day=1)
ytd_end = today

# Same period last year
ly_start = pd.Timestamp(year=year-1, month=1, day=1)
ly_end = today - pd.DateOffset(years=1)

# Fetch this year's data
this_year = tools.get_documents("Sales Invoice",
    filters={
        "docstatus": 1,
        "posting_date": ["between", [
            ytd_start.strftime("%Y-%m-%d"),
            ytd_end.strftime("%Y-%m-%d")
        ]]
    },
    fields=["grand_total"],
    limit=5000
)

# Fetch last year's data
last_year = tools.get_documents("Sales Invoice",
    filters={
        "docstatus": 1,
        "posting_date": ["between", [
            ly_start.strftime("%Y-%m-%d"),
            ly_end.strftime("%Y-%m-%d")
        ]]
    },
    fields=["grand_total"],
    limit=5000
)

if this_year["success"] and last_year["success"]:
    ty_total = sum(inv.get("grand_total", 0) or 0 for inv in this_year["data"])
    ly_total = sum(inv.get("grand_total", 0) or 0 for inv in last_year["data"])

    growth = ((ty_total - ly_total) / ly_total * 100) if ly_total > 0 else 0

    print(f"YEAR-TO-DATE COMPARISON:")
    print(f"  {year} YTD: ${ty_total:,.2f}")
    print(f"  {year-1} Same Period: ${ly_total:,.2f}")
    print(f"  Growth: {growth:+.1f}%")
```

### Monthly Sales Trend

```python
# Get last 12 months of data
today = pd.Timestamp.now()
twelve_months_ago = today - pd.DateOffset(months=12)

result = tools.get_documents("Sales Invoice",
    filters={
        "docstatus": 1,
        "posting_date": [">=", twelve_months_ago.strftime("%Y-%m-%d")]
    },
    fields=["posting_date", "grand_total"],
    limit=5000
)

if result["success"]:
    df = pd.DataFrame(result["data"])
    df['posting_date'] = pd.to_datetime(df['posting_date'])
    df['grand_total'] = df['grand_total'].fillna(0)
    df['month'] = df['posting_date'].dt.to_period('M')

    monthly = df.groupby('month')['grand_total'].sum().reset_index()
    monthly = monthly.sort_values('month')

    print("MONTHLY SALES TREND (Last 12 Months):")
    for _, row in monthly.iterrows():
        print(f"  {row['month']}: ${row['grand_total']:,.2f}")
```

### Inventory Analysis

```python
# Get stock levels from Bin
bins = tools.get_documents("Bin",
    fields=["item_code", "warehouse", "actual_qty", "projected_qty"],
    limit=500
)

# Get item details
items = tools.get_documents("Item",
    filters={"disabled": 0},
    fields=["item_code", "item_name", "item_group", "valuation_rate"],
    limit=500
)

if bins["success"] and items["success"]:
    bin_df = pd.DataFrame(bins["data"])
    item_df = pd.DataFrame(items["data"])

    # Merge data
    merged = bin_df.merge(item_df, on="item_code", how="left")

    # Handle None values
    merged['actual_qty'] = merged['actual_qty'].fillna(0)
    merged['valuation_rate'] = merged['valuation_rate'].fillna(0)

    # Calculate stock value
    merged['stock_value'] = merged['actual_qty'] * merged['valuation_rate']

    # Aggregate by item group
    by_group = merged.groupby('item_group').agg({
        'actual_qty': 'sum',
        'stock_value': 'sum'
    }).sort_values('stock_value', ascending=False)

    print("STOCK VALUE BY ITEM GROUP:")
    for group, row in by_group.head(10).iterrows():
        if pd.notna(group):
            print(f"  {group}: {row['actual_qty']:,.0f} units, ${row['stock_value']:,.2f}")
```

### Using data_query Parameter

Instead of using the tools API, you can fetch data via the `data_query` parameter:

```json
{
  "code": "df = pd.DataFrame(data)\nprint(df.describe())",
  "data_query": {
    "doctype": "Sales Invoice",
    "fields": ["grand_total", "outstanding_amount"],
    "filters": {"docstatus": 1},
    "limit": 100
  }
}
```

The fetched data will be available as the `data` variable.

### Simple Calculation

```python
# For calculations on provided data (no fetching needed)
numbers = [100, 250, 175, 300, 225]

avg = statistics.mean(numbers)
median = statistics.median(numbers)
std_dev = statistics.stdev(numbers)

print(f"Average: {avg:.2f}")
print(f"Median: {median:.2f}")
print(f"Std Dev: {std_dev:.2f}")
```

---

## Common Pitfalls

### 1. Using datetime Module Directly

```python
# WRONG - May cause sandbox errors
today = datetime.date.today()
delta = datetime.timedelta(days=30)

# RIGHT - Use pandas
today = pd.Timestamp.now()
delta = pd.Timedelta(days=30)
thirty_days_ago = today - delta
```

### 2. Duplicate Filter Keys

```python
# WRONG - Python dict keeps only the last key!
filters = {
    "posting_date": [">=", "2024-01-01"],
    "posting_date": ["<=", "2024-01-31"]  # Overwrites the first!
}
# Result: Only <= filter is applied

# RIGHT - Use "between"
filters = {
    "posting_date": ["between", ["2024-01-01", "2024-01-31"]]
}
```

### 3. Not Handling None Values

```python
# WRONG - Will fail on None values
total = df['amount'].sum()  # NaN if any None values
rate = collected / total  # Division error if total is 0

# RIGHT - Handle None values first
df['amount'] = df['amount'].fillna(0)
total = df['amount'].sum()
rate = (collected / total * 100) if total > 0 else 0
```

### 4. Unsafe Dictionary Access

```python
# WRONG - KeyError if field missing
value = row['field_name']

# RIGHT - Use .get() with default
value = row.get('field_name', 0)
```

### 5. Not Checking API Response

```python
# WRONG - Assumes success
result = tools.get_documents("Sales Invoice", ...)
df = pd.DataFrame(result["data"])  # Fails if success=False

# RIGHT - Check success first
result = tools.get_documents("Sales Invoice", ...)
if result["success"] and len(result["data"]) > 0:
    df = pd.DataFrame(result["data"])
    # Process data
else:
    print("No data found or query failed")
```

---

## Data Handling Best Practices

### Handle None Values

```python
df['amount'] = df['amount'].fillna(0)  # Numeric
df['name'] = df['name'].fillna('Unknown')  # String
```

### Safe Dictionary Access

```python
value = row.get('field', 'default_value')  # Not row['field']
```

### Safe Division

```python
rate = (paid / total * 100) if total > 0 else 0
```

### Check Before Formatting

```python
if pd.notna(value):
    print(f"{value:,.2f}")
```

---

## Response Format

### Success

```json
{
  "success": true,
  "output": "TOP 10 CUSTOMERS BY REVENUE:\n1. ABC Corp: $125,000 (85.2% collected)\n...",
  "variables": {
    "summary": "<DataFrame with 10 rows>"
  },
  "user_context": "user@example.com",
  "execution_time": 1.23
}
```

### Error

```json
{
  "success": false,
  "error": "NameError: name 'undefined_var' is not defined",
  "output": "",
  "variables": {},
  "traceback": "..."
}
```

---

## When to Use Tools API vs. Other Approaches

### Use Tools API (Recommended)

- User asks for data analysis requiring fetching + processing
- Combining data from multiple sources
- Processing datasets with 50+ rows
- Token efficiency is important

### Use generate_report Tool Directly

- Standard business report with known filters
- No custom processing needed
- Example: "Show me Sales Analytics for Q1"

### Use run_python_code Without Tools API

- Simple calculations on small provided data
- User explicitly provides all data
- No database access needed

---

## Security

- **Read-only database** - Only SELECT queries allowed
- **Permission checks** - User permissions are enforced
- **Code scanning** - Dangerous operations are blocked
- **No file system access** - Cannot read/write files
- **No network access** - Cannot make HTTP requests
- **Sandboxed execution** - Isolated environment
- **Audit logging** - All executions are logged

### Blocked Operations

- File I/O operations
- Network requests
- System commands
- Most module imports (except pre-loaded and whitelisted)
- Database writes

---

## Related Tools

- **generate_report** - Execute standard Frappe reports directly
- **list_documents** - Simple document listing (for small datasets)
- **get_document** - Retrieve single document
- **get_doctype_info** - Understand DocType structure

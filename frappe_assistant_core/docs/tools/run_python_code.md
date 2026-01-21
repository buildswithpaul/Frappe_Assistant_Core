# run_python_code

Execute custom Python code in a secure sandboxed environment for data analysis, calculations, and complex operations.

## When to Use

- **Data analysis** requiring aggregation, filtering, or calculations
- **Complex transformations** that need pandas/numpy operations
- **Multi-source analysis** combining data from multiple DocTypes
- **Custom visualizations** using matplotlib/seaborn
- **Calculations** too complex for standard tools

## Key Features

- **Pre-loaded libraries** - No imports needed
- **Tools API** - Fetch data directly inside your code
- **Read-only database** - Safe SELECT operations only
- **Permission-aware** - User permissions are respected
- **Audit logging** - All executions are logged

## Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| code | string | Yes | - | Python code to execute |
| data_query | object | No | - | Query to fetch data (available as `data` variable) |
| timeout | integer | No | 30 | Execution timeout in seconds (1-300) |
| capture_output | boolean | No | true | Capture print output |
| return_variables | array | No | [] | Variable names to return values for |

## Pre-Loaded Libraries

All libraries are pre-loaded and ready to use. **Do NOT use import statements.**

| Alias | Library | Purpose |
|-------|---------|---------|
| `pd` | pandas | Data manipulation |
| `np` | numpy | Numerical operations |
| `plt` | matplotlib.pyplot | Plotting |
| `sns` | seaborn | Statistical visualization |
| `frappe` | frappe | Frappe framework |
| `math` | math | Mathematical functions |
| `datetime` | datetime | Date/time handling |
| `json` | json | JSON parsing |
| `re` | re | Regular expressions |
| `statistics` | statistics | Statistical functions |
| `random` | random | Random number generation |
| `collections` | collections | Specialized containers |

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

## Examples

### Customer Revenue Analysis

```python
# Fetch sales invoices
result = tools.get_documents("Sales Invoice",
    filters={"docstatus": 1, "posting_date": [">=", "2024-01-01"]},
    fields=["customer_name", "grand_total", "outstanding_amount"],
    limit=500
)

if result["success"]:
    df = pd.DataFrame(result["data"])

    # Handle null values
    df['grand_total'] = df['grand_total'].fillna(0)
    df['outstanding_amount'] = df['outstanding_amount'].fillna(0)

    # Aggregate by customer
    summary = df.groupby("customer_name").agg({
        "grand_total": "sum",
        "outstanding_amount": "sum"
    }).reset_index()

    # Calculate collection rate
    summary["collection_rate"] = summary.apply(
        lambda x: (x["grand_total"] - x["outstanding_amount"]) / x["grand_total"] * 100
        if x["grand_total"] > 0 else 0,
        axis=1
    ).round(2)

    # Get top 10
    top_10 = summary.sort_values("grand_total", ascending=False).head(10)

    print("TOP 10 CUSTOMERS BY REVENUE:")
    for idx, row in enumerate(top_10.itertuples(), 1):
        print(f"{idx}. {row.customer_name}: ${row.grand_total:,.0f} ({row.collection_rate:.1f}% collected)")
```

### Monthly Sales Trend

```python
result = tools.get_documents("Sales Invoice",
    filters={"docstatus": 1},
    fields=["posting_date", "grand_total"],
    limit=1000
)

if result["success"]:
    df = pd.DataFrame(result["data"])
    df['posting_date'] = pd.to_datetime(df['posting_date'])
    df['month'] = df['posting_date'].dt.to_period('M')

    monthly = df.groupby('month')['grand_total'].sum().reset_index()

    print("MONTHLY SALES TREND:")
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

    # Calculate stock value
    merged['stock_value'] = merged['actual_qty'] * merged['valuation_rate'].fillna(0)

    # Aggregate by item group
    by_group = merged.groupby('item_group').agg({
        'actual_qty': 'sum',
        'stock_value': 'sum'
    }).sort_values('stock_value', ascending=False)

    print("STOCK VALUE BY ITEM GROUP:")
    for group, row in by_group.head(10).iterrows():
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
- Module imports (except pre-loaded)
- Database writes

## Related Tools

- **generate_report** - Execute standard Frappe reports directly
- **list_documents** - Simple document listing (for small datasets)
- **get_document** - Retrieve single document
- **get_doctype_info** - Understand DocType structure

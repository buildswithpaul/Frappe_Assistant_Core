# Python Code Multi-Tool Orchestration Guide

## Overview

The `run_python_code` tool has been enhanced with **multi-tool orchestration** capability, allowing LLMs to write Python code that calls other tools directly inside the sandbox environment. This revolutionary approach achieves **80-95% token savings** for data analysis workflows by processing data in the sandbox instead of passing it through the LLM context.

### The Problem This Solves

**Traditional approach (Token Wasteful):**
```
User: "Analyze sales by customer for top 10 customers"

LLM calls: list_documents (gets 100 invoices)
→ Returns 100 invoice records to LLM (5000+ tokens)
→ LLM manually analyzes in its context (burns tokens)
→ LLM returns insights
```

**Orchestrated approach (Token Efficient):**
```
User: "Analyze sales by customer for top 10 customers"

LLM writes: run_python_code with tools.get_documents() inside
→ Data fetched and processed in sandbox (0 tokens to LLM)
→ Only insights returned (50 tokens)
→ 98% token savings!
```

## Quick Start

### Basic Example: Invoice Analysis

**CORRECT - Using Tools API (Token Efficient):**
```python
# LLM writes this code in run_python_code tool
import pandas as pd

# Fetch data INSIDE the sandbox using tools API
result = tools.get_documents(
    doctype="Sales Invoice",
    filters={"status": "Paid"},
    fields=["customer_name", "grand_total", "outstanding_amount"],
    limit=100
)

if result["success"]:
    # Data stays in sandbox - process with pandas
    df = pd.DataFrame(result["data"])
    df['grand_total'] = df['grand_total'].fillna(0)

    # Aggregate by customer
    customer_summary = df.groupby("customer_name").agg({
        "grand_total": "sum"
    }).sort_values("grand_total", ascending=False).head(10)

    # Return only insights (not raw data)
    print("Top 10 Customers by Revenue:")
    print(customer_summary.to_string())
```

**INCORRECT - Manual Data Copy (Token Wasteful):**
```python
# DON'T DO THIS - wastes tokens by passing data through LLM
import pandas as pd

# Hard-coding data that LLM manually copied from list_documents call
data = [
    {"customer_name": "ABC Corp", "grand_total": 50000},
    {"customer_name": "XYZ Ltd", "grand_total": 45000},
    # ... 98 more records manually transcribed ...
]

df = pd.DataFrame(data)
# ... analysis ...
```

**Token Comparison:**
- INCORRECT: ~5000 tokens (raw data through LLM context)
- CORRECT: ~50 tokens (only insights returned)
- **Savings: 99%**

## Tools API Reference

The `tools` object is automatically available in the `run_python_code` sandbox environment.

### Available Methods

#### `tools.get_documents()`

Fetch multiple documents with filtering and pagination.

**Signature:**
```python
tools.get_documents(
    doctype: str,
    filters: dict = None,
    fields: list = None,
    limit: int = 100
) -> dict
```

**Parameters:**
- `doctype` (str, required): DocType name (e.g., "Sales Invoice", "Customer")
- `filters` (dict, optional): Filter conditions (e.g., `{"status": "Open"}`)
- `fields` (list, optional): Fields to retrieve (e.g., `["name", "customer_name"]`)
- `limit` (int, optional): Maximum records to fetch (default: 100)

**Returns:**
```python
{
    "success": True,
    "data": [
        {"name": "SINV-00001", "customer_name": "ABC Corp", ...},
        {"name": "SINV-00002", "customer_name": "XYZ Ltd", ...}
    ],
    "count": 2
}
```

**Example:**
```python
# Fetch all paid invoices from Q1 2024
result = tools.get_documents(
    doctype="Sales Invoice",
    filters={
        "status": "Paid",
        "posting_date": ["between", ["2024-01-01", "2024-03-31"]]
    },
    fields=["name", "customer_name", "grand_total", "posting_date"],
    limit=500
)

if result["success"]:
    df = pd.DataFrame(result["data"])
    print(f"Fetched {len(df)} invoices")
```

#### `tools.get_document()`

Fetch a single document by name.

**Signature:**
```python
tools.get_document(
    doctype: str,
    name: str
) -> dict
```

**Parameters:**
- `doctype` (str, required): DocType name
- `name` (str, required): Document name/ID

**Returns:**
```python
{
    "success": True,
    "data": {
        "name": "SINV-00001",
        "customer_name": "ABC Corp",
        "grand_total": 50000,
        # ... all fields ...
    }
}
```

**Example:**
```python
# Get specific invoice details
result = tools.get_document(
    doctype="Sales Invoice",
    name="SINV-00001"
)

if result["success"]:
    invoice = result["data"]
    print(f"Invoice {invoice['name']}: ${invoice['grand_total']}")
```

#### `tools.generate_report()`

Execute Frappe reports (Script Reports, Query Reports, Custom Reports).

**Signature:**
```python
tools.generate_report(
    report_name: str,
    filters: dict = None
) -> dict
```

**Parameters:**
- `report_name` (str, required): Report name (e.g., "Sales Analytics")
- `filters` (dict, optional): Report-specific filters

**Returns:**
```python
{
    "success": True,
    "data": [
        {"entity": "Customer A", "total_sales": 100000, ...},
        {"entity": "Customer B", "total_sales": 75000, ...}
    ],
    "columns": [...],
    "report_summary": [...]
}
```

**Example:**
```python
# Run Sales Analytics report
result = tools.generate_report(
    report_name="Sales Analytics",
    filters={
        "from_date": "2024-01-01",
        "to_date": "2024-03-31",
        "tree_type": "Customer"
    }
)

if result["success"]:
    df = pd.DataFrame(result["data"])
    top_customers = df.nlargest(5, "total_sales")
    print(top_customers)
```

## Usage Patterns

### Pattern 1: Data Fetching + Analysis

**Use Case:** Analyze data that requires fetching and processing.

```python
import pandas as pd
import numpy as np

# Fetch data using tools API
result = tools.get_documents(
    doctype="Sales Order",
    filters={"status": ["in", ["To Deliver", "To Bill"]]},
    fields=["name", "customer", "grand_total", "delivery_date"],
    limit=200
)

if result["success"]:
    df = pd.DataFrame(result["data"])

    # Handle null values
    df['grand_total'] = df['grand_total'].fillna(0)
    df['delivery_date'] = pd.to_datetime(df['delivery_date'])

    # Analysis
    overdue = df[df['delivery_date'] < pd.Timestamp.now()]

    # Aggregate by customer
    customer_analysis = df.groupby('customer').agg({
        'grand_total': 'sum',
        'name': 'count'
    }).rename(columns={'name': 'order_count'})

    print(f"Total pending orders: {len(df)}")
    print(f"Overdue orders: {len(overdue)}")
    print("\nTop 5 Customers by Pending Value:")
    print(customer_analysis.nlargest(5, 'grand_total'))
```

### Pattern 2: Multi-Source Data Combination

**Use Case:** Combine data from multiple DocTypes.

```python
import pandas as pd

# Fetch customers
customers_result = tools.get_documents(
    doctype="Customer",
    filters={"disabled": 0},
    fields=["name", "customer_group", "territory"]
)

# Fetch invoices
invoices_result = tools.get_documents(
    doctype="Sales Invoice",
    filters={"docstatus": 1},
    fields=["customer", "grand_total", "posting_date"],
    limit=1000
)

if customers_result["success"] and invoices_result["success"]:
    customers_df = pd.DataFrame(customers_result["data"])
    invoices_df = pd.DataFrame(invoices_result["data"])

    # Merge data
    merged = invoices_df.merge(
        customers_df,
        left_on="customer",
        right_on="name",
        how="left"
    )

    # Analyze by customer group
    group_analysis = merged.groupby("customer_group").agg({
        "grand_total": ["sum", "mean", "count"]
    })

    print("Sales Analysis by Customer Group:")
    print(group_analysis.to_string())
```

### Pattern 3: Report Execution + Post-Processing

**Use Case:** Run Frappe report and perform additional analysis.

```python
import pandas as pd

# Execute report using tools API
result = tools.generate_report(
    report_name="Sales Analytics",
    filters={
        "from_date": "2024-01-01",
        "to_date": "2024-12-31",
        "tree_type": "Customer",
        "based_on": "Item"
    }
)

if result["success"]:
    df = pd.DataFrame(result["data"])

    # Post-process report data
    df['total'] = df['total'].fillna(0)

    # Calculate percentages
    total_sales = df['total'].sum()
    df['percentage'] = (df['total'] / total_sales * 100).round(2)

    # Find top performers
    top_items = df.nlargest(10, 'total')

    print(f"Total Sales: ${total_sales:,.2f}")
    print("\nTop 10 Items by Sales:")
    print(top_items[['entity', 'total', 'percentage']].to_string())
```

### Pattern 4: Time-Series Analysis

**Use Case:** Analyze trends over time.

```python
import pandas as pd
import numpy as np

# Fetch time-series data
result = tools.get_documents(
    doctype="Sales Invoice",
    filters={"docstatus": 1},
    fields=["posting_date", "grand_total", "customer_group"],
    limit=1000
)

if result["success"]:
    df = pd.DataFrame(result["data"])

    # Convert to datetime and handle nulls
    df['posting_date'] = pd.to_datetime(df['posting_date'])
    df['grand_total'] = df['grand_total'].fillna(0)

    # Resample by month
    df.set_index('posting_date', inplace=True)
    monthly_sales = df.resample('M')['grand_total'].sum()

    # Calculate growth rate
    growth = monthly_sales.pct_change() * 100

    print("Monthly Sales Trend:")
    for date, sales in monthly_sales.items():
        growth_rate = growth[date] if not pd.isna(growth[date]) else 0
        print(f"{date.strftime('%Y-%m')}: ${sales:,.2f} ({growth_rate:+.1f}%)")
```

## Best Practices

### 1. Data Handling

**Always handle None/null values:**
```python
# For numeric fields
df['amount'] = df['amount'].fillna(0)

# For string fields
df['status'] = df['status'].fillna('Unknown')

# Check before formatting
if pd.notna(value):
    print(f"{value:,.2f}")
```

**Safe dictionary access:**
```python
# Use .get() with defaults
customer = row.get('customer_name', 'Unknown')

# Not direct access that might fail
# customer = row['customer_name']  # May raise KeyError
```

**Safe division:**
```python
# Prevent division by zero
rate = (paid / total * 100) if total > 0 else 0
```

### 2. Error Handling

**Always check result success:**
```python
result = tools.get_documents(doctype="Customer", limit=100)

if result["success"]:
    # Process data
    df = pd.DataFrame(result["data"])
else:
    print(f"Error: {result.get('error', 'Unknown error')}")
```

**Handle empty datasets:**
```python
if result["success"]:
    if len(result["data"]) == 0:
        print("No data found")
    else:
        df = pd.DataFrame(result["data"])
        # Process...
```

### 3. Performance Optimization

**Use appropriate limits:**
```python
# Don't fetch more than needed
result = tools.get_documents(
    doctype="Sales Invoice",
    limit=100  # Not 10000 if you only need top 10
)
```

**Select only required fields:**
```python
# Good - only fields needed
fields=["name", "customer", "grand_total"]

# Bad - fetching everything
fields=["*"]
```

**Use filters to reduce dataset:**
```python
# Filter at database level
filters={
    "docstatus": 1,
    "posting_date": [">", "2024-01-01"]
}
```

### 4. Output Formatting

**Return structured insights, not raw data:**
```python
# Good - formatted insights
print("Top 5 Customers:")
print(f"1. {name1}: ${amount1:,.2f}")
print(f"2. {name2}: ${amount2:,.2f}")

# Bad - dumping raw dataframe
print(df)  # Too much data in response
```

**Use clear visualizations:**
```python
# Use pandas formatting
print(df.to_string(index=False))

# Or markdown tables
print(df.to_markdown())
```

## Advanced Techniques

### Complex Aggregations

```python
import pandas as pd

result = tools.get_documents(
    doctype="Sales Invoice",
    filters={"docstatus": 1},
    fields=["customer", "territory", "grand_total", "posting_date"],
    limit=1000
)

if result["success"]:
    df = pd.DataFrame(result["data"])
    df['grand_total'] = df['grand_total'].fillna(0)
    df['posting_date'] = pd.to_datetime(df['posting_date'])
    df['month'] = df['posting_date'].dt.to_period('M')

    # Multi-level aggregation
    pivot = df.pivot_table(
        values='grand_total',
        index='territory',
        columns='month',
        aggfunc='sum',
        fill_value=0
    )

    print("Sales by Territory and Month:")
    print(pivot.to_string())
```

### Statistical Analysis

```python
import pandas as pd
import numpy as np

result = tools.get_documents(
    doctype="Sales Order",
    filters={},
    fields=["grand_total", "delivery_date", "transaction_date"],
    limit=500
)

if result["success"]:
    df = pd.DataFrame(result["data"])
    df['grand_total'] = df['grand_total'].fillna(0)

    # Calculate delivery time
    df['delivery_date'] = pd.to_datetime(df['delivery_date'])
    df['transaction_date'] = pd.to_datetime(df['transaction_date'])
    df['lead_time'] = (df['delivery_date'] - df['transaction_date']).dt.days

    # Statistical summary
    print("Order Value Statistics:")
    print(df['grand_total'].describe())
    print(f"\nMedian Lead Time: {df['lead_time'].median():.1f} days")
    print(f"90th Percentile Lead Time: {df['lead_time'].quantile(0.9):.1f} days")
```

### Cohort Analysis

```python
import pandas as pd

# Fetch customer and order data
customers = tools.get_documents(
    doctype="Customer",
    fields=["name", "creation"],
    limit=500
)

orders = tools.get_documents(
    doctype="Sales Order",
    filters={"docstatus": 1},
    fields=["customer", "transaction_date", "grand_total"],
    limit=2000
)

if customers["success"] and orders["success"]:
    cust_df = pd.DataFrame(customers["data"])
    ord_df = pd.DataFrame(orders["data"])

    # Prepare data
    cust_df['creation'] = pd.to_datetime(cust_df['creation'])
    cust_df['cohort'] = cust_df['creation'].dt.to_period('M')

    ord_df['transaction_date'] = pd.to_datetime(ord_df['transaction_date'])
    ord_df['order_month'] = ord_df['transaction_date'].dt.to_period('M')

    # Merge and analyze
    merged = ord_df.merge(cust_df[['name', 'cohort']],
                          left_on='customer', right_on='name')

    # Cohort analysis
    cohort_data = merged.groupby(['cohort', 'order_month']).agg({
        'customer': 'nunique',
        'grand_total': 'sum'
    })

    print("Customer Cohort Analysis:")
    print(cohort_data.head(20))
```

## Troubleshooting

### Common Issues

**Issue: `'NoneType' object has no attribute 'format'`**
```python
# Solution: Check for None before formatting
value = row.get('amount')
if value is not None and pd.notna(value):
    print(f"Amount: {value:,.2f}")
```

**Issue: `invalid __array_struct__` error**
```python
# Solution: Data is already converted to plain dicts, but if you see this:
result = tools.get_documents(...)
# The tools API automatically converts frappe._dict to plain dict
# If still issues, explicitly convert:
data = [dict(row) for row in result["data"]]
df = pd.DataFrame(data)
```

**Issue: `Tool execution failed: No data found`**
```python
# Solution: Check filters and ensure data exists
result = tools.get_documents(doctype="Customer", filters={})
if result["success"]:
    if len(result["data"]) == 0:
        print("No customers found - check filters")
    else:
        print(f"Found {len(result['data'])} customers")
```

**Issue: Code times out**
```python
# Solution: Reduce data fetching and processing
# Bad: fetch 10000 records
result = tools.get_documents(doctype="Sales Invoice", limit=10000)

# Good: fetch reasonable amount
result = tools.get_documents(doctype="Sales Invoice", limit=500)
```

## Token Savings Calculator

| Scenario | Without Orchestration | With Orchestration | Savings |
|----------|----------------------|-------------------|---------|
| **100 invoice records** | 5,000 tokens | 50 tokens | 99% |
| **Customer analysis (50 records)** | 3,000 tokens | 100 tokens | 96.7% |
| **Report with 200 rows** | 8,000 tokens | 150 tokens | 98.1% |
| **Multi-table join (500 records)** | 15,000 tokens | 200 tokens | 98.7% |

**Average savings: 80-95%**

## Security Model

The tools API runs with the same permissions as the authenticated user:

- **Read-only operations**: Only SELECT queries allowed
- **Permission checks**: All DocType permissions enforced
- **Row-level security**: User can only access documents they have permission for
- **Field-level security**: Sensitive fields are automatically filtered
- **Audit logging**: All tool calls are logged for security monitoring

## Conclusion

Multi-tool orchestration transforms `run_python_code` from a simple script executor into a powerful data processing engine that achieves massive token savings while enabling complex analysis workflows. By fetching and processing data inside the sandbox, you minimize LLM context usage and maximize analysis capability.

**Key Takeaways:**
1. Use `tools.get_documents()` and `tools.generate_report()` INSIDE Python code
2. Process data with pandas/numpy in the sandbox
3. Return only insights and summaries to LLM
4. Achieve 80-95% token savings for data analysis tasks
5. Always handle null values and check for errors

For more information, see:
- [Tool Reference](../api/TOOL_REFERENCE.md)
- [Technical Documentation](../architecture/TECHNICAL_DOCUMENTATION.md)
- [run_python_code Tool Source](../../frappe_assistant_core/plugins/data_science/tools/run_python_code.py)

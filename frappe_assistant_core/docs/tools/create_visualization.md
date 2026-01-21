# create_visualization

Create data visualizations using matplotlib, plotly, and seaborn.

## When to Use

- Creating custom charts for data analysis
- Generating visualizations from query results
- Building charts from DocType data
- Exporting visualizations as images

## Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| data_source | object | Yes | Data source configuration (see below) |
| chart_config | object | Yes | Chart configuration (see below) |
| styling | object | No | Visual styling options |
| output_format | string | No | Output format: "base64", "svg", "html", "json" |

### Data Source Options

```json
{
  "type": "data",        // Use provided raw data
  "data": [...]          // Array of data objects
}
```

```json
{
  "type": "query",       // Execute SQL query
  "query": "SELECT ..."  // SQL query string
}
```

```json
{
  "type": "doctype",     // Fetch from DocType
  "doctype": "Sales Invoice",
  "fields": ["customer", "grand_total"],
  "filters": {"docstatus": 1},
  "limit": 100
}
```

### Chart Configuration

| Property | Type | Description |
|----------|------|-------------|
| chart_type | string | bar, line, pie, scatter, histogram, box, heatmap, area |
| title | string | Chart title |
| x_column | string | X-axis column |
| y_column | string | Y-axis column |
| color_column | string | Column for color grouping |
| size_column | string | Column for size (scatter plots) |
| aggregation | string | sum, count, mean, median, min, max |

## Examples

### Bar Chart from DocType

```json
{
  "data_source": {
    "type": "doctype",
    "doctype": "Sales Invoice",
    "fields": ["customer", "grand_total"],
    "filters": {"docstatus": 1},
    "limit": 50
  },
  "chart_config": {
    "chart_type": "bar",
    "title": "Sales by Customer",
    "x_column": "customer",
    "y_column": "grand_total",
    "aggregation": "sum"
  }
}
```

### Line Chart from Query

```json
{
  "data_source": {
    "type": "query",
    "query": "SELECT DATE(posting_date) as date, SUM(grand_total) as total FROM `tabSales Invoice` WHERE docstatus=1 GROUP BY DATE(posting_date)"
  },
  "chart_config": {
    "chart_type": "line",
    "title": "Daily Sales Trend",
    "x_column": "date",
    "y_column": "total"
  }
}
```

### Pie Chart from Data

```json
{
  "data_source": {
    "type": "data",
    "data": [
      {"status": "Paid", "count": 45},
      {"status": "Unpaid", "count": 20},
      {"status": "Overdue", "count": 10}
    ]
  },
  "chart_config": {
    "chart_type": "pie",
    "title": "Invoice Status Distribution",
    "x_column": "status"
  }
}
```

### Scatter Plot

```json
{
  "data_source": {
    "type": "doctype",
    "doctype": "Item",
    "fields": ["valuation_rate", "standard_rate"],
    "filters": {"disabled": 0}
  },
  "chart_config": {
    "chart_type": "scatter",
    "title": "Valuation vs Standard Rate",
    "x_column": "valuation_rate",
    "y_column": "standard_rate"
  }
}
```

### Heatmap (Correlation)

```json
{
  "data_source": {
    "type": "doctype",
    "doctype": "Sales Invoice",
    "fields": ["grand_total", "discount_amount", "outstanding_amount"],
    "limit": 500
  },
  "chart_config": {
    "chart_type": "heatmap",
    "title": "Field Correlations"
  }
}
```

## Styling Options

```json
{
  "styling": {
    "theme": "default",           // default, dark, whitegrid, darkgrid
    "color_palette": "viridis",   // default, viridis, plasma, cool, warm
    "figure_size": [10, 6],       // width, height in inches
    "dpi": 150                    // resolution
  }
}
```

## Response Format

```json
{
  "success": true,
  "visualization": "base64_encoded_png_data...",
  "format": "base64",
  "chart_type": "bar",
  "title": "Sales by Customer",
  "data_points": 50,
  "display_hint": "Base64 encoded PNG image. Use in <img> tag or save as PNG file."
}
```

## Output Formats

| Format | Description | Use Case |
|--------|-------------|----------|
| base64 | Base64 encoded PNG | Web display, embedding |
| svg | SVG vector format | Scalable graphics |
| html | Interactive HTML | Plotly charts |
| json | Chart data | Further processing |

## Chart Types

| Type | Best For |
|------|----------|
| bar | Comparing categories |
| line | Trends over time |
| pie | Proportions/percentages |
| scatter | Relationships between variables |
| histogram | Distribution of values |
| box | Statistical distribution |
| heatmap | Correlation matrices |
| area | Cumulative trends |

## Related Tools

- **create_dashboard_chart** - Create charts for Frappe dashboards
- **run_python_code** - Custom visualizations with full matplotlib control
- **analyze_business_data** - Statistical analysis before visualization

# Prompt Templates User Guide

Prompt Templates in Frappe Assistant Core (FAC) provide a powerful way to create reusable, parameterized prompts for your AI assistant. This guide covers all features, from basic usage to advanced customization.

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Creating Prompt Templates](#creating-prompt-templates)
4. [Template Arguments](#template-arguments)
5. [Rendering Engines](#rendering-engines)
6. [Categories](#categories)
7. [Visibility and Sharing](#visibility-and-sharing)
8. [Versioning](#versioning)
9. [System Templates](#system-templates)
10. [MCP Integration](#mcp-integration)
11. [API Reference](#api-reference)
12. [Best Practices](#best-practices)

---

## Overview

Prompt Templates allow you to:

- Create standardized prompts for common analysis tasks
- Define configurable arguments that users can customize
- Organize prompts into categories for easy discovery
- Share prompts across teams with role-based access control
- Track usage analytics and version history
- Expose prompts via the MCP protocol to AI clients

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Prompt ID** | Unique identifier used in MCP (e.g., `sales_analysis`) |
| **Template Content** | The prompt text with placeholders for arguments |
| **Arguments** | Configurable parameters that customize the prompt |
| **Category** | Hierarchical organization for prompts |
| **Visibility** | Access control (Private, Shared, Public) |

---

## Quick Start

### Accessing Prompt Templates

1. Navigate to **Assistant Core > Prompt Template** in your Frappe desk
2. Click **+ Add Prompt Template** to create a new template
3. Fill in the required fields and save

### Using a Prompt via MCP

Once published, prompts are available via MCP:

```bash
# List available prompts
curl -X POST https://your-site.com/api/method/frappe_assistant_core.api.mcp_endpoint.handle_mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "prompts/list", "id": 1}'

# Get a specific prompt with arguments
curl -X POST https://your-site.com/api/method/frappe_assistant_core.api.mcp_endpoint.handle_mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "prompts/get",
    "params": {
      "name": "sales_analysis",
      "arguments": {
        "analysis_focus": "revenue_trends",
        "time_period": "last_month"
      }
    },
    "id": 2
  }'
```

---

## Creating Prompt Templates

### Required Fields

| Field | Description |
|-------|-------------|
| **Prompt ID** | Unique identifier (lowercase, alphanumeric, hyphens, underscores only) |
| **Title** | Human-readable name displayed in lists |
| **Template Content** | The actual prompt text with placeholders |

### Optional Fields

| Field | Description |
|-------|-------------|
| **Description** | Brief explanation shown in MCP prompt lists |
| **Category** | Link to a Prompt Category for organization |
| **Status** | Draft (hidden) or Published (visible to users) |
| **Visibility** | Private, Shared, or Public access |
| **Rendering Engine** | Jinja2, Format String, or Raw |

### Example: Creating a Sales Analysis Prompt

```
Prompt ID: sales_analysis
Title: Sales Analysis
Description: Analyze sales performance with customizable focus areas
Status: Published
Visibility: Public
Category: Sales & CRM
Rendering Engine: Jinja2

Template Content:
---
Perform a comprehensive sales analysis focusing on {{ analysis_focus }}
for the {{ time_period }} period.

**Analysis Scope:**
1. Revenue trends and comparisons
2. Customer insights and segmentation
3. Product performance metrics

{% if include_territory %}
**Territory Breakdown:**
- Regional performance comparison
- Market penetration by area
{% endif %}

Use the query_and_analyze tool to extract data from Sales Invoice,
Sales Order, and Customer DocTypes.
---
```

---

## Template Arguments

Arguments make your prompts configurable. They are defined in the **Arguments** child table.

### Argument Types

| Type | Description | Example |
|------|-------------|---------|
| `string` | Free-form text input | DocType name, search query |
| `number` | Numeric value | Limit, threshold |
| `boolean` | True/False toggle | Include optional sections |
| `select` | Single choice from options | Analysis focus area |
| `multiselect` | Multiple choices | Selected modules |

### Argument Properties

| Property | Description |
|----------|-------------|
| **Argument Name** | Variable name used in template (e.g., `analysis_focus`) |
| **Display Label** | Human-readable label (e.g., "Analysis Focus") |
| **Argument Type** | One of the types above |
| **Is Required** | Whether the argument must be provided |
| **Default Value** | Value used if not specified |
| **Description** | Help text explaining the argument |
| **Allowed Values** | Comma-separated options for select/multiselect |
| **Validation Regex** | Pattern for string validation |
| **Min/Max Length** | Length constraints for strings |

### Example: Select Argument with Options

```
Argument Name: time_period
Display Label: Time Period
Argument Type: select
Is Required: No
Default Value: last_month
Description: Analysis time period
Allowed Values: last_week,last_month,last_quarter,last_year,year_to_date
```

In MCP, this appears as:
```json
{
  "name": "time_period",
  "description": "Analysis time period. Options: last_week, last_month, last_quarter, last_year, year_to_date. Default: last_month",
  "required": false,
  "enum": ["last_week", "last_month", "last_quarter", "last_year", "year_to_date"],
  "default": "last_month"
}
```

---

## Rendering Engines

FAC supports three rendering engines for template processing:

### Jinja2 (Recommended)

Full-featured templating with conditionals, loops, and filters.

```jinja2
Analyze {{ doctype_name }} records from {{ time_period }}.

{% if include_details %}
Include detailed field-level analysis:
{% for field in fields %}
- {{ field }}
{% endfor %}
{% endif %}

Total records to analyze: {{ limit | default(100) }}
```

**Features:**
- Conditionals: `{% if condition %}...{% endif %}`
- Loops: `{% for item in list %}...{% endfor %}`
- Filters: `{{ value | upper }}`, `{{ value | default('N/A') }}`
- Comments: `{# This is a comment #}`

### Format String

Simple Python-style placeholders. Best for straightforward templates.

```
Analyze {doctype_name} records for the {time_period} period.
Focus on {analysis_focus} metrics.
```

**Features:**
- Simple variable substitution
- No conditionals or loops
- Faster processing

### Raw

No processing - template content is returned as-is.

Use for prompts that don't need parameterization.

---

## Categories

Categories provide hierarchical organization for prompt templates.

### System Categories

FAC includes these pre-installed categories:

| Category ID | Name | Description |
|-------------|------|-------------|
| `data-analysis` | Data Analysis | Parent category for analysis prompts |
| `manufacturing` | Manufacturing | Production, BOMs, work orders |
| `sales-crm` | Sales & CRM | Sales analysis, leads, customers |
| `purchasing` | Purchasing | Procurement, suppliers |
| `hr-payroll` | HR & Payroll | Employee metrics, attendance |
| `data-quality` | Data Quality | Data audits, validation |
| `documentation` | Documentation | DocType docs, guides |
| `system-admin` | System Administration | System tasks |

### Creating Custom Categories

1. Navigate to **Assistant Core > Prompt Category**
2. Create a new category with:
   - **Category ID**: Unique identifier (e.g., `custom-reports`)
   - **Category Name**: Display name (e.g., "Custom Reports")
   - **Parent Category**: Optional parent for hierarchy
   - **Is Group**: Check if this category will have children
   - **Icon**: FontAwesome icon class (e.g., `fa-chart-bar`)
   - **Color**: Category color for UI

### Searching by Category

```python
# Python API
from frappe_assistant_core.assistant_core.doctype.prompt_template.prompt_template import (
    get_prompts_by_category
)

prompts = get_prompts_by_category("sales-crm")
# Returns all prompts in sales-crm and its subcategories
```

---

## Visibility and Sharing

Control who can access your prompt templates.

### Visibility Levels

| Level | Description |
|-------|-------------|
| **Private** | Only visible to the owner |
| **Shared** | Visible to users with specified roles |
| **Public** | Visible to all users with Assistant User role |

### Role-Based Sharing

When visibility is "Shared":

1. Add roles to the **Shared With Roles** table
2. Only users with at least one of those roles can access the prompt
3. System Manager can always access all prompts

### Permission Hierarchy

```
System Manager → Can access everything
Owner → Can access their own prompts (any status)
Public + Published → Everyone with Assistant User role
Shared + Published → Users with specified roles
System Template → Everyone (is_system=1)
```

---

## Versioning

FAC tracks changes to prompt templates automatically.

### Automatic Version Increment

The `version_number` field increments automatically when you change:
- Template content
- Rendering engine
- Arguments (add/remove/modify)

Changes to title, description, or metadata do NOT increment the version.

### Version History

View the complete change history:

1. Open a Prompt Template
2. Click **Actions > Version History**
3. See all changes with timestamps and authors
4. Click **Restore** to revert to any previous version

This uses Frappe's built-in Version tracking (`track_changes=1`).

### Creating Named Versions

Create an explicit copy with a new prompt_id:

1. Open the template
2. Click **Actions > Create New Version**
3. Add optional version notes
4. A new template is created with `_v2` suffix

### Duplicating as Private

Copy any template (including system templates) for personal customization:

1. Open the template
2. Click **Actions > Duplicate as Private**
3. A private copy is created for your user

---

## System Templates

FAC includes pre-built templates for common analysis tasks.

### Included System Templates

| Prompt ID | Title | Category |
|-----------|-------|----------|
| `manufacturing_analysis` | Manufacturing Analysis | Manufacturing |
| `sales_analysis` | Sales Analysis | Sales & CRM |
| `purchase_analysis` | Purchase Analysis | Purchasing |
| `hr_analysis` | HR Analysis | HR & Payroll |
| `crm_analysis` | CRM Analysis | Sales & CRM |
| `doctype_documentation` | DocType Documentation Generator | Documentation |
| `data_quality_audit` | Data Quality Audit | Data Quality |

### System Template Properties

- **Cannot be deleted** (is_system=1 flag)
- **Cannot be modified directly** (UI shows warning)
- **Always visible** to all users
- **Updated via migration** (`bench migrate`)

### Customizing System Templates

To customize a system template:

1. Open the system template
2. Click **Actions > Duplicate as Private**
3. Modify your private copy
4. Publish when ready

---

## MCP Integration

Prompt Templates integrate with the Model Context Protocol (MCP).

### prompts/list

Returns all prompts accessible to the current user:

```json
{
  "jsonrpc": "2.0",
  "method": "prompts/list",
  "id": 1
}
```

Response:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "prompts": [
      {
        "name": "sales_analysis",
        "title": "Sales Analysis",
        "description": "Analyze sales performance...",
        "arguments": [
          {
            "name": "analysis_focus",
            "description": "Primary focus area. Options: revenue_trends, customer_analysis...",
            "required": true,
            "enum": ["revenue_trends", "customer_analysis", "..."],
            "default": null
          }
        ]
      }
    ]
  }
}
```

### prompts/get

Retrieve and render a specific prompt:

```json
{
  "jsonrpc": "2.0",
  "method": "prompts/get",
  "params": {
    "name": "sales_analysis",
    "arguments": {
      "analysis_focus": "revenue_trends",
      "time_period": "last_quarter",
      "include_territory": true
    }
  },
  "id": 2
}
```

Response:
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "description": "Analyze sales performance...",
    "messages": [
      {
        "role": "user",
        "content": {
          "type": "text",
          "text": "Perform a comprehensive sales analysis focusing on revenue_trends..."
        }
      }
    ]
  }
}
```

### Usage Analytics

Each `prompts/get` call:
- Increments `use_count` on the template
- Updates `last_used` timestamp
- Allows tracking popular prompts

---

## API Reference

### Python API

```python
import frappe
from frappe_assistant_core.assistant_core.doctype.prompt_template.prompt_template import (
    preview_template,
    get_version_history,
    restore_version,
    search_prompts,
    get_popular_prompts,
    get_prompts_by_category,
)

# Preview a template with test arguments
result = preview_template(
    template_content="Analyze {{ doctype }} for {{ period }}",
    rendering_engine="Jinja2",
    arguments={"doctype": "Sales Invoice", "period": "last month"}
)

# Search prompts
prompts = search_prompts(
    query="sales",
    category="sales-crm",
    status="Published",
    limit=10
)

# Get popular prompts
popular = get_popular_prompts(limit=5)

# Get prompts by category (includes subcategories)
category_prompts = get_prompts_by_category("data-analysis")
```

### REST API

```bash
# Preview template
curl -X POST "https://your-site.com/api/method/frappe_assistant_core.assistant_core.doctype.prompt_template.prompt_template.preview_template" \
  -H "Content-Type: application/json" \
  -d '{
    "template_content": "Analyze {{ doctype }}",
    "rendering_engine": "Jinja2",
    "arguments": {"doctype": "Customer"}
  }'

# Search prompts
curl -X POST "https://your-site.com/api/method/frappe_assistant_core.assistant_core.doctype.prompt_template.prompt_template.search_prompts" \
  -H "Content-Type: application/json" \
  -d '{"query": "analysis", "status": "Published"}'
```

---

## Best Practices

### Template Design

1. **Be specific about tools**: Mention which FAC tools the AI should use
   ```
   Use the query_and_analyze tool to fetch data from Sales Invoice.
   ```

2. **Structure output expectations**: Guide the AI on response format
   ```
   Present findings in these sections:
   1. Executive Summary
   2. Key Metrics
   3. Recommendations
   ```

3. **Use conditionals wisely**: Make optional sections clear
   ```jinja2
   {% if include_details %}
   ## Detailed Analysis
   ...
   {% endif %}
   ```

4. **Provide context**: Help the AI understand the business domain
   ```
   **Relevant DocTypes:** Sales Invoice, Sales Order, Customer, Item
   ```

### Argument Design

1. **Use descriptive names**: `analysis_focus` not `af`
2. **Provide helpful descriptions**: Explain what each option does
3. **Set sensible defaults**: Most common choice should be default
4. **Limit select options**: 3-7 options is ideal
5. **Mark truly required fields**: Don't over-require

### Organization

1. **Use categories**: Group related prompts together
2. **Consistent naming**: `{domain}_{action}` (e.g., `sales_analysis`)
3. **Version notes**: Document why you created a new version
4. **Status workflow**: Draft → Test → Published

### Security

1. **Visibility**: Start with Private, expand as needed
2. **Role-based sharing**: Use specific roles, not broad ones
3. **Avoid sensitive data**: Don't hardcode credentials or PII
4. **Review system templates**: Customize before production use

---

## Troubleshooting

### Prompt not appearing in MCP list

1. Check **Status** is "Published"
2. Verify **Visibility** allows access
3. Confirm user has required roles
4. Run `bench migrate` if recently installed

### Template syntax errors

1. Use **Actions > Preview** to test rendering
2. Check Jinja2 syntax (matching `{% %}` tags)
3. Verify all placeholders have matching arguments

### Version not incrementing

Version only increments for significant changes:
- Template content
- Rendering engine
- Arguments (type, required, allowed values)

Metadata changes (title, description) don't increment version.

### Categories not showing

1. Run `bench migrate` to install system categories
2. Check **Prompt Category** list for available options
3. Create custom categories if needed

---

## Migration Notes

### Installing/Updating System Data

System categories and templates are installed via migration hooks:

```bash
bench --site your-site migrate
```

This will:
1. Create/update system prompt categories
2. Create/update system prompt templates
3. Remove obsolete system templates no longer in data files

### Data Files Location

- Categories: `frappe_assistant_core/data/system_prompt_categories.json`
- Templates: `frappe_assistant_core/data/system_prompt_templates.json`

---

## Support

For issues or feature requests:
- GitHub: [frappe_assistant_core issues](https://github.com/your-repo/frappe_assistant_core/issues)
- Frappe Forum: Tag with `frappe-assistant-core`

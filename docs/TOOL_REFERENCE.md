# Tool Reference Guide

## Overview

This document provides a comprehensive reference for all tools available in Frappe Assistant Core. Tools are organized by plugins and categories for easy discovery.

**Total Available Tools**: 21 tools across 4 active plugins

## Plugin Architecture

Tools are organized into plugins that can be enabled/disabled as needed:

| Plugin | Tools | Status | Description |
|--------|-------|--------|-------------|
| **Core** | 19 | Always Enabled | Essential Frappe operations |
| **Data Science** | 3 | Optional | Advanced analytics and Python execution |
| **Visualization** | 3 | Optional | Dashboard and chart creation |
| **WebSocket** | - | Optional | Real-time communication (under development) |
| **Batch Processing** | - | Optional | Background operations (under development) |

## Core Plugin Tools

### Document Management (5 tools)

#### create_document
- **Description**: Create new Frappe documents with validation
- **When to use**: User wants to add new records to the system
- **Key patterns**: "create a new", "add a", "make a"
- **Example**: "Create a new customer named ABC Corp"

#### get_document
- **Description**: Retrieve complete details of a specific document
- **When to use**: User knows the exact document ID/name and needs full details
- **Key patterns**: "show me", "get details of", "what is in"
- **Example**: "Show me details of Sales Invoice SINV-00001"

#### update_document
- **Description**: Modify existing document fields
- **When to use**: User wants to change data in existing records
- **Key patterns**: "update", "change", "modify", "edit", "set"
- **Example**: "Update the status of SO-00001 to Completed"

#### delete_document
- **Description**: Delete a document (with permission checks)
- **When to use**: User wants to remove records permanently
- **Key patterns**: "delete", "remove", "cancel"
- **Example**: "Delete the draft purchase order PO-00005"

#### list_documents
- **Description**: List and filter documents with pagination
- **When to use**: Primary tool for finding and browsing records
- **Key patterns**: "list", "show all", "find", "search for", "how many"
- **Example**: "List all sales invoices from last month"

### Search Tools (3 tools)

#### search_documents
- **Description**: Global search across all accessible DocTypes
- **When to use**: User doesn't know which DocType contains the information
- **Key patterns**: "search everywhere", "find across all", "global search"
- **Example**: "Search for 'electronics' across all documents"

#### search_doctype
- **Description**: Search within a specific DocType using text search
- **When to use**: User knows the DocType and wants text-based search
- **Key patterns**: "search in", "find in [DocType]"
- **Example**: "Search for 'pending' in Purchase Orders"

#### search_link
- **Description**: Get valid options for Link fields
- **When to use**: Need to populate or validate link field values
- **Key patterns**: "link options", "available values for", "valid options"
- **Example**: "What are the available customer groups?"

### Metadata Tools (5 tools)

#### get_doctype_info
- **Description**: Get complete DocType structure and field definitions
- **When to use**: Understanding data model and field requirements
- **Key patterns**: "structure of", "fields in", "schema"
- **Example**: "What fields are in the Sales Order DocType?"

#### metadata_list_doctypes
- **Description**: List all DocTypes accessible to the user
- **When to use**: Discovery of available data types in the system
- **Key patterns**: "list all doctypes", "what doctypes", "available types"
- **Example**: "Show me all available DocTypes"

#### get_doctype_info_fields
- **Description**: Get detailed field metadata including types and options
- **When to use**: Need field-level details for forms or validation
- **Key patterns**: "field types", "required fields", "field options"
- **Example**: "What are the required fields for Customer?"

#### metadata_permissions
- **Description**: Get permission details for DocTypes
- **When to use**: Understanding access control and security
- **Key patterns**: "permissions for", "who can access", "allowed to"
- **Example**: "What are my permissions for Sales Invoice?"

#### metadata_workflow
- **Description**: Get workflow configuration for DocTypes
- **When to use**: Understanding approval processes and document states
- **Key patterns**: "workflow for", "approval process", "states"
- **Example**: "Show me the workflow for Purchase Orders"

### Report Tools (3 tools)

#### generate_report
- **Description**: Execute Frappe reports with filters
- **When to use**: Running standard or custom business reports
- **Key patterns**: "run report", "execute", "generate report"
- **Example**: "Run the Sales Analytics report for Q1 2024"
- **Features**: 
  - Supports Script, Query, and Standard reports
  - Returns data with column definitions
  - Includes enhanced error handling

#### report_list
- **Description**: List all available reports with metadata
- **When to use**: Discovering what reports are available
- **Key patterns**: "list reports", "available reports", "what reports"
- **Example**: "Show me all sales-related reports"

#### report_columns
- **Description**: Get report structure without executing
- **When to use**: Understanding report output before running
- **Key patterns**: "report columns", "report structure", "what fields"
- **Example**: "What columns are in the Accounts Receivable report?"

### Workflow Tools (3 tools)

#### workflow_action
- **Description**: Execute workflow transitions (approve, reject, etc.)
- **When to use**: Moving documents through workflow states
- **Key patterns**: "approve", "reject", "submit for", "transition"
- **Example**: "Approve Purchase Order PO-00123"

#### workflow_list
- **Description**: List documents pending workflow actions
- **When to use**: Viewing workflow queues and pending approvals
- **Key patterns**: "pending approvals", "workflow queue", "awaiting"
- **Example**: "Show me all pending purchase orders"

#### workflow_status
- **Description**: Get current workflow state of a document
- **When to use**: Checking document approval status
- **Key patterns**: "workflow status", "approval state", "current state"
- **Example**: "What's the workflow status of SO-00045?"

## Data Science Plugin Tools

### run_python_code
- **Description**: Execute Python code in a secure sandbox
- **When to use**: Complex calculations, custom analysis, data transformations
- **Available libraries**: frappe, pandas, numpy, matplotlib, seaborn, datetime
- **Key patterns**: "calculate", "analyze with python", "custom code"
- **Example**: "Calculate the monthly growth rate using Python"
- **Features**:
  - Automatic import handling
  - Artifact streaming for plots
  - 30-second timeout
  - Access to Frappe data

### analyze_business_data
- **Description**: Automated statistical analysis of DocType data
- **When to use**: Quick insights without writing code
- **Analysis types**:
  - **profile**: Data overview and distributions
  - **statistics**: Descriptive statistics
  - **correlations**: Relationship analysis
  - **trends**: Time-based patterns
  - **quality**: Data quality assessment
- **Example**: "Analyze sales trends for the last quarter"

### run_database_query
- **Description**: Execute SELECT queries for custom analysis
- **When to use**: Complex joins, aggregations beyond standard tools
- **Key patterns**: "SQL query", "custom query", "join tables"
- **Example**: "Run a query to find top customers by region"
- **Security**: SELECT-only queries with validation

## Visualization Plugin Tools

### create_dashboard
- **Description**: Create complete Frappe dashboards
- **When to use**: Building comprehensive multi-chart dashboards
- **Key patterns**: "create dashboard", "build dashboard", "dashboard with"
- **Example**: "Create a sales performance dashboard"
- **Features**:
  - Multiple chart types
  - Automatic layout
  - Time series support
  - Professional styling

### create_dashboard_chart
- **Description**: Create individual dashboard charts
- **When to use**: Adding specific visualizations to dashboards
- **Chart types**: bar, line, pie, donut, percentage, heatmap
- **Key patterns**: "create chart", "visualize", "plot", "graph"
- **Example**: "Create a pie chart of sales by region"

### list_user_dashboards
- **Description**: List accessible dashboards
- **When to use**: Finding existing dashboards
- **Key patterns**: "my dashboards", "list dashboards", "show dashboards"
- **Example**: "Show me all my dashboards"

## Tool Selection Guide

### For Document Operations
1. **Finding records**: Start with `list_documents`
2. **Specific record**: Use `get_document`
3. **Creating**: Use `create_document`
4. **Modifying**: Use `update_document`
5. **Removing**: Use `delete_document`

### For Analysis
1. **Quick insights**: Use `analyze_business_data`
2. **Custom analysis**: Use `run_python_code`
3. **Complex queries**: Use `run_database_query`
4. **Standard reports**: Use `generate_report`

### For Visualization
1. **Full dashboard**: Use `create_dashboard`
2. **Single chart**: Use `create_dashboard_chart`
3. **Existing dashboards**: Use `list_user_dashboards`

### For System Understanding
1. **Data structure**: Use metadata tools
2. **Available data**: Use `metadata_list_doctypes`
3. **Permissions**: Use `metadata_permissions`
4. **Workflows**: Use `metadata_workflow`

## Best Practices

### Tool Chaining
Many tasks require multiple tools:
```
1. list_documents → find records
2. get_document → get full details
3. update_document → make changes
```

### Performance Considerations
- Use filters in `list_documents` to limit results
- Run `report_columns` before `generate_report` for large reports
- Batch operations when possible

### Security Notes
- All tools respect Frappe permissions
- Document-level and field-level security enforced
- SQL queries restricted to SELECT operations
- Python code executed in sandbox environment

## Recent Updates

### January 2025
- Visualization tools streamlined from 11 to 3 essential tools
- Enhanced report error handling and debugging
- Improved time series support in dashboards
- Better field validation across all tools

## Related Documentation

- For development: See [DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md)
- For API details: See [API_REFERENCE.md](API_REFERENCE.md)
- For architecture: See [ARCHITECTURE.md](ARCHITECTURE.md)
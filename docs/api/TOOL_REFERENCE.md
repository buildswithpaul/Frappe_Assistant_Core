# Tool Reference Guide

## Overview

This document provides a comprehensive reference for all tools available in Frappe Assistant Core. Tools are organized by plugins and categories for easy discovery.

**Total Available Tools**: 22 tools across 4 active plugins

## Plugin Architecture

Tools are organized into plugins that can be enabled/disabled as needed:

| Plugin | Tools | Status | Description |
|--------|-------|--------|-------------|
| **Core** | 19 | Always Enabled | Essential Frappe operations |
| **Data Science** | 4 | Optional | Advanced analytics, Python execution, and file processing |
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
- **Key patterns**: "list", "show all", "find", "search_documents for", "how many"
- **Example**: "List all sales invoices from last month"

### Search Tools (3 tools)

#### search_documents
- **Description**: Global search_documents across all accessible DocTypes
- **When to use**: User doesn't know which DocType contains the information
- **Key patterns**: "search_documents everywhere", "find across all", "global search_documents"
- **Example**: "Search for 'electronics' across all documents"

#### search_doctype
- **Description**: Search within a specific DocType using text search_documents
- **When to use**: User knows the DocType and wants text-based search_documents
- **Key patterns**: "search_documents in", "find in [DocType]"
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

### 🏆 Report Tools (3 tools) - **PRIORITIZE THESE FOR BUSINESS ANALYSIS**

#### generate_report
- **Description**: 🏆 **YOUR FIRST CHOICE** for professional business reports and analytics
- **When to use**: ANY time users ask for business analysis, sales data, financial reports
- **Key patterns**: "sales analysis", "revenue report", "profit analysis", "financial report", "business intelligence"
- **Example**: "Run the Sales Analytics report for Q1 2024"
- **Why use this first**: Pre-built, optimized, professionally formatted reports ready for management
- **Features**: 
  - Access to 183+ business reports across all modules
  - Supports Script, Query, and Standard reports
  - Returns data with proper calculations and totals

#### report_list
- **Description**: 🔍 **ESSENTIAL DISCOVERY TOOL** - Find the perfect business report
- **When to use**: **ALWAYS USE FIRST** when users ask for any business analysis
- **Key patterns**: "list reports", "available reports", "what reports", "find reports"
- **Example**: "Show me all sales-related reports" → Then use generate_report
- **Pro tip**: Filter by module (Selling, Accounts, Stock, HR) to find relevant reports quickly

#### report_requirements
- **Description**: 📋 **REPORT REQUIREMENTS ANALYZER** - Understand what you need before running reports
- **When to use**: When generate_report fails due to missing filters or you need to understand report capabilities and requirements
- **Key patterns**: "report requirements", "what does this report need", "required filters", "report structure"
- **Example**: "What are the requirements for the Sales Analytics report?"
- **Enhanced**: Now includes comprehensive metadata and advanced filter analysis

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

## Data Science Plugin Tools - **USE ONLY WHEN REPORTS DON'T SUFFICE**

### analyze_business_data
- **Description**: 📊 Custom statistical analysis when standard reports aren't enough
- **⚠️ When to use**: Only after checking available reports first with `report_list` and `generate_report`
- **✅ Try first**: Use `report_list` to find Sales Analytics, Profit & Loss, or other standard reports
- **Analysis types**:
  - **profile**: Data overview and distributions
  - **statistics**: Descriptive statistics  
  - **correlations**: Relationship analysis
  - **trends**: Time-based patterns
  - **quality**: Data quality assessment
- **Example**: After finding no suitable report, "Analyze custom field correlations in Sales Invoice data"

### run_python_code 🚀
- **Description**: ⚡ Advanced Python sandbox with **Multi-Tool Orchestration** capability
- **🎯 PRIMARY USE**: Write Python code that calls other tools using the `tools` API (80-95% token savings!)
- **When to use**:
  - **Data Analysis Workflows**: Fetch data with `tools.get_documents()` and analyze with pandas (RECOMMENDED)
  - **Report Post-Processing**: Run `tools.generate_report()` and perform additional analysis
  - **Complex Calculations**: Advanced mathematical models beyond standard tools
  - **Custom Visualizations**: matplotlib/seaborn charts (after analysis)
- **Available libraries**: frappe, pandas, numpy, matplotlib, seaborn, datetime
- **Tools API**:
  - `tools.get_documents(doctype, filters, fields, limit)` - Fetch documents inside sandbox
  - `tools.get_document(doctype, name)` - Get single document
  - `tools.generate_report(report_name, filters)` - Execute Frappe reports
- **Key patterns**: "analyze sales data", "customer analysis", "complex aggregation", "trend analysis"
- **Token Savings**: Process data in sandbox, return only insights (not raw data to LLM)
- **Example**: "Analyze top 10 customers by revenue from Sales Invoice data" → Code fetches data using `tools.get_documents()`, aggregates with pandas, returns summary
- **📖 Complete Guide**: [Python Code Orchestration Guide](../guides/PYTHON_CODE_ORCHESTRATION.md)

### run_database_query
- **Description**: Execute SELECT queries for custom analysis
- **When to use**: Complex joins, aggregations beyond standard tools
- **Key patterns**: "SQL query", "custom query", "join tables"
- **Example**: "Run a query to find top customers by region"
- **Security**: SELECT-only queries with validation

### extract_file_content 🆕
- **Description**: Extract content from various file formats for LLM processing
- **When to use**: Need to read and analyze documents, invoices, contracts, spreadsheets
- **Supported formats**:
  - **PDFs**: Text extraction, OCR for scanned documents, table extraction
  - **Images**: OCR text extraction (JPG, PNG, TIFF)
  - **Spreadsheets**: CSV and Excel data parsing with structured output
  - **Documents**: DOCX and TXT file content extraction
- **Operations**:
  - **extract**: General text/data extraction from any supported format
  - **ocr**: Optical character recognition for images and scanned PDFs
  - **parse_data**: Structured data extraction from CSV/Excel files
  - **extract_tables**: Table extraction from PDF documents
- **Key patterns**: "read invoice", "extract from PDF", "OCR scan", "parse spreadsheet"
- **Example use cases**:
  - "Extract text from the uploaded contract PDF"
  - "OCR this scanned invoice image"
  - "Parse the data from sales.csv file"
  - "Extract tables from the financial report PDF"
- **Features**:
  - Multi-language OCR support (English, French, German, Spanish, etc.)
  - Automatic format detection
  - Table extraction with structure preservation
  - Integration with Frappe File DocType
  - Content preparation optimized for LLM analysis

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

## 🎯 BUSINESS INTELLIGENCE DECISION TREE

### 🏆 For Business Analysis & Reporting (Priority Order):

#### 1. **📊 FIRST: Try `report_list`**
   - "Show me sales reports" 
   - "What financial reports are available?"
   - Filter by module: Selling, Accounts, Stock, HR, etc.
   - **Key insight**: 183+ pre-built business reports are available!

#### 2. **🏆 SECOND: Use `generate_report`** 
   - "Run Sales Analytics report"
   - "Generate Profit & Loss Statement"
   - "Execute Territory-wise Sales report"
   - **Why this first**: Professional, pre-optimized, presentation-ready

#### 3. **📈 THIRD: Use `analyze_business_data`**
   - Only when no standard report meets your needs
   - For custom statistical analysis (profile, trends, correlations)
   - For unique data combinations not covered by reports

#### 4. **🚀 ORCHESTRATED ANALYSIS: Use `run_python_code` with Tools API**
   - **RECOMMENDED for data analysis**: Fetch data with `tools.get_documents()` inside Python code
   - Achieves 80-95% token savings by processing data in sandbox
   - Complex aggregations, statistical analysis, custom calculations
   - Advanced visualizations with matplotlib/seaborn
   - **See**: [Python Code Orchestration Guide](../guides/PYTHON_CODE_ORCHESTRATION.md)

### 🚀 Quick Reference Examples:

#### **✅ MOST RELIABLE REPORTS:**
- **"Sales transactions"** → `generate_report` "Sales Register" (24 columns, very reliable)
- **"Customer balances"** → `generate_report` "Accounts Receivable Summary" (aging analysis)
- **"Customer ledger"** → `generate_report` "Customer Ledger Summary" (account balances)
- **"Product sales"** → `generate_report` "Item-wise Sales History" (19 columns)

#### **⚠️ ENHANCED REPORTS (now working):**
- **"Sales analytics"** → `generate_report` "Sales Analytics" (auto-adds value_quantity='Value')
- **"Quotation trends"** → `generate_report` "Quotation Trends" (auto-adds based_on='Item')

#### **🔄 ANALYSIS OPTIONS (Best to Good):**
- **🚀 BEST: Orchestrated Python** → Use `run_python_code` with `tools.get_documents()` for complex analysis (80-95% token savings)
- **📊 GOOD: Pre-built Reports** → Use `generate_report` for standard business intelligence
- **📈 GOOD: Statistical Tools** → Use `analyze_business_data` for standard statistical analysis
- **📝 FALLBACK: Direct Queries** → Use `list_documents` for simple data retrieval

### 🛠️ When Reports Need Help:
- **Filter errors** → Use `report_requirements` to understand what's needed
- **Understanding report capabilities** → Use `report_requirements` with include_metadata=true  
- **Planning complex reports** → Use `report_requirements` to see all options

---

## Tool Selection Guide by Category

### For Document Operations
1. **Finding records**: Start with `list_documents`
2. **Specific record**: Use `get_document`
3. **Creating**: Use `create_document`
4. **Modifying**: Use `update_document`
5. **Removing**: Use `delete_document`

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

- For development: See [DEVELOPMENT_GUIDE.md](../development/DEVELOPMENT_GUIDE.md)
- For API details: See [API_REFERENCE.md](API_REFERENCE.md)
- For architecture: See [ARCHITECTURE.md](../architecture/ARCHITECTURE.md)
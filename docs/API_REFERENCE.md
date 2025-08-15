# API Reference

## Plugin-Based Architecture

The Frappe Assistant Core uses a plugin-based architecture where tools are organized into discoverable plugins. This reference covers both the MCP protocol endpoints and the plugin-specific tool APIs.

## MCP Protocol Endpoints

### Core Endpoints

#### Initialize

```
POST /api/method/frappe_assistant_core.api.mcp.handle_mcp_request
```

Initializes MCP connection and returns server capabilities.

**Request:**

```json
{
  "jsonrpc": "2.0",
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-06-18",
    "capabilities": {}
  },
  "id": 1
}
```

**Response:**

```json
{
  "jsonrpc": "2.0",
  "result": {
    "protocolVersion": "2025-06-18",
    "capabilities": {
      "tools": {
        "listChanged": true
      }
    },
    "serverInfo": {
      "name": "frappe-assistant-core",
      "version": "1.2.0"
    }
  },
  "id": 1
}
```

#### List Tools

```
POST /api/method/frappe_assistant_core.api.mcp.handle_mcp_request
```

Returns list of available tools for current user.

**Request:**

```json
{
  "jsonrpc": "2.0",
  "method": "tools/list",
  "params": {},
  "id": 2
}
```

**Response:**

```json
{
  "jsonrpc": "2.0",
  "result": {
    "tools": [
      {
        "name": "create_document",
        "description": "Create a new Frappe document",
        "inputSchema": {
          "type": "object",
          "properties": {
            "doctype": { "type": "string" },
            "data": { "type": "object" }
          },
          "required": ["doctype", "data"]
        }
      }
    ]
  },
  "id": 2
}
```

#### Execute Tool

```
POST /api/method/frappe_assistant_core.api.mcp.handle_mcp_request
```

Executes a specific tool with provided arguments.

**Request:**

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "create_document",
    "arguments": {
      "doctype": "Customer",
      "data": {
        "customer_name": "Test Customer"
      }
    }
  },
  "id": 3
}
```

**Response:**

```json
{
  "jsonrpc": "2.0",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Customer created successfully with ID: CUST-00001"
      }
    ]
  },
  "id": 3
}
```

## Administrative Endpoints

### Plugin Management

#### Get Discovered Plugins

```
GET /api/method/frappe_assistant_core.api.plugin_api.get_discovered_plugins
```

Returns all discovered plugins with their status.

**Response:**

```json
{
  "success": true,
  "plugins": [
    {
      "name": "data_science",
      "display_name": "Data Science & Analytics",
      "version": "1.0.0",
      "can_enable": true,
      "loaded": false
    }
  ]
}
```

#### Refresh Plugins

```
POST /api/method/frappe_assistant_core.api.plugin_api.refresh_plugins
```

Refreshes plugin discovery.

**Response:**

```json
{
  "success": true,
  "message": "Plugin discovery completed",
  "plugin_count": 3
}
```

#### Get Available Tools

```
GET /api/method/frappe_assistant_core.api.plugin_api.get_available_tools
```

Returns all available tools with statistics.

**Response:**

```json
{
  "success": true,
  "tools": [...],
  "stats": {
    "total_tools": 20,
    "core_tools": 15,
    "plugin_tools": 5
  }
}
```

## Plugin Tools API

### Core Plugin Tools

#### Document Tools

#### create_document

Creates a new Frappe document.

**Parameters:**

- `doctype` (string, required): DocType name
- `data` (object, required): Document field data
- `submit` (boolean, optional): Whether to submit after creation

**Example:**

```json
{
  "doctype": "Customer",
  "data": {
    "customer_name": "ABC Corp",
    "customer_type": "Company"
  },
  "submit": false
}
```

#### get_document

Retrieves a specific document.

**Parameters:**

- `doctype` (string, required): DocType name
- `name` (string, required): Document ID
- `fields` (array, optional): Specific fields to retrieve

#### update_document

Updates an existing document.

**Parameters:**

- `doctype` (string, required): DocType name
- `name` (string, required): Document ID
- `data` (object, required): Fields to update

#### list_documents

Lists documents with filters.

**Parameters:**

- `doctype` (string, required): DocType name
- `filters` (object, optional): Filter conditions
- `fields` (array, optional): Fields to retrieve
- `limit` (integer, optional): Maximum records (default: 20)

#### delete_document

Deletes a document.

**Parameters:**

- `doctype` (string, required): DocType name
- `name` (string, required): Document ID
- `force` (boolean, optional): Force delete

#### Search Tools

#### search_documents

Searches across all accessible DocTypes.

**Parameters:**

- `query` (string, required): Search query
- `limit` (integer, optional): Results per DocType
- `doctypes` (array, optional): Specific DocTypes to search

#### search_doctype

Searches within a specific DocType.

**Parameters:**

- `doctype` (string, required): DocType to search
- `query` (string, required): Search query
- `fields` (array, optional): Fields to search in
- `limit` (integer, optional): Maximum results

#### search_link

Searches for link field options.

**Parameters:**

- `doctype` (string, required): Target DocType
- `query` (string, optional): Filter query
- `filters` (object, optional): Additional filters
- `limit` (integer, optional): Maximum options

#### Metadata Tools

#### get_doctype_info

Gets DocType metadata and structure.

**Parameters:**

- `doctype` (string, required): DocType name
- `include_fields` (boolean, optional): Include field definitions
- `include_permissions` (boolean, optional): Include permissions
- `include_links` (boolean, optional): Include linked DocTypes

#### metadata_list_doctypes

Lists all available DocTypes.

**Parameters:**

- `module` (string, optional): Filter by module
- `is_submittable` (boolean, optional): Filter by submittable
- `include_custom` (boolean, optional): Include custom DocTypes

#### get_doctype_info_fields

Gets detailed field information.

**Parameters:**

- `doctype` (string, required): DocType name
- `fieldtype` (string, optional): Filter by field type
- `required_only` (boolean, optional): Show only required fields

#### Report Tools

#### generate_report

Executes a Frappe report.

**Parameters:**

- `report_name` (string, required): Report name
- `filters` (object, optional): Report filters
- `format` (string, optional): Output format
- `limit` (integer, optional): Maximum rows

#### report_list

Lists available reports.

**Parameters:**

- `module` (string, optional): Filter by module
- `report_type` (string, optional): Filter by type
- `reference_doctype` (string, optional): Filter by DocType

#### get_report_data

Gets detailed report information.

**Parameters:**

- `report_name` (string, required): Report name
- `include_query` (boolean, optional): Include SQL query

#### Workflow Tools

#### workflow_action

Performs workflow action on document.

**Parameters:**

- `doctype` (string, required): Document type
- `docname` (string, required): Document ID
- `action` (string, required): Workflow action
- `comment` (string, optional): Action comment

#### workflow_status

Checks workflow status of document.

**Parameters:**

- `doctype` (string, required): Document type
- `docname` (string, required): Document ID

#### workflow_list

Lists documents in workflow queues.

**Parameters:**

- `doctype` (string, optional): Filter by DocType
- `workflow_state` (string, optional): Filter by state
- `assigned_to_me` (boolean, optional): Only assigned items
- `limit` (integer, optional): Maximum results

### Data Science Plugin Tools

#### run_python_code

Executes Python code safely.

**Parameters:**

- `code` (string, required): Python code
- `timeout` (integer, optional): Execution timeout
- `capture_output` (boolean, optional): Capture print output
- `return_variables` (array, optional): Variables to return

#### analyze_business_data

Performs statistical analysis on DocType data.

**Parameters:**

- `doctype` (string, required): DocType to analyze
- `analysis_type` (string, required): Type of analysis
- `fields` (array, optional): Fields to analyze
- `filters` (object, optional): Data filters
- `limit` (integer, optional): Maximum records

#### query_and_analyze

Executes SQL queries and analyzes results.

**Parameters:**

- `query` (string, required): SQL query (SELECT only)
- `analysis_type` (string, optional): Analysis type
- `parameters` (object, optional): Query parameters
- `limit` (integer, optional): Row limit

#### extract_file_content

Extracts content from various file formats for LLM processing.

**Parameters:**

- `file_url` (string, optional): File URL from Frappe (e.g., '/files/invoice.pdf')
- `file_name` (string, optional): File name from File DocType
- `operation` (string, required): Operation type
  - `extract`: General text/data extraction
  - `ocr`: OCR for images and scanned documents
  - `parse_data`: Structured data from CSV/Excel
  - `extract_tables`: Table extraction from PDFs
- `language` (string, optional): OCR language code (default: 'eng')
- `output_format` (string, optional): Output format ('json', 'text', 'markdown')
- `max_pages` (integer, optional): Max pages for PDFs (default: 50)

**Example:**

```json
{
  "file_url": "/files/contract.pdf",
  "operation": "extract",
  "output_format": "text"
}
```

**Response:**

```json
{
  "success": true,
  "content": "Extracted text content...",
  "file_info": {
    "name": "contract.pdf",
    "type": "pdf",
    "size": 245678
  },
  "pages": 10
}
```

### Visualization Plugin Tools

#### create_dashboard

Creates Frappe dashboards with multiple charts.

**Parameters:**

- `dashboard_name` (string, required): Name of the dashboard
- `doctype` (string, required): Primary DocType for data source
- `chart_configs` (array, required): Array of chart configurations
- `filters` (object, optional): Global filters for all charts

#### create_dashboard_chart

Creates individual Dashboard Chart documents.

**Parameters:**

- `chart_name` (string, required): Name of the chart
- `chart_type` (string, required): Chart type (bar, line, pie, donut, percentage, heatmap)
- `doctype` (string, required): DocType for data source
- `aggregate_field` (string, required): Field to aggregate
- `aggregate_function` (string, required): Aggregation function (Sum, Count, Average)
- `time_series` (object, optional): Time series configuration
- `filters` (object, optional): Chart-specific filters

#### list_user_dashboards

Lists user's accessible dashboards.

**Parameters:**

- `dashboard_type` (string, optional): Filter by dashboard type
- `include_shared` (boolean, optional): Include shared dashboards

## Error Handling

### Standard Error Response

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32603,
    "message": "Internal error",
    "data": {
      "error_type": "ValidationError",
      "details": "Missing required field: doctype"
    }
  },
  "id": 1
}
```

### Common Error Codes

- `-32700`: Parse error (Invalid JSON)
- `-32600`: Invalid request
- `-32601`: Method not found
- `-32602`: Invalid params
- `-32603`: Internal error

### Frappe-Specific Errors

- `PermissionError`: Insufficient permissions
- `ValidationError`: Invalid input data
- `DoesNotExistError`: Resource not found
- `DuplicateEntryError`: Duplicate data

## Authentication

### API Key Authentication

```http
Authorization: token api_key:api_secret
```

### Session Authentication

Standard Frappe session cookies for web requests.

## Rate Limiting

- Default: 60 requests per minute per user
- Configurable in Assistant Core Settings
- Exceeded requests return HTTP 429

## Response Formats

### Success Response

```json
{
  "success": true,
  "data": {...},
  "meta": {
    "count": 10,
    "total": 100
  }
}
```

### Error Response

```json
{
  "success": false,
  "error": "Error message",
  "error_type": "ValidationError"
}
```

## Pagination

For list endpoints:

```json
{
  "limit": 20,
  "offset": 0,
  "order_by": "creation desc"
}
```

## Filtering

Standard Frappe filters format:

```json
{
  "filters": {
    "disabled": 0,
    "creation": [">=", "2024-01-01"]
  }
}
```

## Field Selection

Specify fields to retrieve:

```json
{
  "fields": ["name", "customer_name", "creation"]
}
```

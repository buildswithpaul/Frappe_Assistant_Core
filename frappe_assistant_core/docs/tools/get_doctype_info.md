# get_doctype_info

Get DocType metadata including field definitions, required fields, and child tables. Essential for understanding document structure before creating or updating records.

## When to Use

- Before creating documents - understand required fields
- Learning DocType structure - field types, options, validations
- Discovering child tables - table fields and their structure
- Understanding link fields - what DocTypes they reference

## Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| doctype | string | Yes | The DocType name to get information about |

## Examples

### Get Customer DocType Info
```json
{
  "doctype": "Customer"
}
```

### Get Sales Invoice Structure
```json
{
  "doctype": "Sales Invoice"
}
```

### Get Item DocType Info
```json
{
  "doctype": "Item"
}
```

## Response Format

```json
{
  "success": true,
  "doctype": "Customer",
  "data": {
    "name": "Customer",
    "module": "Selling",
    "is_submittable": false,
    "is_tree": false,
    "autoname": "naming_series:",
    "fields": [
      {
        "fieldname": "customer_name",
        "fieldtype": "Data",
        "label": "Customer Name",
        "reqd": 1,
        "description": "Full name of the customer"
      },
      {
        "fieldname": "customer_type",
        "fieldtype": "Select",
        "label": "Customer Type",
        "options": "Company\nIndividual",
        "reqd": 1
      },
      {
        "fieldname": "customer_group",
        "fieldtype": "Link",
        "label": "Customer Group",
        "options": "Customer Group",
        "reqd": 1
      }
    ],
    "required_fields": ["customer_name", "customer_type", "customer_group"],
    "child_tables": [],
    "link_fields": [
      {"fieldname": "customer_group", "options": "Customer Group"},
      {"fieldname": "territory", "options": "Territory"}
    ]
  }
}
```

### DocType with Child Tables
```json
{
  "success": true,
  "doctype": "Sales Invoice",
  "data": {
    "name": "Sales Invoice",
    "is_submittable": true,
    "fields": [...],
    "required_fields": ["customer", "posting_date", "items"],
    "child_tables": [
      {
        "fieldname": "items",
        "options": "Sales Invoice Item",
        "label": "Items"
      },
      {
        "fieldname": "taxes",
        "options": "Sales Taxes and Charges",
        "label": "Taxes"
      }
    ]
  }
}
```

## Field Types Reference

| Field Type | Description | Example Values |
|------------|-------------|----------------|
| Data | Text input | "John Doe" |
| Select | Dropdown options | "Company" or "Individual" |
| Link | Reference to another DocType | "CUST-00001" |
| Int | Integer number | 10 |
| Float | Decimal number | 99.99 |
| Currency | Money value | 1500.00 |
| Date | Date value | "2024-06-15" |
| Datetime | Date and time | "2024-06-15 10:30:00" |
| Check | Boolean (0 or 1) | 1 |
| Text | Long text | "Description..." |
| Table | Child table | Array of objects |

## Common Patterns

### 1. Before Creating Documents
```
get_doctype_info (understand structure)
    ↓
create_document (with correct fields)
```

### 2. Understanding Child Tables
When `get_doctype_info` shows a child table, you can query that DocType too:
```
get_doctype_info (doctype: "Sales Invoice")
    → sees "items" child table with options: "Sales Invoice Item"
    ↓
get_doctype_info (doctype: "Sales Invoice Item")
    → understand item line fields
```

### 3. Finding Valid Link Options
For Link fields, use `list_documents` to find valid values:
```
get_doctype_info shows: customer_group links to "Customer Group"
    ↓
list_documents (doctype: "Customer Group")
    → get valid customer group names
```

## Key Information Returned

- **required_fields** - Fields that must be provided when creating
- **child_tables** - Table fields that accept arrays of child rows
- **link_fields** - Fields that reference other DocTypes
- **is_submittable** - Whether documents can be submitted
- **naming_series** - How document names are generated

## Related Tools

- **create_document** - Create documents after understanding structure
- **list_documents** - Find valid values for Link fields
- **search_link** - Search for link field options

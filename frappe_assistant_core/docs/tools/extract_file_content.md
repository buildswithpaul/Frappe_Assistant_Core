# extract_file_content

Extract text and data from various file formats for analysis and processing.

## When to Use

- Reading invoices, contracts, or reports from attachments
- Extracting data from CSV/Excel files
- OCR on scanned documents or images
- Extracting tables from PDFs
- Preparing documents for LLM analysis

## Supported Formats

| Format | Extensions | Capabilities |
|--------|------------|--------------|
| PDF | .pdf | Text extraction, table extraction, OCR for scanned |
| Images | .jpg, .jpeg, .png, .bmp, .tiff | OCR text extraction |
| Spreadsheets | .csv, .xlsx, .xls | Data parsing, column detection |
| Documents | .docx | Text and table extraction |
| Text | .txt | Direct content reading |

## Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| file_url | string | No* | - | File URL from Frappe (e.g., '/files/invoice.pdf') |
| file_name | string | No* | - | File name from File DocType |
| operation | string | Yes | - | Operation type (see below) |
| language | string | No | "eng" | OCR language code |
| output_format | string | No | "text" | Output format: "json", "text", "markdown" |
| max_pages | integer | No | 50 | Maximum PDF pages to process |

*Provide either `file_url` OR `file_name`

## Operations

| Operation | Description | Best For |
|-----------|-------------|----------|
| extract | Get text/data from file | PDFs, DOCX, TXT |
| ocr | Extract text from images | Scanned docs, images |
| parse_data | Structured data extraction | CSV, Excel |
| extract_tables | Extract tables from PDFs | Invoices, reports |

## Examples

### Extract PDF Content

```json
{
  "file_url": "/files/contract.pdf",
  "operation": "extract"
}
```

### OCR on Image

```json
{
  "file_url": "/files/scanned_invoice.jpg",
  "operation": "ocr",
  "language": "eng"
}
```

### Parse CSV Data

```json
{
  "file_name": "import_data.csv",
  "operation": "parse_data"
}
```

### Extract Excel Data

```json
{
  "file_url": "/files/sales_report.xlsx",
  "operation": "extract"
}
```

### Extract PDF Tables

```json
{
  "file_url": "/files/invoice.pdf",
  "operation": "extract_tables",
  "max_pages": 5
}
```

## Response Format

### PDF Extraction

```json
{
  "success": true,
  "content": "--- Page 1 ---\nContract Agreement...\n\n--- Page 2 ---\nTerms and Conditions...",
  "pages": 10,
  "extracted_pages": 10,
  "file_info": {
    "name": "contract.pdf",
    "type": "pdf",
    "size": 125000,
    "url": "/files/contract.pdf"
  }
}
```

### CSV/Excel Extraction

```json
{
  "success": true,
  "content": "CSV Data Summary:\nColumns: Name, Amount, Date\nTotal Rows: 100\n\nSample Data:\n...",
  "structured_data": {
    "columns": ["Name", "Amount", "Date"],
    "row_count": 100,
    "sample_data": [
      {"Name": "Item 1", "Amount": 100, "Date": "2024-01-15"},
      ...
    ],
    "data_types": {"Name": "object", "Amount": "int64", "Date": "object"}
  }
}
```

### Table Extraction

```json
{
  "success": true,
  "tables": [
    {
      "page": 1,
      "table_index": 1,
      "data": [
        {"Item": "Widget", "Qty": "10", "Price": "100"}
      ],
      "rows": 5,
      "columns": 3
    }
  ],
  "total_tables": 2,
  "pages_processed": 5
}
```

### OCR Result

```json
{
  "success": true,
  "content": "INVOICE\nInvoice No: INV-001\nDate: 2024-06-15\n...",
  "ocr_language": "eng"
}
```

## OCR Languages

Common language codes:
- `eng` - English
- `fra` - French
- `deu` - German
- `spa` - Spanish
- `chi_sim` - Simplified Chinese

## File Size Limit

Maximum file size: 50MB

## Dependencies

- **pypdf** - PDF extraction
- **Pillow** - Image processing
- **pandas** - CSV/Excel parsing
- **pytesseract** - OCR (requires tesseract-ocr system package)
- **pdfplumber** - PDF table extraction
- **python-docx** - DOCX extraction

## Common Workflows

### Analyze Invoice Attachment

1. Extract content:
   ```json
   {"file_url": "/files/invoice.pdf", "operation": "extract_tables"}
   ```

2. Process with `run_python_code` for analysis

### Import CSV Data

1. Parse file:
   ```json
   {"file_name": "import.csv", "operation": "parse_data"}
   ```

2. Review `structured_data` for column mapping

### Process Scanned Documents

1. OCR extraction:
   ```json
   {"file_url": "/files/scan.jpg", "operation": "ocr"}
   ```

2. Use extracted text for further processing

## Related Tools

- **run_python_code** - Process extracted data with pandas
- **create_document** - Create records from extracted data
- **analyze_business_data** - Analyze extracted datasets

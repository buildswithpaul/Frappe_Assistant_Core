# How to Use extract_file_content

## Overview

The `extract_file_content` tool extracts text and data from files stored in Frappe's file system. Supports PDF, images (OCR), spreadsheets, and documents.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `operation` | string | **Yes** | — | `"extract"`, `"ocr"`, `"parse_data"`, or `"extract_tables"` |
| `file_url` | string | Conditional | — | File URL from Frappe (e.g., `"/files/invoice.pdf"`) |
| `file_name` | string | Conditional | — | File name from File DocType. Provide `file_url` OR `file_name`. |
| `output_format` | string | No | `"text"` | `"text"`, `"json"`, or `"markdown"` |
| `language` | string | No | `"en"` | OCR language code |
| `max_pages` | integer | No | 50 | Max pages for PDFs |

## Operations

| Operation | Use for | Formats |
|-----------|---------|---------|
| `extract` | Get text content | PDF, DOCX, TXT |
| `ocr` | Extract text from images | JPG, PNG (uses PaddleOCR) |
| `parse_data` | Structured data extraction | CSV, Excel (XLSX) |
| `extract_tables` | Table extraction from PDFs | PDF |

## Best Practices

1. **Provide either `file_url` OR `file_name`** — not both. `file_url` is the path like `"/files/doc.pdf"` or `"/private/files/doc.pdf"`.
2. **Use `ocr` for images** — supports invoices, forms, receipts, screenshots.
3. **Use `parse_data` for spreadsheets** — returns structured data ready for analysis.
4. **Use `extract_tables` for PDF tables** — better than plain `extract` when PDFs contain tabular data.
5. **Set `output_format: "json"`** — for structured output suitable for further processing.
6. **Use `language` for non-English** — common codes: `"fr"`, `"de"`, `"es"`, `"ch"` (Chinese).

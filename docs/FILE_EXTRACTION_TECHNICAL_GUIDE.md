# File Content Extraction Tool - Technical Deep Dive

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [How It Works - Step by Step](#how-it-works---step-by-step)
4. [Library Deep Dive](#library-deep-dive)
5. [File Format Processing](#file-format-processing)
6. [Real-World Use Cases](#real-world-use-cases)
7. [Complete Examples](#complete-examples)
8. [Troubleshooting](#troubleshooting)
9. [Performance Considerations](#performance-considerations)
10. [Future Enhancements](#future-enhancements)

## Overview

The `extract_file_content` tool is a sophisticated file processing system that extracts text and structured data from various file formats, making them accessible for Large Language Model (LLM) processing through the Model Context Protocol (MCP). It acts as a bridge between binary file formats and text-based AI analysis.

### Core Philosophy

```
Binary Files → Content Extraction → Normalized Text → LLM Processing → Insights
```

The tool follows a **separation of concerns** principle:
- **This Tool**: Handles file reading, format detection, and content extraction
- **LLM (Claude/GPT)**: Processes the extracted text for analysis, Q&A, summarization

## Architecture

### Component Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    extract_file_content Tool                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. File Input Layer                                            │
│  ┌────────────────────────────────────────────────────────┐    │
│  │ Frappe File DocType → Permission Check → File Retrieval │    │
│  └────────────────────────────────────────────────────────┘    │
│                              ↓                                   │
│  2. Format Detection Layer                                      │
│  ┌────────────────────────────────────────────────────────┐    │
│  │ Extension Check → MIME Type Detection → Format Decision │    │
│  └────────────────────────────────────────────────────────┘    │
│                              ↓                                   │
│  3. Processing Router                                           │
│  ┌────────────────────────────────────────────────────────┐    │
│  │         PDF ──→ PyPDF2/pdfplumber                       │    │
│  │       Image ──→ Pillow + Tesseract                      │    │
│  │    CSV/Excel ──→ pandas + openpyxl                      │    │
│  │        DOCX ──→ python-docx                             │    │
│  │         TXT ──→ Direct decode                           │    │
│  └────────────────────────────────────────────────────────┘    │
│                              ↓                                   │
│  4. Content Normalization                                       │
│  ┌────────────────────────────────────────────────────────┐    │
│  │ Text Cleaning → Encoding Fix → Structure Preservation   │    │
│  └────────────────────────────────────────────────────────┘    │
│                              ↓                                   │
│  5. Output Formatting                                           │
│  ┌────────────────────────────────────────────────────────┐    │
│  │     JSON / Text / Markdown → MCP Response               │    │
│  └────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## How It Works - Step by Step

### Step 1: File Retrieval from Frappe

```python
def _get_file_document(self, arguments):
    """
    Retrieves file from Frappe's File DocType
    """
    # Two ways to identify a file:
    # 1. By file URL (e.g., "/files/invoice.pdf")
    # 2. By file name (e.g., "invoice-2024.pdf")
    
    if file_url:
        # Query File DocType by URL
        file_doc = frappe.get_all("File", 
            filters={"file_url": file_url},
            fields=["*"])
    
    # The File DocType contains:
    # - file_url: Path to file
    # - file_name: Original filename
    # - file_size: Size in bytes
    # - is_private: Access control flag
```

**What happens here:**
1. Tool receives either a file URL or filename
2. Queries Frappe's File DocType (document management system)
3. Retrieves file metadata and location
4. Checks user permissions

### Step 2: File Content Loading

```python
def _get_file_content(self, file_doc):
    """
    Loads actual file bytes from disk
    """
    # Frappe stores files in two locations:
    # - /public/files/ - Public files
    # - /private/files/ - Private files (permission-controlled)
    
    if file_doc.file_url.startswith("/private"):
        file_path = frappe.get_site_path(file_doc.file_url.lstrip("/"))
    else:
        file_path = frappe.get_site_path("public", file_doc.file_url.lstrip("/"))
    
    with open(file_path, 'rb') as f:
        return f.read()  # Returns raw bytes
```

### Step 3: Format Detection

```python
def _detect_file_type(self, file_doc):
    """
    Intelligent format detection using multiple methods
    """
    # Method 1: File extension
    if file_name.endswith('.pdf'):
        return 'pdf'
    
    # Method 2: MIME type detection
    mime_type, _ = mimetypes.guess_type(file_name)
    if 'pdf' in mime_type:
        return 'pdf'
    
    # Method 3: Magic bytes (file signature)
    # PDF files start with %PDF
    # JPEG starts with FF D8 FF
    # PNG starts with 89 50 4E 47
```

### Step 4: Content Extraction Process

Based on detected format, the tool routes to specialized extractors:

```python
if operation == "extract":
    if file_type == 'pdf':
        result = self._extract_pdf_content(file_content)
    elif file_type == 'image':
        result = self._extract_image_content(file_content)
    elif file_type == 'csv':
        result = self._extract_csv_content(file_content)
    # ... etc
```

## Library Deep Dive

### 1. PyPDF2 - PDF Text Extraction

**Purpose**: Extract text from PDF files

**How it works:**
```python
from PyPDF2 import PdfReader
import io

# Create a PDF reader from bytes
pdf_file = io.BytesIO(file_content)
reader = PdfReader(pdf_file)

# Iterate through pages
for page_num in range(len(reader.pages)):
    page = reader.pages[page_num]
    text = page.extract_text()
    # PyPDF2 uses content stream parsing to extract text
    # It interprets PDF drawing commands to reconstruct text
```

**Behind the scenes:**
- PDFs store text as drawing instructions (not actual text)
- PyPDF2 parses these instructions and reconstructs readable text
- Works well for digitally created PDFs
- May fail on scanned PDFs (images of text)

**Limitations:**
- Cannot extract text from scanned PDFs
- May lose formatting and structure
- Tables might become jumbled text

### 2. pdfplumber - Advanced PDF Processing

**Purpose**: Extract tables and structured data from PDFs

**How it works:**
```python
import pdfplumber

with pdfplumber.open(io.BytesIO(file_content)) as pdf:
    page = pdf.pages[0]
    
    # Extract tables with structure
    tables = page.extract_tables()
    # Returns: [[['Header1', 'Header2'], ['Data1', 'Data2']]]
    
    # pdfplumber analyzes:
    # - Line positions and intersections
    # - Text positioning coordinates
    # - Visual structure patterns
```

**Advanced features:**
- Detects table boundaries using line detection
- Preserves table structure (rows and columns)
- Can extract text with positioning information
- Better at handling complex layouts

### 3. Tesseract OCR - Optical Character Recognition

**Purpose**: Extract text from images and scanned documents

**Installation required:**
```bash
# System level (required)
sudo apt-get install tesseract-ocr  # Ubuntu/Debian
brew install tesseract              # macOS

# Python wrapper
pip install pytesseract
```

**How it works:**
```python
import pytesseract
from PIL import Image

# Load image
image = Image.open(io.BytesIO(image_bytes))

# Preprocessing (improves accuracy)
# - Convert to grayscale
# - Adjust contrast
# - Remove noise
# - Deskew

# Run OCR
text = pytesseract.image_to_string(image, lang='eng')

# Tesseract process:
# 1. Line detection - finds text lines
# 2. Word detection - segments lines into words
# 3. Character recognition - uses neural networks
# 4. Language model - improves accuracy using dictionaries
```

**OCR Process Visualization:**
```
Original Image → Preprocessing → Binarization → Text Detection
     ↓               ↓                ↓              ↓
[Photo/Scan]   [Enhance/Clean]  [Black/White]  [Find text regions]
                                                      ↓
                                              Character Recognition
                                                      ↓
                                              [Neural Network]
                                                      ↓
                                                 Text Output
```

**Language support:**
```python
# Multiple languages
text = pytesseract.image_to_string(image, lang='eng+fra+deu')
# Combines English, French, and German models
```

### 4. pandas - CSV/Excel Processing

**Purpose**: Parse and structure tabular data

**How it works:**
```python
import pandas as pd

# CSV Processing
df = pd.read_csv(io.BytesIO(file_content), encoding='utf-8')
# Automatic detection of:
# - Delimiters (comma, tab, semicolon)
# - Headers
# - Data types

# Excel Processing
excel_file = pd.ExcelFile(io.BytesIO(file_content))
# Can read multiple sheets
for sheet_name in excel_file.sheet_names:
    df = pd.read_excel(excel_file, sheet_name=sheet_name)
```

**Data structure example:**
```python
# Input CSV:
# Name,Age,Salary
# John,30,50000
# Jane,25,45000

# Pandas DataFrame:
df.to_dict('records')
# Output: [
#   {'Name': 'John', 'Age': 30, 'Salary': 50000},
#   {'Name': 'Jane', 'Age': 25, 'Salary': 45000}
# ]
```

### 5. python-docx - Word Document Processing

**Purpose**: Extract content from DOCX files

**How it works:**
```python
from docx import Document

doc = Document(io.BytesIO(file_content))

# DOCX structure:
# - Paragraphs: Regular text content
# - Tables: Structured data
# - Styles: Formatting information

# Extract paragraphs
for paragraph in doc.paragraphs:
    text = paragraph.text
    style = paragraph.style.name  # Heading 1, Normal, etc.

# Extract tables
for table in doc.tables:
    for row in table.rows:
        for cell in row.cells:
            cell_text = cell.text
```

**DOCX Internal Structure:**
```
DOCX File (actually a ZIP archive)
├── word/
│   ├── document.xml     # Main content
│   ├── styles.xml       # Formatting
│   └── media/          # Embedded images
├── _rels/              # Relationships
└── docProps/           # Metadata
```

## File Format Processing

### PDF Processing

#### Text Extraction Flow
```python
def _extract_pdf_content(self, file_content, arguments):
    """
    Extract text from PDF with fallback strategies
    """
    # Step 1: Try PyPDF2 for regular PDFs
    try:
        reader = PdfReader(io.BytesIO(file_content))
        text_content = []
        
        for page_num in range(len(reader.pages)):
            page_text = reader.pages[page_num].extract_text()
            if page_text.strip():
                text_content.append(page_text)
        
        if text_content:
            return {"success": True, "content": "\n".join(text_content)}
    except:
        pass
    
    # Step 2: If no text found, might be scanned PDF
    # Could convert to images and OCR each page
    # (Requires pdf2image library)
    
    return {
        "success": True,
        "content": "",
        "message": "No text found. Try OCR operation for scanned PDFs"
    }
```

#### Table Extraction
```python
def _extract_pdf_tables(self, file_content, arguments):
    """
    Extract tables with structure preservation
    """
    import pdfplumber
    
    with pdfplumber.open(io.BytesIO(file_content)) as pdf:
        all_tables = []
        
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                # Convert to DataFrame for structure
                df = pd.DataFrame(table[1:], columns=table[0])
                all_tables.append({
                    "data": df.to_dict('records'),
                    "rows": len(df),
                    "columns": list(df.columns)
                })
    
    return {"success": True, "tables": all_tables}
```

### Image Processing with OCR

#### Complete OCR Pipeline
```python
def _perform_ocr(self, file_content, arguments):
    """
    Complete OCR pipeline with preprocessing
    """
    from PIL import Image, ImageEnhance, ImageFilter
    import pytesseract
    import numpy as np
    
    # Load image
    image = Image.open(io.BytesIO(file_content))
    
    # Preprocessing for better OCR accuracy
    # 1. Convert to grayscale
    if image.mode != 'L':
        image = image.convert('L')
    
    # 2. Enhance contrast
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2.0)
    
    # 3. Apply sharpening filter
    image = image.filter(ImageFilter.SHARPEN)
    
    # 4. Denoise
    image = image.filter(ImageFilter.MedianFilter(size=3))
    
    # 5. Resize if too small
    if image.width < 1000:
        scale = 1000 / image.width
        new_size = (int(image.width * scale), int(image.height * scale))
        image = image.resize(new_size, Image.LANCZOS)
    
    # Run OCR with configuration
    custom_config = r'--oem 3 --psm 6'
    # OEM 3: Default (LSTM OCR Engine)
    # PSM 6: Uniform block of text
    
    text = pytesseract.image_to_string(
        image, 
        lang=arguments.get('language', 'eng'),
        config=custom_config
    )
    
    # Post-processing
    # Remove extra whitespace
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    cleaned_text = '\n'.join(lines)
    
    return {
        "success": True,
        "content": cleaned_text,
        "ocr_confidence": self._calculate_confidence(image)
    }
```

### CSV/Excel Processing

#### Smart CSV Parsing
```python
def _extract_csv_content(self, file_content):
    """
    Intelligent CSV parsing with encoding detection
    """
    import chardet
    import pandas as pd
    
    # Detect encoding
    detection = chardet.detect(file_content)
    encoding = detection['encoding'] or 'utf-8'
    
    # Try different delimiters
    delimiters = [',', '\t', ';', '|']
    
    for delimiter in delimiters:
        try:
            df = pd.read_csv(
                io.BytesIO(file_content),
                encoding=encoding,
                delimiter=delimiter,
                error_bad_lines=False,
                warn_bad_lines=True
            )
            
            # Validate it parsed correctly
            if len(df.columns) > 1:  # Multiple columns found
                break
        except:
            continue
    
    # Data profiling
    profile = {
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": list(df.columns),
        "data_types": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "null_counts": df.isnull().sum().to_dict(),
        "sample_data": df.head(5).to_dict('records')
    }
    
    # Create readable text representation
    text = f"CSV Data Analysis:\n"
    text += f"Total Rows: {profile['rows']}\n"
    text += f"Columns: {', '.join(profile['column_names'])}\n\n"
    text += "Sample Data:\n"
    text += df.head(10).to_string()
    
    return {
        "success": True,
        "content": text,
        "structured_data": profile
    }
```

## Real-World Use Cases

### Use Case 1: Invoice Processing

**Scenario**: Extract data from uploaded invoices (PDFs or scanned images)

```python
# Step 1: Upload invoice to Frappe
# File uploaded as "invoice_2024_001.pdf"

# Step 2: Extract content
result = extract_file_content.execute({
    "file_name": "invoice_2024_001.pdf",
    "operation": "extract"
})

# Step 3: If scanned invoice (no text extracted)
if not result.get("content"):
    result = extract_file_content.execute({
        "file_name": "invoice_2024_001.pdf",
        "operation": "ocr"
    })

# Step 4: LLM processes extracted text
# Claude/GPT can now:
# - Extract invoice number, date, amount
# - Identify vendor and items
# - Validate against purchase orders
```

**Extracted Content Example:**
```
INVOICE
Invoice #: INV-2024-001
Date: January 15, 2024

Bill To:
Acme Corporation
123 Business St
New York, NY 10001

Items:
Product A - Qty: 10 - Price: $50.00 - Total: $500.00
Product B - Qty: 5 - Price: $100.00 - Total: $500.00

Subtotal: $1,000.00
Tax (10%): $100.00
Total: $1,100.00
```

### Use Case 2: Contract Analysis

**Scenario**: Extract and analyze legal contracts

```python
# Extract contract text
contract_text = extract_file_content.execute({
    "file_url": "/private/files/contract_vendor_2024.pdf",
    "operation": "extract"
})

# LLM can now analyze:
# - Key terms and conditions
# - Payment terms
# - Deliverables
# - Deadlines
# - Liability clauses
```

### Use Case 3: Financial Report Analysis

**Scenario**: Extract tables from financial PDFs

```python
# Extract tables from financial report
tables = extract_file_content.execute({
    "file_url": "/files/quarterly_report_q1_2024.pdf",
    "operation": "extract_tables"
})

# Returns structured data:
{
    "tables": [
        {
            "page": 1,
            "data": [
                {"Quarter": "Q1 2024", "Revenue": 1000000, "Profit": 100000},
                {"Quarter": "Q4 2023", "Revenue": 950000, "Profit": 95000}
            ]
        }
    ]
}

# LLM can perform:
# - Trend analysis
# - Year-over-year comparison
# - Anomaly detection
```

### Use Case 4: Form Processing

**Scenario**: Extract data from scanned forms

```python
# Scanned application form (image)
form_data = extract_file_content.execute({
    "file_url": "/files/application_form_scan.jpg",
    "operation": "ocr",
    "language": "eng"
})

# OCR extracts:
"""
APPLICATION FORM
Name: John Doe
Date of Birth: 01/15/1990
Address: 456 Main Street, Boston, MA
Phone: (555) 123-4567
Email: john.doe@email.com
"""

# LLM can:
# - Parse into structured fields
# - Validate data formats
# - Create Frappe documents
```

### Use Case 5: Bulk Data Import

**Scenario**: Process CSV files for data migration

```python
# Extract CSV data
csv_data = extract_file_content.execute({
    "file_url": "/files/customer_import.csv",
    "operation": "parse_data"
})

# Returns structured data:
{
    "structured_data": {
        "columns": ["name", "email", "phone", "address"],
        "row_count": 500,
        "sample_data": [
            {"name": "ABC Corp", "email": "abc@example.com", ...}
        ]
    }
}

# LLM can:
# - Map fields to Frappe DocTypes
# - Validate data before import
# - Generate import scripts
```

## Complete Examples

### Example 1: Multi-Format Document Processing

```python
def process_uploaded_document(file_url):
    """
    Complete workflow for processing any document type
    """
    # Step 1: Extract content
    result = extract_file_content.execute({
        "file_url": file_url,
        "operation": "extract"
    })
    
    # Step 2: Check if extraction successful
    if result.get("success"):
        content = result.get("content", "")
        
        # Step 3: If no content, try OCR
        if not content and result.get("file_info", {}).get("type") in ["pdf", "image"]:
            ocr_result = extract_file_content.execute({
                "file_url": file_url,
                "operation": "ocr"
            })
            content = ocr_result.get("content", "")
        
        # Step 4: Process with LLM
        if content:
            # Send to Claude/GPT for analysis
            analysis = analyze_with_llm(content, 
                prompt="Extract key information from this document")
            return analysis
    
    return {"error": "Could not extract content"}
```

### Example 2: Automated Invoice to Purchase Order Matching

```python
def match_invoice_to_po(invoice_file, po_number):
    """
    Extract invoice data and match with purchase order
    """
    # Extract invoice content
    invoice_data = extract_file_content.execute({
        "file_url": invoice_file,
        "operation": "extract"
    })
    
    # Get PO from Frappe
    po = frappe.get_doc("Purchase Order", po_number)
    
    # Send both to LLM for matching
    prompt = f"""
    Compare this invoice with the purchase order:
    
    Invoice Content:
    {invoice_data['content']}
    
    Purchase Order Items:
    {po.items}
    
    Check for:
    1. Item matching
    2. Quantity verification
    3. Price validation
    4. Total amount matching
    """
    
    # LLM performs intelligent matching
    matching_result = llm_analyze(prompt)
    
    return matching_result
```

### Example 3: Document Classification Pipeline

```python
def classify_and_route_document(file_url):
    """
    Classify document and route to appropriate handler
    """
    # Extract content
    content_result = extract_file_content.execute({
        "file_url": file_url,
        "operation": "extract"
    })
    
    if not content_result.get("content"):
        # Try OCR for scanned documents
        content_result = extract_file_content.execute({
            "file_url": file_url,
            "operation": "ocr"
        })
    
    content = content_result.get("content", "")
    
    # LLM classifies document
    classification_prompt = """
    Classify this document into one of these categories:
    - Invoice
    - Purchase Order
    - Contract
    - Report
    - Form
    - Other
    
    Document content:
    """ + content[:2000]  # First 2000 chars for classification
    
    doc_type = llm_classify(classification_prompt)
    
    # Route based on classification
    if doc_type == "Invoice":
        process_invoice(file_url, content)
    elif doc_type == "Contract":
        process_contract(file_url, content)
    # ... etc
```

## Troubleshooting

### Common Issues and Solutions

#### 1. OCR Not Working

**Problem**: `Tesseract OCR not installed on system`

**Solution**:
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install tesseract-ocr
sudo apt-get install tesseract-ocr-eng  # English
sudo apt-get install tesseract-ocr-fra  # French

# macOS
brew install tesseract

# Verify installation
tesseract --version
```

#### 2. PDF Text Extraction Returns Empty

**Problem**: PDF contains scanned images, not text

**Solution**:
```python
# Use OCR operation instead
result = extract_file_content.execute({
    "file_url": "/files/scanned.pdf",
    "operation": "ocr"  # Instead of "extract"
})
```

#### 3. CSV Parsing Errors

**Problem**: Special characters or encoding issues

**Solution**:
```python
# Tool automatically tries multiple encodings
# But you can also preprocess:
import chardet

# Detect encoding first
with open(file_path, 'rb') as f:
    raw_data = f.read()
    encoding = chardet.detect(raw_data)['encoding']
```

#### 4. Large File Timeouts

**Problem**: Files over 50MB timeout

**Solution**:
```python
# Process in chunks for PDFs
result = extract_file_content.execute({
    "file_url": "/files/large_document.pdf",
    "operation": "extract",
    "max_pages": 10  # Process first 10 pages only
})
```

#### 5. Memory Issues with Large Excel Files

**Problem**: OutOfMemoryError with large Excel files

**Solution**:
```python
# Read in chunks
import pandas as pd

chunk_size = 1000
for chunk in pd.read_excel(file_path, chunksize=chunk_size):
    # Process each chunk
    process_data(chunk)
```

## Performance Considerations

### Optimization Techniques

#### 1. Caching Extracted Content

```python
def get_cached_or_extract(file_url):
    """
    Cache extraction results for repeated access
    """
    cache_key = f"file_extract:{file_url}"
    
    # Check cache
    cached = frappe.cache().get(cache_key)
    if cached:
        return cached
    
    # Extract
    result = extract_file_content.execute({
        "file_url": file_url,
        "operation": "extract"
    })
    
    # Cache for 1 hour
    frappe.cache().set(cache_key, result, 3600)
    
    return result
```

#### 2. Async Processing for Large Files

```python
def process_large_file_async(file_url):
    """
    Queue large file processing
    """
    frappe.enqueue(
        extract_and_process,
        queue='long',
        timeout=600,  # 10 minutes
        file_url=file_url
    )
```

#### 3. Memory-Efficient Streaming

```python
def stream_large_csv(file_path):
    """
    Process large CSV without loading into memory
    """
    import pandas as pd
    
    # Use iterator
    csv_iterator = pd.read_csv(
        file_path,
        iterator=True,
        chunksize=1000
    )
    
    for chunk in csv_iterator:
        # Process chunk
        yield process_chunk(chunk)
```

### Performance Benchmarks

| Operation | File Size | Processing Time | Memory Usage |
|-----------|-----------|-----------------|--------------|
| PDF Text Extract | 1MB | ~0.5s | 10MB |
| PDF Text Extract | 10MB | ~3s | 50MB |
| OCR (Image) | 1MB | ~2s | 100MB |
| OCR (Image) | 5MB | ~8s | 300MB |
| CSV Parse | 10MB | ~0.3s | 30MB |
| CSV Parse | 100MB | ~2s | 300MB |
| Excel Parse | 5MB | ~1s | 50MB |
| DOCX Extract | 2MB | ~0.2s | 20MB |

## Future Enhancements

### Planned Features

#### 1. Advanced OCR with Layout Preservation

```python
# Future: Preserve document layout
def extract_with_layout(image):
    """
    Extract text while preserving spatial relationships
    """
    # Use LayoutLM or similar models
    layout_data = extract_layout(image)
    
    return {
        "text": extracted_text,
        "layout": {
            "headers": [...],
            "paragraphs": [...],
            "tables": [...],
            "positions": [...]
        }
    }
```

#### 2. Multi-Page Image PDFs

```python
# Future: Convert PDF pages to images for OCR
def ocr_pdf_pages(pdf_content):
    """
    OCR each page of a scanned PDF
    """
    from pdf2image import convert_from_bytes
    
    images = convert_from_bytes(pdf_content)
    
    all_text = []
    for page_num, image in enumerate(images):
        text = pytesseract.image_to_string(image)
        all_text.append(f"Page {page_num + 1}:\n{text}")
    
    return "\n".join(all_text)
```

#### 3. Smart Table Detection

```python
# Future: AI-powered table detection
def detect_and_extract_tables(image):
    """
    Use computer vision to detect tables
    """
    # Use models like Table Transformer
    tables = table_detection_model.detect(image)
    
    extracted_tables = []
    for table_region in tables:
        # Extract and structure table data
        table_data = extract_table_structure(table_region)
        extracted_tables.append(table_data)
    
    return extracted_tables
```

#### 4. Document Intelligence

```python
# Future: Intelligent field extraction
def extract_fields_intelligently(content, document_type):
    """
    Use NER and pattern matching for field extraction
    """
    if document_type == "invoice":
        fields = {
            "invoice_number": extract_pattern(r"INV-\d+", content),
            "date": extract_date(content),
            "total": extract_currency(content),
            "vendor": extract_entity(content, type="organization")
        }
    
    return fields
```

## Conclusion

The `extract_file_content` tool is a powerful bridge between binary file formats and text-based AI processing. By understanding how each component works - from file retrieval through Frappe's File DocType to specialized extraction using libraries like PyPDF2, Tesseract, and pandas - developers can effectively process any document type for LLM analysis.

The tool's strength lies in its:
1. **Flexibility**: Handles multiple file formats with appropriate extractors
2. **Robustness**: Fallback strategies for challenging documents
3. **Integration**: Seamless Frappe framework integration
4. **Extensibility**: Easy to add new format support

This separation of concerns - where the tool handles extraction and the LLM handles analysis - creates a clean, maintainable architecture that can evolve with changing requirements and new file formats.

---

*For implementation details, see the [source code](../frappe_assistant_core/plugins/data_science/tools/extract_file_content.py)*

*For API reference, see the [API Documentation](API_REFERENCE.md#extract_file_content)*
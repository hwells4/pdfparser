# PDF Parser System Analysis

## Overview

This document provides a comprehensive analysis of the PDF Parser microservice, which processes PDFs through two different Doctly API endpoints. Both endpoints now use identical asynchronous queue-based processing and produce consistent outputs for frontend integration.

## System Architecture

### Core Components

1. **FastAPI Application** (`main.py`) - Main web server with two processing endpoints
2. **Job Queue System** (`job_queue.py`) - In-memory thread-safe queue for asynchronous processing
3. **Background Worker** (`worker.py`) - Processes jobs from the queue in the background
4. **Doctly Client** (`doctly_client.py`) - Handles interactions with Doctly API services
5. **Table Parser** (`tableparser.py`) - Converts Markdown tables to CSV format
6. **S3 Utilities** (`s3_utils.py`) - Handles AWS S3 file operations

## Processing Systems

Both endpoints now use **identical asynchronous queue-based processing** with the only difference being the Doctly API endpoint used.

### Endpoint 1: PDF → Markdown → CSV Processing

**Endpoint:** `POST /parse`
**Doctly API:** Standard document processing (`/documents/`)
**Output Format:** Markdown tables converted to CSV

### Endpoint 2: PDF → JSON → CSV Processing  

**Endpoint:** `POST /parse-json`
**Doctly API:** Insurance extractor (`/e/insurance`)
**Output Format:** JSON data converted to CSV

## Unified Processing Workflow

Both endpoints follow this **identical workflow**:

### 1. Request Handling
```http
POST /parse (or /parse-json)
Headers: X-API-Key: your_api_key
Content-Type: application/json

{
  "s3_bucket": "your-bucket-name",
  "s3_key": "path/to/document.pdf", 
  "webhook_url": "https://your-app.com/webhook"
}
```

**Response:**
```json
{
  "status": "queued",
  "position": 1
}
```

### 2. Background Processing
1. **PDF Download** - Downloads PDF from S3 using provided bucket/key
2. **Doctly Processing** - Sends to appropriate Doctly API endpoint:
   - `/parse` → Standard API (`https://api.doctly.ai/api/v1/documents/`)
   - `/parse-json` → Insurance API (`https://api.doctly.ai/api/v1/e/insurance`)
3. **Content Conversion** - Converts result to CSV:
   - Markdown tables → CSV (via `tableparser.py`)
   - JSON data → CSV (via pandas normalization)
4. **S3 Upload** - Saves CSV to: `s3://{bucket}/processed/{filename}.csv`
5. **Webhook Notification** - Sends completion notification

### 3. File Storage Location

**S3 Path Pattern:** `s3://{input_bucket}/processed/{original_filename_without_extension}.csv`

**Examples:**
- Input: `s3://client-docs/invoices/invoice-123.pdf`
- Output: `s3://client-docs/processed/invoice-123.csv`

### 4. Webhook Notifications

**Webhook URL:** The exact URL provided in the request + `?document_id={doctly_document_id}`

**Success Webhook:**
```json
POST {webhook_url}?document_id=doc_abc123
Content-Type: application/json

{
  "status": "success",
  "csv_url": "https://s3.amazonaws.com/client-docs/processed/invoice-123.csv",
  "original_filename": "invoice-123.pdf",
  "document_id": "doc_abc123"
}
```

**Error Webhook:**
```json
POST {webhook_url}?document_id=doc_abc123
Content-Type: application/json

{
  "status": "error", 
  "message": "Detailed error description",
  "original_filename": "invoice-123.pdf",
  "document_id": "doc_abc123"
}
```

**Note:** If processing fails before getting a document ID, the webhook is sent to the original URL without the query parameter.

## Doctly API Details

### Standard API (`/parse` endpoint)
- **Endpoint:** `https://api.doctly.ai/api/v1/documents/`
- **Input:** PDF file
- **Output:** Markdown content with tables
- **Accuracy:** Auto-selected (< 500KB = "lite", >= 500KB = "ultra")
- **Processing Time:** Typically 2-15 minutes depending on document complexity

### Insurance API (`/parse-json` endpoint)
- **Endpoint:** `https://api.doctly.ai/api/v1/e/insurance`
- **Input:** PDF file
- **Output:** Structured JSON data
- **Specialization:** Optimized for insurance forms and documents
- **Processing Time:** Typically 2-15 minutes depending on document complexity

## Frontend Integration Guide

### API Authentication
All requests require an API key in the header:
```http
X-API-Key: your_api_key_here
```

### Error Responses
All endpoints return standard HTTP error codes:

**401 Unauthorized:**
```json
{
  "detail": "Invalid API key"
}
```

**429 Too Many Requests:**
```json
{
  "detail": "Too many failed attempts. Please try again later."
}
```

**500 Internal Server Error:**
```json
{
  "detail": "Missing environment variables: AWS_ACCESS_KEY_ID, DOCTLY_API_KEY"
}
```

### Monitoring and Status

**Health Check:**
```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "queue_size": 3,
  "service": "pdf-parser"
}
```

### CSV Output Format

Both endpoints produce CSV files with the following characteristics:

**Markdown Processing (`/parse`):**
- Extracts tables from documents
- Headers from first table row (if non-numeric)
- Falls back to "Column 1", "Column 2", etc. if no headers detected
- Filters out separator rows (`|---|---|`)
- Handles multi-line cell content

**JSON Processing (`/parse-json`):**
- Flattens nested JSON structures using pandas `json_normalize`
- Handles arrays, objects, and primitive types
- Creates columns for all JSON keys
- Nested objects become dot-notation columns (e.g., `person.name`, `person.age`)

### Integration Patterns

**1. Immediate Processing (Recommended):**
```javascript
// Submit document for processing
const response = await fetch('/parse-json', {
  method: 'POST',
  headers: {
    'X-API-Key': 'your-key',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    s3_bucket: 'your-bucket',
    s3_key: 'document.pdf',
    webhook_url: 'https://your-app.com/webhook'
  })
});

const result = await response.json();
// result = { status: "queued", position: 1 }

// Your webhook endpoint will receive the result
```

**2. Webhook Handler:**
```javascript
app.post('/webhook', (req, res) => {
  const { status, csv_url, original_filename, document_id } = req.body;
  
  if (status === 'success') {
    // Download CSV from csv_url
    // Update database with document_id
    // Notify user of completion
  } else {
    // Handle error case
    // Log error message
    // Notify user of failure
  }
  
  res.status(200).send('OK');
});
```

### Expected Processing Times

| Document Type | Size | Typical Processing Time |
|---------------|------|-------------------------|
| Simple Invoice | < 1MB | 2-5 minutes |
| Insurance Form | < 2MB | 3-8 minutes |
| Complex Report | 2-5MB | 5-15 minutes |
| Large Document | > 5MB | 10-25 minutes |

**Note:** Processing times vary based on document complexity, not just file size.

## Configuration Requirements

### Environment Variables
```bash
# Required
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key  
DOCTLY_API_KEY=your_doctly_api_key
API_KEY=your_service_api_key

# Optional
AWS_REGION=us-east-1
PORT=8000
LOG_LEVEL=INFO
```

### System Requirements
- **Memory:** 512MB minimum (recommended for Docker deployment)
- **CPU:** 0.5 cores minimum
- **Storage:** Temporary disk space for PDF/CSV files during processing
- **Network:** Outbound HTTPS access to Doctly API and S3

### Timeouts and Limits
- **Doctly Upload:** 300 seconds (5 minutes)
- **Doctly Polling:** 1800 seconds (30 minutes maximum)
- **Webhook Delivery:** 30 seconds
- **Queue Size:** Unlimited (in-memory)
- **Rate Limiting:** 5 failed auth attempts per IP (5 minute lockout)

## Deployment Considerations

### Production Recommendations
1. **Load Balancing:** Use multiple instances with shared S3 storage
2. **Monitoring:** Track queue depth and processing times
3. **Alerting:** Monitor webhook delivery failures
4. **Backup:** Ensure S3 bucket has proper backup policies
5. **Security:** Use IAM roles instead of access keys when possible

### Scaling Notes
- **Horizontal Scaling:** Deploy multiple instances behind load balancer
- **Queue Management:** Each instance has independent in-memory queue
- **S3 Coordination:** All instances can safely write to same S3 bucket
- **Document ID Uniqueness:** Doctly ensures unique document IDs across all requests

## Troubleshooting

### Common Issues

**Queue Not Processing:**
- Check background worker logs
- Verify AWS credentials
- Confirm Doctly API key validity

**Webhook Failures:**
- Ensure webhook URL is publicly accessible
- Check webhook endpoint returns 2xx status codes
- Verify webhook URL accepts POST requests

**CSV Upload Failures:**
- Confirm S3 bucket exists and is writable
- Check AWS IAM permissions for S3 operations
- Verify correct AWS region configuration

**Document Processing Timeouts:**
- Large/complex documents may exceed 30-minute limit
- Check Doctly API status for service issues
- Consider splitting large documents

## System Status

✅ **Both endpoints now fully operational with identical behavior**

**Recent Updates:**
- ✅ Fixed `/parse-json` synchronous processing issue
- ✅ Unified worker logic for both processing types  
- ✅ Standardized CSV output locations and webhook formats
- ✅ Removed deprecated synchronous processing code
- ✅ Added comprehensive test coverage

**Architecture Benefits:**
- **Scalable:** Handles concurrent requests efficiently
- **Reliable:** Background processing with error handling
- **Consistent:** Identical behavior between endpoints
- **Maintainable:** Single codebase for both processing types
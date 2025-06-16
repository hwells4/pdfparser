# PDF Parser Microservice

A FastAPI-based microservice that converts PDFs to CSV files using Doctly for Markdown conversion and AWS S3 for file storage.

## Overview

This service replaces AWS Textract workflows with a Doctly + Markdown parsing pipeline:

1. **Receives** PDF references from S3
2. **Converts** PDFs to Markdown via Doctly API
3. **Parses** Markdown tables into clean CSV format
4. **Uploads** results back to S3
5. **Notifies** via webhooks when complete

## Features

- 🚀 **FastAPI** web framework with async support
- 📋 **In-memory job queue** to serialize processing
- 🔄 **Background worker** for PDF processing
- 📊 **Markdown table parsing** to CSV
- ☁️ **AWS S3 integration** for file storage
- 🔔 **Webhook notifications** for job completion
- 🐳 **Docker support** for containerized deployment
- 🧪 **Comprehensive testing** with test runner

## Project Structure

```
pdf-parser/
├── main.py              # FastAPI application entrypoint
├── job_queue.py         # In-memory job queue system
├── worker.py            # Background worker for processing
├── s3_utils.py          # AWS S3 utilities
├── doctly_client.py     # Doctly API client
├── tableparser.py       # Markdown to CSV parser
├── requirements.txt     # Python dependencies
├── Dockerfile          # Docker configuration
├── docker-compose.yml  # Docker Compose configuration
├── env.example         # Environment variables template
├── scripts/
│   ├── test_runner.py  # End-to-end testing script
│   ├── test_docker_deployment.sh  # Docker deployment test
│   └── prd.txt         # Product requirements document
└── tasks/              # TaskMaster project management
```

## Quick Start

### 1. Environment Setup

Copy the environment template and configure your credentials:

```bash
cp env.example .env
```

Edit `.env` with your credentials:

```bash
# AWS S3 Configuration
AWS_ACCESS_KEY_ID=your_aws_access_key_here
AWS_SECRET_ACCESS_KEY=your_aws_secret_key_here
AWS_REGION=us-east-1

# Doctly API Configuration
DOCTLY_API_KEY=your_doctly_api_key_here

# Optional Configuration
S3_OUTPUT_PREFIX=processed
PORT=8000
LOG_LEVEL=INFO
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the Service

```bash
python main.py
```

The service will start on `http://localhost:8000`

### 4. Test the API

Check health status:
```bash
curl http://localhost:8000/health
```

Trigger a parse job:
```bash
curl -X POST http://localhost:8000/parse \
  -H "Content-Type: application/json" \
  -d '{
    "s3_bucket": "your-bucket",
    "s3_key": "path/to/document.pdf",
    "webhook_url": "https://your-app.com/webhook"
  }'
```

## Docker Deployment

### Option 1: Docker Compose (Recommended)

1. **Create environment file:**
   ```bash
   cp env.example .env
   # Edit .env with your actual credentials
   ```

2. **Deploy with Docker Compose:**
   ```bash
   docker-compose up -d
   ```

3. **Check status:**
   ```bash
   docker-compose ps
   docker-compose logs pdf-parser
   ```

4. **Test the deployment:**
   ```bash
   curl http://localhost:8000/health
   ```

### Option 2: Standalone Docker

1. **Build the image:**
   ```bash
   docker build -t pdf-parser .
   ```

2. **Run with environment variables:**
   ```bash
   docker run -d -p 8000:8000 \
     -e AWS_ACCESS_KEY_ID=your-access-key \
     -e AWS_SECRET_ACCESS_KEY=your-secret-key \
     -e DOCTLY_API_KEY=your-doctly-key \
     --name pdf-parser \
     pdf-parser
   ```

3. **Check logs:**
   ```bash
   docker logs pdf-parser
   ```

### Docker Deployment Testing

Run the comprehensive deployment test:

```bash
./scripts/test_docker_deployment.sh
```

This script will:
- Build the Docker image
- Test without credentials (should reject requests)
- Test with test credentials (should accept but fail on AWS)
- Verify health checks and endpoints
- Clean up automatically

### Production Deployment

For production environments:

1. **Use docker-compose with resource limits:**
   ```yaml
   # Already configured in docker-compose.yml
   deploy:
     resources:
       limits:
         memory: 512M
         cpus: '0.5'
   ```

2. **Set up monitoring:**
   - Health check endpoint: `GET /health`
   - Application logs via `docker logs`
   - Container metrics via Docker stats

3. **Environment variables:**
   ```bash
   # Required
   AWS_ACCESS_KEY_ID=your-access-key
   AWS_SECRET_ACCESS_KEY=your-secret-key
   DOCTLY_API_KEY=your-doctly-key
   
   # Optional
   PORT=8000
   AWS_REGION=us-east-1
   ```

## API Endpoints

### `POST /parse`

Initiates a PDF parsing job.

**Request Body:**
```json
{
  "s3_bucket": "client-uploads",
  "s3_key": "incoming/document.pdf",
  "webhook_url": "https://frontend.com/api/onCsvComplete"
}
```

**Response:**
```json
{
  "status": "queued",
  "position": 1
}
```

### `GET /health`

Returns service health status and queue information.

**Response:**
```json
{
  "status": "healthy",
  "queue_size": 0,
  "service": "pdf-parser"
}
```

## Webhook Notifications

Upon job completion, the service sends a POST request to the provided webhook URL:

**Success:**
```json
{
  "status": "success",
  "csv_url": "https://s3.amazonaws.com/bucket/processed/document.csv",
  "original_filename": "document.pdf"
}
```

**Error:**
```json
{
  "status": "error",
  "message": "Error description",
  "original_filename": "document.pdf"
}
```

## Testing

### End-to-End Testing

Use the included test runner for comprehensive testing:

```bash
python scripts/test_runner.py \
  --s3-bucket your-test-bucket \
  --create-sample \
  --api-url http://localhost:8000
```

### Manual Testing

1. Upload a PDF to your S3 bucket
2. Call the `/parse` endpoint with the S3 details
3. Monitor the webhook endpoint for completion notification
4. Check the processed CSV in S3

## Development

### Task Management

This project uses TaskMaster for task management. View current tasks:

```bash
# Install TaskMaster globally
npm install -g task-master-ai

# View tasks
task-master list

# Get next task
task-master next

# Mark task complete
task-master set-status --id=1 --status=done
```

### Adding Features

1. Check TaskMaster for next priority task
2. Implement the feature following the task details
3. Update tests as needed
4. Mark task as complete

## Error Handling

The service includes comprehensive error handling:

- **S3 download failures** → Webhook with error status
- **Doctly processing failures** → Webhook with error details
- **Malformed Markdown** → Best-effort CSV with fallback headers
- **Uncaught exceptions** → Logged and generic error webhook

## File Cleanup

- Temporary files are automatically cleaned up after processing
- Failed jobs also trigger cleanup
- In-memory queue resets on service restart

## Limitations

- **Single instance only** (in-memory queue assumption)
- **No retry queue persistence** (acceptable for current scope)
- **No admin dashboard** (out of scope)
- **No direct file uploads** (S3 references only)

## Contributing

1. Check TaskMaster for available tasks
2. Create feature branch
3. Implement changes with tests
4. Update documentation
5. Submit pull request

## License

[Add your license here]

## Support

For issues and questions:
- Check the TaskMaster tasks for known issues
- Review the test runner output for debugging
- Check service logs for detailed error information # Force redeploy

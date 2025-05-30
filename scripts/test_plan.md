# PDF Parser Microservice - Testing Plan

## 🎯 Overview
This document provides a comprehensive testing plan for the PDF Parser Microservice that was implemented by the previous agent. The service converts PDFs to CSV via Doctly API and S3 storage.

## 🔧 Critical Fix Applied
✅ **FIXED**: Added `TableParser` class wrapper to `tableparser.py` - the worker now properly imports and uses the table parsing functionality.

## 🏗️ Architecture Summary
- **FastAPI App** (`main.py`): REST API with `/parse` endpoint
- **Job Queue** (`queue.py`): Thread-safe in-memory job management
- **Background Worker** (`worker.py`): Processes PDF→CSV pipeline
- **S3 Utils** (`s3_utils.py`): AWS S3 upload/download operations
- **Doctly Client** (`doctly_client.py`): API client with polling
- **Table Parser** (`tableparser.py`): Markdown→CSV conversion
- **Test Runner** (`scripts/test_runner.py`): End-to-end testing

## 📋 Testing Phases

### Phase 1: Environment Setup ✅
**Goal**: Ensure all dependencies and configuration are correct

**Steps**:
1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Configuration**:
   ```bash
   cp env.example .env
   # Edit .env with your actual credentials:
   # - AWS_ACCESS_KEY_ID
   # - AWS_SECRET_ACCESS_KEY  
   # - DOCTLY_API_KEY
   # - AWS_REGION (default: us-east-1)
   ```

3. **Verify Import Fix**:
   ```bash
   python -c "from tableparser import TableParser; print('✅ TableParser import works')"
   ```

**Expected Results**:
- All packages install without errors
- TableParser imports successfully
- Environment variables are set

### Phase 2: Local API Testing ✅
**Goal**: Verify the FastAPI application starts and responds correctly

**Steps**:
1. **Start the API**:
   ```bash
   python main.py
   ```

2. **Test Health Endpoint**:
   ```bash
   curl http://localhost:8000/health
   ```

3. **Test Root Endpoint**:
   ```bash
   curl http://localhost:8000/
   ```

4. **Test Parse Endpoint (without credentials)**:
   ```bash
   curl -X POST http://localhost:8000/parse \
     -H "Content-Type: application/json" \
     -d '{"s3_bucket":"test","s3_key":"test.pdf","webhook_url":"http://example.com"}'
   ```

**Expected Results**:
- API starts on port 8000
- Health check returns `{"status": "healthy", "queue_size": 0, "service": "pdf-parser"}`
- Root returns service info
- Parse endpoint returns 500 error about missing environment variables (expected without real credentials)

### Phase 3: Docker Testing ✅
**Goal**: Ensure the application works in containerized environment

**Steps**:
1. **Build Docker Image**:
   ```bash
   docker build -t pdf-parser .
   ```

2. **Run Container**:
   ```bash
   docker run -p 8000:8000 --env-file .env pdf-parser
   ```

3. **Test Health Check**:
   ```bash
   curl http://localhost:8000/health
   ```

4. **Check Docker Health**:
   ```bash
   docker ps  # Should show healthy status
   ```

**Expected Results**:
- Docker image builds successfully
- Container starts and passes health checks
- API endpoints respond correctly
- Container shows "healthy" status

### Phase 4: Component Unit Testing ✅
**Goal**: Test individual components in isolation

**Steps**:
1. **Test Table Parser**:
   ```bash
   python -c "
   from tableparser import TableParser
   parser = TableParser()
   markdown = '''
   | Name | Age | City |
   |------|-----|------|
   | John | 25  | NYC  |
   | Jane | 30  | LA   |
   '''
   csv = parser.markdown_to_csv(markdown)
   print('✅ TableParser works')
   print(csv)
   "
   ```

2. **Test Job Queue**:
   ```bash
   python -c "
   from queue import JobQueue
   q = JobQueue()
   pos = q.add_job({'test': 'data'})
   job = q.get_next_job()
   print(f'✅ Queue works: position={pos}, job_id={job[\"id\"]}')
   "
   ```

3. **Test S3 Utils** (requires AWS credentials):
   ```bash
   python -c "
   from s3_utils import S3Utils
   s3 = S3Utils()
   print('✅ S3Utils initialized')
   # Note: Actual upload/download tests require valid credentials
   "
   ```

**Expected Results**:
- TableParser converts markdown to CSV correctly
- JobQueue adds and retrieves jobs properly
- S3Utils initializes without errors

### Phase 5: Integration Testing (Requires Credentials) 🔐
**Goal**: Test the complete workflow with real services

**Prerequisites**:
- Valid AWS credentials with S3 access
- Valid Doctly API key
- S3 bucket for testing
- Sample PDF file

**Steps**:
1. **Prepare Test Environment**:
   ```bash
   # Ensure .env has real credentials
   # Create test S3 bucket or use existing one
   # Have a sample PDF ready for testing
   ```

2. **Run End-to-End Test**:
   ```bash
   cd scripts
   python test_runner.py --api-url http://localhost:8000 --s3-bucket your-test-bucket --pdf-path /path/to/test.pdf
   ```

3. **Manual Integration Test**:
   ```bash
   # Start API in one terminal
   python main.py
   
   # In another terminal, trigger a job
   curl -X POST http://localhost:8000/parse \
     -H "Content-Type: application/json" \
     -d '{
       "s3_bucket": "your-test-bucket",
       "s3_key": "test-pdfs/sample.pdf",
       "webhook_url": "https://webhook.site/your-unique-url"
     }'
   ```

**Expected Results**:
- PDF uploads to S3 successfully
- Doctly processes PDF and returns markdown
- TableParser converts markdown to CSV
- CSV uploads to S3 under `processed/` prefix
- Webhook notification sent with success/error status

### Phase 6: Error Handling Testing ✅
**Goal**: Verify the system handles errors gracefully

**Steps**:
1. **Test Missing Environment Variables**:
   ```bash
   # Temporarily remove AWS_ACCESS_KEY_ID from .env
   curl -X POST http://localhost:8000/parse \
     -H "Content-Type: application/json" \
     -d '{"s3_bucket":"test","s3_key":"test.pdf","webhook_url":"http://example.com"}'
   ```

2. **Test Invalid S3 Bucket**:
   ```bash
   curl -X POST http://localhost:8000/parse \
     -H "Content-Type: application/json" \
     -d '{"s3_bucket":"nonexistent-bucket-12345","s3_key":"test.pdf","webhook_url":"http://example.com"}'
   ```

3. **Test Invalid JSON**:
   ```bash
   curl -X POST http://localhost:8000/parse \
     -H "Content-Type: application/json" \
     -d '{"invalid": json}'
   ```

**Expected Results**:
- Appropriate error messages returned
- API doesn't crash
- Errors logged properly
- Webhook receives error notifications

## 🚀 Quick Start Commands

### For Testing Agent:
```bash
# 1. Fix is already applied ✅

# 2. Install and test locally
pip install -r requirements.txt
cp env.example .env  # Edit with your credentials
python main.py &
curl http://localhost:8000/health

# 3. Test with Docker
docker build -t pdf-parser .
docker run -p 8000:8000 --env-file .env pdf-parser &
curl http://localhost:8000/health

# 4. Run integration tests (if you have credentials)
cd scripts
python test_runner.py --api-url http://localhost:8000 --s3-bucket your-bucket --pdf-path test.pdf
```

## 📊 Success Criteria

### ✅ Basic Functionality
- [ ] API starts without errors
- [ ] Health check returns healthy status
- [ ] All endpoints respond correctly
- [ ] Docker container builds and runs

### ✅ Component Integration
- [ ] TableParser converts markdown to CSV
- [ ] Job queue manages jobs correctly
- [ ] Worker processes jobs in background
- [ ] S3 operations work with valid credentials

### ✅ End-to-End Workflow
- [ ] PDF upload to S3 succeeds
- [ ] Doctly API integration works
- [ ] Markdown to CSV conversion works
- [ ] CSV upload to S3 succeeds
- [ ] Webhook notifications sent

### ✅ Error Handling
- [ ] Missing credentials handled gracefully
- [ ] Invalid requests return proper errors
- [ ] Failed jobs send error webhooks
- [ ] System remains stable under errors

## 🐛 Known Issues & Limitations

1. **In-Memory Queue**: Jobs are lost on restart (consider Redis for production)
2. **No Authentication**: API endpoints are public (add API keys for production)
3. **Limited Error Recovery**: Failed jobs aren't retried automatically
4. **Webhook Reliability**: No webhook retry mechanism
5. **File Cleanup**: Temporary files cleaned up but no disk space monitoring

## 📝 Testing Notes

- The test runner includes a webhook server for receiving notifications
- S3 operations require valid AWS credentials and permissions
- Doctly API calls may take time depending on PDF complexity
- Docker health checks ensure container stability
- All temporary files are cleaned up after processing

## 🔄 Next Steps After Testing

1. **If tests pass**: Deploy to Railway or your preferred platform
2. **If tests fail**: Check logs, verify credentials, debug specific components
3. **For production**: Add authentication, persistent queue, monitoring
4. **For scaling**: Consider multiple workers, load balancing, caching 
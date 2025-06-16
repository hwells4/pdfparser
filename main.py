"""
PDF Parser Microservice - Main Application
FastAPI application with /parse endpoint for PDF to CSV conversion via Doctly
"""

import os
import logging
import time
import json
from typing import Dict, Any
from collections import defaultdict
from fastapi import FastAPI, HTTPException, Header, Depends, Request
from pydantic import BaseModel
from dotenv import load_dotenv

from job_queue import JobQueue
from worker import start_background_worker
from doctly_client import DoctlyClient

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="PDF Parser Microservice",
    description="Convert PDFs to CSV via Doctly and S3",
    version="1.0.0"
)

# Initialize job queue
job_queue = JobQueue()

# Initialize Doctly client
doctly_client = DoctlyClient()

# Start background worker
start_background_worker(job_queue)

# Simple rate limiting for failed auth attempts
failed_attempts = defaultdict(list)
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION = 300  # 5 minutes

# Store for tracking Doctly jobs (document_id -> original request data)
doctly_jobs = {}


def is_ip_locked(ip: str) -> bool:
    """Check if IP is temporarily locked due to too many failed attempts"""
    now = time.time()
    # Clean old attempts
    failed_attempts[ip] = [attempt for attempt in failed_attempts[ip] 
                          if now - attempt < LOCKOUT_DURATION]
    
    return len(failed_attempts[ip]) >= MAX_FAILED_ATTEMPTS


def record_failed_attempt(ip: str):
    """Record a failed authentication attempt"""
    failed_attempts[ip].append(time.time())


def verify_api_key(request: Request, x_api_key: str = Header(..., alias="X-API-Key")):
    """
    Verify API key from request header
    
    Args:
        request: FastAPI request object
        x_api_key: API key from X-API-Key header
        
    Raises:
        HTTPException: If API key is invalid or missing
    """
    client_ip = request.client.host if request.client else "unknown"
    
    # Check if IP is temporarily locked
    if is_ip_locked(client_ip):
        logger.warning(f"Blocked request from locked IP: {client_ip}")
        raise HTTPException(
            status_code=429,
            detail="Too many failed attempts. Please try again later."
        )
    
    expected_api_key = os.getenv("API_KEY")
    if not expected_api_key:
        logger.error("API_KEY environment variable not set")
        raise HTTPException(
            status_code=500,
            detail="Server configuration error"
        )
    
    # Handle empty or whitespace-only keys
    if not x_api_key or not x_api_key.strip():
        logger.warning(f"Empty or whitespace API key provided from IP: {client_ip}")
        record_failed_attempt(client_ip)
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    
    if x_api_key != expected_api_key:
        # Log more details for debugging (but keep key secure)
        logger.warning(f"Invalid API key attempt from IP {client_ip}: {x_api_key[:8]}... (length: {len(x_api_key)})")
        record_failed_attempt(client_ip)
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    
    # Log successful authentication (but don't log the actual key)
    logger.debug(f"API key authentication successful from IP: {client_ip}")
    return x_api_key


class ParseRequest(BaseModel):
    s3_bucket: str
    s3_key: str
    webhook_url: str
    document_id: int = None  # Optional for backwards compatibility


class ParseResponse(BaseModel):
    status: str
    position: int = None  # Optional for async endpoints
    document_id: str = None  # For async endpoints


class DoctlyWebhookRequest(BaseModel):
    document_id: str
    status: str
    output_file_url: str = None
    extractor: Dict[str, str] = None


@app.post("/parse", response_model=ParseResponse)
async def parse_pdf(request: ParseRequest, api_key: str = Depends(verify_api_key)) -> ParseResponse:
    """
    Main endpoint to initiate PDF parsing job
    
    Args:
        request: ParseRequest containing S3 bucket, key, and webhook URL
        api_key: Verified API key from X-API-Key header
        
    Returns:
        ParseResponse with job status and queue position
    """
    try:
        # Validate required environment variables
        required_vars = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "DOCTLY_API_KEY"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            error_msg = f"Missing environment variables: {', '.join(missing_vars)}"
            logger.error(f"Parse request failed: {error_msg}")
            raise HTTPException(
                status_code=500, 
                detail=error_msg
            )
        
        # Add job to queue
        position = job_queue.add_job({
            "s3_bucket": request.s3_bucket,
            "s3_key": request.s3_key,
            "webhook_url": request.webhook_url,
            "document_id": request.document_id
        })
        
        logger.info(f"Added job to queue: {request.s3_key}, position: {position}")
        
        return ParseResponse(status="queued", position=position)
        
    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        error_msg = str(e) if str(e) else "Unknown error occurred"
        logger.error(f"Error processing parse request: {error_msg}")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Exception args: {e.args}")
        raise HTTPException(status_code=500, detail=error_msg)


@app.post("/parse-json", response_model=ParseResponse)
async def parse_pdf_json(request: ParseRequest, api_key: str = Depends(verify_api_key)) -> ParseResponse:
    """
    New endpoint for PDF parsing using Doctly Insurance extractor with internal polling
    
    Args:
        request: ParseRequest containing S3 bucket, key, and webhook URL
        api_key: Verified API key from X-API-Key header
        
    Returns:
        ParseResponse with job status and success/error details
    """
    try:
        # Validate required environment variables
        required_vars = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "DOCTLY_API_KEY"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            error_msg = f"Missing environment variables: {', '.join(missing_vars)}"
            logger.error(f"Parse-json request failed: {error_msg}")
            raise HTTPException(
                status_code=500, 
                detail=error_msg
            )
        
        # Import here to avoid circular imports
        from s3_utils import S3Utils
        from doctly_client import DoctlyClient
        import tempfile
        import json
        
        s3_utils = S3Utils()
        doctly_client = DoctlyClient()
        
        logger.info(f"Processing parse-json request: {request.s3_key}")
        
        temp_files = []
        document_id = None
        
        try:
            # Step 1: Download PDF from S3
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_pdf:
                temp_files.append(temp_pdf.name)
                s3_utils.download_file(request.s3_bucket, request.s3_key, temp_pdf.name)
                logger.info(f"Downloaded PDF from S3: {request.s3_key}")
            
            # Step 2: Process with Doctly Insurance extractor (internal polling)
            json_content, document_id = doctly_client.process_pdf_insurance_direct(temp_pdf.name)
            logger.info(f"Doctly Insurance processing completed, document ID: {document_id}")
            
            # Step 3: Convert JSON to CSV
            csv_content = await convert_json_to_csv(json_content)
            logger.info("Converted JSON to CSV")
            
            # Step 4: Upload CSV to S3
            original_filename = os.path.splitext(os.path.basename(request.s3_key))[0]
            csv_key = f"processed/{original_filename}.csv"
            
            with tempfile.NamedTemporaryFile(mode='w', suffix=".csv", delete=False) as temp_csv:
                temp_files.append(temp_csv.name)
                temp_csv.write(csv_content)
                temp_csv.flush()
                
                csv_url = s3_utils.upload_file(temp_csv.name, request.s3_bucket, csv_key)
                logger.info(f"Uploaded CSV to S3: {csv_key}")
            
            # Step 5: Send success webhook with document_id
            webhook_url_with_id = f"{request.webhook_url}?document_id={document_id}"
            await send_success_webhook(webhook_url_with_id, csv_url, os.path.basename(request.s3_key))
            
            logger.info(f"Parse-json request completed successfully for {request.s3_key}")
            
            return ParseResponse(status="completed", document_id=document_id)
            
        except Exception as e:
            logger.error(f"Parse-json request failed: {str(e)}")
            
            # Send error webhook with document_id if available
            webhook_url_with_id = f"{request.webhook_url}?document_id={document_id}" if document_id else request.webhook_url
            await send_error_webhook(webhook_url_with_id, str(e), os.path.basename(request.s3_key))
            
            raise HTTPException(status_code=500, detail=str(e))
            
        finally:
            # Cleanup temporary files
            for file_path in temp_files:
                try:
                    if os.path.exists(file_path):
                        os.unlink(file_path)
                        logger.debug(f"Cleaned up temp file: {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file {file_path}: {str(e)}")
        
    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        error_msg = str(e) if str(e) else "Unknown error occurred"
        logger.error(f"Error processing parse-json request: {error_msg}")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Exception args: {e.args}")
        raise HTTPException(status_code=500, detail=error_msg)


@app.post("/doctly-webhook-handler")
async def doctly_webhook_handler(webhook_data: DoctlyWebhookRequest):
    """
    Handle webhook callbacks from Doctly Insurance extractor
    
    Args:
        webhook_data: Webhook payload from Doctly
    """
    try:
        logger.info(f"Received Doctly webhook for document ID: {webhook_data.document_id}")
        logger.info(f"Webhook data: {webhook_data.dict()}")
        
        # Find original request data
        job_data = doctly_jobs.get(webhook_data.document_id)
        if not job_data:
            logger.error(f"No job data found for document ID: {webhook_data.document_id}")
            raise HTTPException(status_code=404, detail="Job data not found")
        
        # Check if processing was successful
        if webhook_data.status != "COMPLETED":
            error_msg = f"Doctly processing failed with status: {webhook_data.status}"
            logger.error(error_msg)
            await send_error_webhook(job_data["webhook_url"], error_msg, job_data["original_filename"])
            return {"status": "error", "message": error_msg}
        
        if not webhook_data.output_file_url:
            error_msg = "No output file URL provided in webhook"
            logger.error(error_msg)
            await send_error_webhook(job_data["webhook_url"], error_msg, job_data["original_filename"])
            return {"status": "error", "message": error_msg}
        
        # Process the result
        await process_doctly_result(webhook_data.output_file_url, job_data)
        
        # Clean up job data
        del doctly_jobs[webhook_data.document_id]
        
        return {"status": "success"}
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e) if str(e) else "Unknown error occurred"
        logger.error(f"Error in Doctly webhook handler: {error_msg}")
        
        # Try to send error webhook if we have job data
        if webhook_data.document_id in doctly_jobs:
            job_data = doctly_jobs[webhook_data.document_id]
            await send_error_webhook(job_data["webhook_url"], error_msg, job_data["original_filename"])
            del doctly_jobs[webhook_data.document_id]
        
        raise HTTPException(status_code=500, detail=error_msg)


async def process_doctly_result(output_file_url: str, job_data: Dict[str, Any]):
    """
    Process the result from Doctly Insurance extractor
    
    Args:
        output_file_url: URL to download JSON result
        job_data: Original job data
    """
    import requests
    import tempfile
    from s3_utils import S3Utils
    
    s3_utils = S3Utils()
    temp_files = []
    
    try:
        # Step 1: Download JSON result
        logger.info(f"Downloading JSON result from: {output_file_url}")
        response = requests.get(output_file_url, timeout=60)
        response.raise_for_status()
        
        json_content = response.text
        if not json_content.strip():
            raise Exception("Downloaded JSON content is empty")
        
        logger.info(f"Downloaded JSON content ({len(json_content)} characters)")
        
        # Step 2: Convert JSON to CSV
        csv_content = await convert_json_to_csv(json_content)
        logger.info("Converted JSON to CSV")
        
        # Step 3: Upload CSV to S3
        original_filename = os.path.splitext(job_data["original_filename"])[0]
        csv_key = f"processed/{original_filename}.csv"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix=".csv", delete=False) as temp_csv:
            temp_files.append(temp_csv.name)
            temp_csv.write(csv_content)
            temp_csv.flush()
            
            csv_url = s3_utils.upload_file(temp_csv.name, job_data["s3_bucket"], csv_key)
            logger.info(f"Uploaded CSV to S3: {csv_key}")
        
        # Step 4: Send success webhook
        await send_success_webhook(
            job_data["webhook_url"],
            csv_url,
            job_data["original_filename"]
        )
        
    except Exception as e:
        logger.error(f"Error processing Doctly result: {str(e)}")
        await send_error_webhook(job_data["webhook_url"], str(e), job_data["original_filename"])
        raise
    finally:
        # Cleanup temp files
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp file {temp_file}: {str(e)}")


async def convert_json_to_csv(json_content: str) -> str:
    """
    Convert JSON data to CSV format
    
    Args:
        json_content: JSON content from Doctly
        
    Returns:
        CSV content as string
    """
    import pandas as pd
    from io import StringIO
    
    try:
        # Parse JSON
        data = json.loads(json_content)
        
        # Handle different JSON structures
        if isinstance(data, dict):
            # If it's a single object, convert to list
            if 'data' in data and isinstance(data['data'], list):
                # Extract data array if present
                data = data['data']
            elif any(isinstance(v, (list, dict)) for v in data.values()):
                # If it contains nested structures, flatten or handle appropriately
                df = pd.json_normalize(data)
            else:
                # Simple key-value pairs
                df = pd.DataFrame([data])
        elif isinstance(data, list):
            # List of objects
            if data and isinstance(data[0], dict):
                df = pd.json_normalize(data)
            else:
                # Simple list
                df = pd.DataFrame(data, columns=['value'])
        else:
            # Primitive type
            df = pd.DataFrame([{'value': data}])
        
        # Convert to CSV
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False)
        return csv_buffer.getvalue()
        
    except Exception as e:
        logger.error(f"Error converting JSON to CSV: {str(e)}")
        logger.error(f"JSON content: {json_content[:500]}...")  # Log first 500 chars
        raise Exception(f"Failed to convert JSON to CSV: {str(e)}")


async def send_success_webhook(webhook_url: str, csv_url: str, original_filename: str):
    """
    Send success webhook to backend
    
    Args:
        webhook_url: Webhook URL
        csv_url: URL of uploaded CSV file
        original_filename: Original PDF filename
    """
    import requests
    
    payload = {
        "status": "success",
        "csv_url": csv_url,
        "original_filename": original_filename
    }
    
    try:
        response = requests.post(webhook_url, json=payload, timeout=30)
        response.raise_for_status()
        logger.info(f"Success webhook sent to {webhook_url}")
    except Exception as e:
        logger.error(f"Failed to send success webhook to {webhook_url}: {str(e)}")


async def send_error_webhook(webhook_url: str, error_message: str, original_filename: str):
    """
    Send error webhook to backend
    
    Args:
        webhook_url: Webhook URL
        error_message: Error message
        original_filename: Original PDF filename
    """
    import requests
    
    payload = {
        "status": "error",
        "message": f"Processing failed: {error_message}",
        "original_filename": original_filename
    }
    
    try:
        response = requests.post(webhook_url, json=payload, timeout=30)
        response.raise_for_status()
        logger.info(f"Error webhook sent to {webhook_url}")
    except Exception as e:
        logger.error(f"Failed to send error webhook to {webhook_url}: {str(e)}")


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint"""
    return {
        "status": "healthy",
        "queue_size": job_queue.size(),
        "doctly_jobs": len(doctly_jobs),
        "service": "pdf-parser"
    }


@app.get("/")
async def root() -> Dict[str, str]:
    """Root endpoint"""
    return {"message": "PDF Parser Microservice", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port) 
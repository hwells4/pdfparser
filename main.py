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

# Note: doctly_jobs storage removed as we now use async queue processing for all endpoints


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
    Endpoint for PDF parsing using Doctly Insurance extractor (JSON processing)
    
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
            logger.error(f"Parse-json request failed: {error_msg}")
            raise HTTPException(
                status_code=500, 
                detail=error_msg
            )
        
        # Add job to queue with JSON processing flag
        position = job_queue.add_job({
            "s3_bucket": request.s3_bucket,
            "s3_key": request.s3_key,
            "webhook_url": request.webhook_url,
            "document_id": request.document_id,
            "processing_type": "json"  # Flag to indicate JSON processing
        })
        
        logger.info(f"Added JSON processing job to queue: {request.s3_key}, position: {position}")
        
        return ParseResponse(status="queued", position=position)
        
    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        error_msg = str(e) if str(e) else "Unknown error occurred"
        logger.error(f"Error processing parse-json request: {error_msg}")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Exception args: {e.args}")
        raise HTTPException(status_code=500, detail=error_msg)



@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint"""
    return {
        "status": "healthy",
        "queue_size": job_queue.size(),
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
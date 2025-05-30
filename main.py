"""
PDF Parser Microservice - Main Application
FastAPI application with /parse endpoint for PDF to CSV conversion via Doctly
"""

import os
import logging
from typing import Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

from job_queue import JobQueue
from worker import start_background_worker

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

# Start background worker
start_background_worker(job_queue)


class ParseRequest(BaseModel):
    s3_bucket: str
    s3_key: str
    webhook_url: str


class ParseResponse(BaseModel):
    status: str
    position: int


@app.post("/parse", response_model=ParseResponse)
async def parse_pdf(request: ParseRequest) -> ParseResponse:
    """
    Main endpoint to initiate PDF parsing job
    
    Args:
        request: ParseRequest containing S3 bucket, key, and webhook URL
        
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
            "webhook_url": request.webhook_url
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
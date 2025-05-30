"""
Background Worker
Processes jobs from the queue and handles the PDF to CSV conversion workflow
"""

import threading
import time
import logging
import tempfile
import os
from typing import Dict, Any

from s3_utils import S3Utils
from doctly_client import DoctlyClient
from tableparser import TableParser

logger = logging.getLogger(__name__)


class Worker:
    """Background worker for processing PDF conversion jobs"""
    
    def __init__(self, job_queue):
        self.job_queue = job_queue
        self.s3_utils = S3Utils()
        self.doctly_client = DoctlyClient()
        self.table_parser = TableParser()
        self.running = False
        self.worker_thread = None
        
    def start(self):
        """Start the background worker thread"""
        if not self.running:
            self.running = True
            self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
            self.worker_thread.start()
            logger.info("Background worker started")
    
    def stop(self):
        """Stop the background worker thread"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join()
            logger.info("Background worker stopped")
    
    def _worker_loop(self):
        """Main worker loop that processes jobs from the queue"""
        while self.running:
            try:
                job = self.job_queue.get_next_job()
                if job:
                    self._process_job(job)
                else:
                    # No jobs available, sleep briefly
                    time.sleep(1)
            except Exception as e:
                logger.error(f"Error in worker loop: {str(e)}")
                time.sleep(5)  # Wait before retrying
    
    def _process_job(self, job: Dict[str, Any]):
        """
        Process a single job through the complete workflow
        
        Args:
            job: Job dictionary containing processing information
        """
        job_data = job["data"]
        s3_bucket = job_data["s3_bucket"]
        s3_key = job_data["s3_key"]
        webhook_url = job_data["webhook_url"]
        
        logger.info(f"Processing job {job['id']}: {s3_key}")
        
        temp_files = []
        document_id = None
        
        try:
            # Step 1: Download PDF from S3
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_pdf:
                temp_files.append(temp_pdf.name)
                self.s3_utils.download_file(s3_bucket, s3_key, temp_pdf.name)
                logger.info(f"Downloaded PDF from S3: {s3_key}")
            
            # Step 2: Send to Doctly for conversion
            markdown_content, document_id = self.doctly_client.process_pdf_direct(temp_pdf.name)
            logger.info(f"Doctly processing completed, document ID: {document_id}")
            
            # Step 3: Parse Markdown to CSV
            csv_content = self.table_parser.markdown_to_csv(markdown_content)
            logger.info("Converted Markdown to CSV")
            
            # Step 4: Upload CSV to S3
            original_filename = os.path.splitext(os.path.basename(s3_key))[0]
            csv_key = f"processed/{original_filename}.csv"
            
            with tempfile.NamedTemporaryFile(mode='w', suffix=".csv", delete=False) as temp_csv:
                temp_files.append(temp_csv.name)
                temp_csv.write(csv_content)
                temp_csv.flush()
                
                csv_url = self.s3_utils.upload_file(temp_csv.name, s3_bucket, csv_key)
                logger.info(f"Uploaded CSV to S3: {csv_key}")
            
            # Step 5: Send success webhook with document_id appended to URL
            webhook_url_with_id = f"{webhook_url}?document_id={document_id}"
            self._send_webhook(webhook_url_with_id, {
                "status": "success",
                "csv_url": csv_url,
                "original_filename": os.path.basename(s3_key),
                "document_id": document_id
            })
            
            logger.info(f"Job {job['id']} completed successfully")
            
        except Exception as e:
            logger.error(f"Job {job['id']} failed: {str(e)}")
            
            # Send error webhook with document_id if available
            webhook_url_with_id = f"{webhook_url}?document_id={document_id}" if document_id else webhook_url
            self._send_webhook(webhook_url_with_id, {
                "status": "error",
                "message": str(e),
                "original_filename": os.path.basename(s3_key),
                "document_id": document_id
            })
            
        finally:
            # Cleanup temporary files
            self._cleanup_temp_files(temp_files)
    
    def _send_webhook(self, webhook_url: str, payload: Dict[str, Any]):
        """
        Send webhook notification
        
        Args:
            webhook_url: URL to send webhook to
            payload: Webhook payload data
        """
        try:
            import requests
            response = requests.post(webhook_url, json=payload, timeout=30)
            response.raise_for_status()
            logger.info(f"Webhook sent successfully to {webhook_url}")
        except Exception as e:
            logger.error(f"Failed to send webhook to {webhook_url}: {str(e)}")
    
    def _cleanup_temp_files(self, temp_files: list):
        """
        Clean up temporary files
        
        Args:
            temp_files: List of temporary file paths to delete
        """
        for file_path in temp_files:
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
                    logger.debug(f"Cleaned up temp file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp file {file_path}: {str(e)}")


# Global worker instance
_worker_instance = None


def start_background_worker(job_queue):
    """
    Start the background worker with the given job queue
    
    Args:
        job_queue: JobQueue instance to process jobs from
    """
    global _worker_instance
    if _worker_instance is None:
        _worker_instance = Worker(job_queue)
        _worker_instance.start()
    return _worker_instance


def stop_background_worker():
    """Stop the background worker"""
    global _worker_instance
    if _worker_instance:
        _worker_instance.stop()
        _worker_instance = None 
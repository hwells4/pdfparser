"""
Doctly API Client
Handles interactions with the Doctly API for PDF to Markdown conversion
"""

import os
import time
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)


class DoctlyClient:
    """Client for interacting with the Doctly API"""
    
    def __init__(self):
        """Initialize Doctly client with API key from environment"""
        self.api_key = os.getenv('DOCTLY_API_KEY')
        self.base_url = "https://api.doctly.ai/api/v1"  # Fixed: Updated to correct Doctly API URL
        self._api_key_validated = False
        
        logger.info("Doctly client initialized (API key will be validated on first use)")
    
    def _validate_api_key(self):
        """Validate API key on first use"""
        if not self._api_key_validated:
            if not self.api_key:
                raise Exception("DOCTLY_API_KEY environment variable is required")
            
            self.headers = {
                "Authorization": f"Bearer {self.api_key}"
            }
            self._api_key_validated = True
            logger.info("Doctly API key validated")
    
    def upload_pdf(self, pdf_path: str, accuracy: str = "ultra") -> str:
        """
        Upload a PDF file to Doctly for processing
        
        Args:
            pdf_path: Local path to the PDF file
            accuracy: Processing accuracy level ("ultra", "high", "medium")
            
        Returns:
            Job ID for tracking the conversion process
            
        Raises:
            Exception: If upload fails
        """
        self._validate_api_key()  # Validate API key before use
        
        try:
            # Verify file exists
            if not os.path.exists(pdf_path):
                raise Exception(f"PDF file not found: {pdf_path}")
            
            file_size = os.path.getsize(pdf_path)
            logger.info(f"Uploading PDF to Doctly: {pdf_path} ({file_size} bytes)")
            
            # Prepare multipart form data according to Doctly API docs
            with open(pdf_path, 'rb') as pdf_file:
                files = {
                    'files': (os.path.basename(pdf_path), pdf_file, 'application/pdf')
                }
                data = {}
                if accuracy:
                    data['accuracy'] = accuracy
                
                response = requests.post(
                    f"{self.base_url}/documents/",  # Fixed: Updated endpoint path
                    headers=self.headers,
                    files=files,
                    data=data,
                    timeout=300  # 5 minute timeout for upload
                )
                
                response.raise_for_status()
                result = response.json()
                
                # The API might return different response structure
                # We'll need to adapt based on actual response
                job_id = result.get('id') or result.get('job_id') or result.get('document_id')
                if not job_id:
                    logger.error(f"Unexpected response from Doctly: {result}")
                    raise Exception("No job/document ID returned from Doctly API")
                
                logger.info(f"PDF uploaded successfully, job ID: {job_id}")
                return job_id
                
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP error uploading to Doctly: {str(e)}")
            raise Exception(f"Doctly upload failed: {str(e)}")
        except Exception as e:
            logger.error(f"Error uploading PDF to Doctly: {str(e)}")
            raise
    
    def get_job_status(self, job_id: str) -> dict:
        """
        Get the status of a Doctly conversion job
        
        Args:
            job_id: Job ID returned from upload_pdf
            
        Returns:
            Dictionary containing job status information
            
        Raises:
            Exception: If status check fails
        """
        self._validate_api_key()  # Validate API key before use
        
        try:
            response = requests.get(
                f"{self.base_url}/documents/{job_id}",  # Fixed: Updated endpoint path
                headers=self.headers,
                timeout=30
            )
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP error checking Doctly job status: {str(e)}")
            raise Exception(f"Doctly status check failed: {str(e)}")
        except Exception as e:
            logger.error(f"Error checking Doctly job status: {str(e)}")
            raise
    
    def download_result(self, job_id: str) -> str:
        """
        Download the converted Markdown content from Doctly
        
        Args:
            job_id: Job ID of the completed conversion
            
        Returns:
            Markdown content as string
            
        Raises:
            Exception: If download fails
        """
        self._validate_api_key()  # Validate API key before use
        
        try:
            response = requests.get(
                f"{self.base_url}/documents/{job_id}/download",  # Fixed: Updated endpoint path
                headers=self.headers,
                timeout=60
            )
            
            response.raise_for_status()
            
            # Check if response is JSON (error) or text (markdown content)
            content_type = response.headers.get('content-type', '')
            if 'application/json' in content_type:
                error_data = response.json()
                raise Exception(f"Doctly download error: {error_data.get('message', 'Unknown error')}")
            
            markdown_content = response.text
            if not markdown_content.strip():
                raise Exception("Downloaded Markdown content is empty")
            
            logger.info(f"Downloaded Markdown content ({len(markdown_content)} characters)")
            return markdown_content
            
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP error downloading from Doctly: {str(e)}")
            raise Exception(f"Doctly download failed: {str(e)}")
        except Exception as e:
            logger.error(f"Error downloading Doctly result: {str(e)}")
            raise
    
    def poll_until_complete(self, job_id: str, max_wait_time: int = 1800, poll_interval: int = 10) -> str:
        """
        Poll Doctly job status until completion and return the result
        
        Args:
            job_id: Job ID to poll
            max_wait_time: Maximum time to wait in seconds (default: 30 minutes)
            poll_interval: Time between polls in seconds (default: 10 seconds)
            
        Returns:
            Markdown content as string
            
        Raises:
            Exception: If job fails or times out
        """
        start_time = time.time()
        logger.info(f"Starting to poll Doctly job {job_id}")
        
        while time.time() - start_time < max_wait_time:
            try:
                status_data = self.get_job_status(job_id)
                status = status_data.get('status', '').upper()
                
                logger.debug(f"Job {job_id} status: {status}")
                
                if status == 'COMPLETED':
                    logger.info(f"Job {job_id} completed successfully")
                    return self.download_result(job_id)
                elif status in ['FAILED', 'ERROR']:
                    error_message = status_data.get('error_message', 'Unknown error')
                    raise Exception(f"Doctly job failed: {error_message}")
                elif status in ['QUEUED', 'PROCESSING', 'IN_PROGRESS']:
                    # Job is still processing, continue polling
                    time.sleep(poll_interval)
                else:
                    logger.warning(f"Unknown job status: {status}")
                    time.sleep(poll_interval)
                    
            except Exception as e:
                if "job failed" in str(e).lower():
                    # Job actually failed, don't retry
                    raise
                else:
                    # Network or other temporary error, log and continue
                    logger.warning(f"Error polling job status: {str(e)}")
                    time.sleep(poll_interval)
        
        # Timeout reached
        elapsed_time = time.time() - start_time
        raise Exception(f"Doctly job {job_id} timed out after {elapsed_time:.1f} seconds")
    
    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a Doctly conversion job
        
        Args:
            job_id: Job ID to cancel
            
        Returns:
            True if successful, False otherwise
        """
        self._validate_api_key()  # Validate API key before use
        
        try:
            response = requests.delete(
                f"{self.base_url}/jobs/{job_id}",
                headers=self.headers,
                timeout=30
            )
            
            response.raise_for_status()
            logger.info(f"Cancelled Doctly job {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel Doctly job {job_id}: {str(e)}")
            return False

    def process_pdf_direct(self, pdf_path: str, accuracy: str = "ultra") -> str:
        """
        Process a PDF file and return the markdown content directly
        This method handles the case where Doctly returns the result immediately
        
        Args:
            pdf_path: Local path to the PDF file
            accuracy: Processing accuracy level ("ultra", "high", "medium")
            
        Returns:
            Markdown content as string
            
        Raises:
            Exception: If processing fails
        """
        self._validate_api_key()
        
        try:
            # Verify file exists
            if not os.path.exists(pdf_path):
                raise Exception(f"PDF file not found: {pdf_path}")
            
            file_size = os.path.getsize(pdf_path)
            logger.info(f"Processing PDF with Doctly: {pdf_path} ({file_size} bytes)")
            
            # Prepare multipart form data according to Doctly API docs
            with open(pdf_path, 'rb') as pdf_file:
                files = {
                    'files': (os.path.basename(pdf_path), pdf_file, 'application/pdf')
                }
                data = {}
                if accuracy:
                    data['accuracy'] = accuracy
                
                response = requests.post(
                    f"{self.base_url}/documents/",
                    headers=self.headers,
                    files=files,
                    data=data,
                    timeout=300  # 5 minute timeout for processing
                )
                
                response.raise_for_status()
                
                # Check if response is JSON (with job ID) or direct markdown
                content_type = response.headers.get('content-type', '')
                if 'application/json' in content_type:
                    # Response contains job information, need to poll
                    result = response.json()
                    job_id = result.get('id') or result.get('job_id') or result.get('document_id')
                    if job_id:
                        logger.info(f"Got job ID {job_id}, polling for completion...")
                        return self.poll_until_complete(job_id)
                    else:
                        logger.error(f"Unexpected JSON response from Doctly: {result}")
                        raise Exception("No job ID returned from Doctly API")
                else:
                    # Direct markdown response
                    markdown_content = response.text
                    if not markdown_content.strip():
                        raise Exception("Received empty markdown content from Doctly")
                    
                    logger.info(f"Received direct markdown content ({len(markdown_content)} characters)")
                    return markdown_content
                
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP error processing PDF with Doctly: {str(e)}")
            raise Exception(f"Doctly processing failed: {str(e)}")
        except Exception as e:
            logger.error(f"Error processing PDF with Doctly: {str(e)}")
            raise 
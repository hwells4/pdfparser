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
            accuracy: Processing accuracy level ("ultra", "lite")
            
        Returns:
            Document ID for tracking the conversion process
            
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
                    f"{self.base_url}/documents/",
                    headers=self.headers,
                    files=files,
                    data=data,
                    timeout=300  # 5 minute timeout for upload
                )
                
                response.raise_for_status()
                result = response.json()
                
                # According to docs, response is an array of document objects
                if isinstance(result, list) and len(result) > 0:
                    document = result[0]  # Get first document
                    document_id = document.get('id')
                    if not document_id:
                        logger.error(f"No ID in document object: {document}")
                        raise Exception("No document ID returned from Doctly API")
                    
                    logger.info(f"PDF uploaded successfully, document ID: {document_id}")
                    logger.info(f"Document status: {document.get('status', 'UNKNOWN')}")
                    return document_id
                else:
                    logger.error(f"Unexpected response format from Doctly: {result}")
                    raise Exception("Invalid response format from Doctly API")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP error uploading to Doctly: {str(e)}")
            raise Exception(f"Doctly upload failed: {str(e)}")
        except Exception as e:
            logger.error(f"Error uploading PDF to Doctly: {str(e)}")
            raise
    
    def get_document_status(self, document_id: str) -> dict:
        """
        Get the status of a Doctly document
        
        Args:
            document_id: Document ID returned from upload_pdf
            
        Returns:
            Dictionary containing document status information
            
        Raises:
            Exception: If status check fails
        """
        self._validate_api_key()  # Validate API key before use
        
        try:
            response = requests.get(
                f"{self.base_url}/documents/{document_id}",
                headers=self.headers,
                timeout=30
            )
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP error checking Doctly document status: {str(e)}")
            raise Exception(f"Doctly status check failed: {str(e)}")
        except Exception as e:
            logger.error(f"Error checking Doctly document status: {str(e)}")
            raise

    # Keep the old method name for backward compatibility
    def get_job_status(self, job_id: str) -> dict:
        """Backward compatibility wrapper for get_document_status"""
        return self.get_document_status(job_id)
    
    def download_result(self, document_id: str) -> str:
        """
        Download the converted Markdown content from Doctly
        
        Args:
            document_id: Document ID of the completed conversion
            
        Returns:
            Markdown content as string
            
        Raises:
            Exception: If download fails
        """
        self._validate_api_key()  # Validate API key before use
        
        try:
            # First get the document status to get the download URL
            document_info = self.get_document_status(document_id)
            
            output_file_url = document_info.get('output_file_url')
            if not output_file_url:
                status = document_info.get('status', 'UNKNOWN')
                if status != 'COMPLETED':
                    raise Exception(f"Document not ready for download. Status: {status}")
                else:
                    raise Exception("No output_file_url available in completed document")
            
            # Download from the provided URL
            response = requests.get(
                output_file_url,
                headers=self.headers,
                timeout=60
            )
            
            response.raise_for_status()
            
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
    
    def poll_until_complete(self, document_id: str, max_wait_time: int = 1800, poll_interval: int = 10) -> str:
        """
        Poll Doctly document status until completion and return the result
        
        Args:
            document_id: Document ID to poll
            max_wait_time: Maximum time to wait in seconds (default: 30 minutes)
            poll_interval: Time between polls in seconds (default: 10 seconds)
            
        Returns:
            Markdown content as string
            
        Raises:
            Exception: If document processing fails or times out
        """
        start_time = time.time()
        logger.info(f"Starting to poll Doctly document {document_id}")
        
        while time.time() - start_time < max_wait_time:
            try:
                status_data = self.get_document_status(document_id)
                status = status_data.get('status', '').upper()
                
                logger.debug(f"Document {document_id} status: {status}")
                
                if status == 'COMPLETED':
                    logger.info(f"Document {document_id} completed successfully")
                    return self.download_result(document_id)
                elif status in ['FAILED', 'EXPIRED']:
                    error_message = f"Document processing {status.lower()}"
                    logger.error(f"Document {document_id} {error_message}")
                    raise Exception(f"Doctly document {error_message}")
                elif status in ['PENDING', 'PROCESSING']:
                    # Document is still processing, continue polling
                    logger.debug(f"Document {document_id} still {status.lower()}, waiting...")
                    time.sleep(poll_interval)
                else:
                    logger.warning(f"Unknown document status: {status}")
                    time.sleep(poll_interval)
                    
            except Exception as e:
                if any(word in str(e).lower() for word in ["failed", "expired"]):
                    # Document actually failed, don't retry
                    raise
                else:
                    # Network or other temporary error, log and continue
                    logger.warning(f"Error polling document status: {str(e)}")
                    time.sleep(poll_interval)
        
        # Timeout reached
        elapsed_time = time.time() - start_time
        raise Exception(f"Doctly document {document_id} timed out after {elapsed_time:.1f} seconds")
    
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
        This method handles the complete workflow: upload, poll, and download
        
        Args:
            pdf_path: Local path to the PDF file
            accuracy: Processing accuracy level ("ultra", "lite")
            
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
                result = response.json()
                
                # According to docs, response is always an array of document objects
                if isinstance(result, list) and len(result) > 0:
                    document = result[0]  # Get first document
                    document_id = document.get('id')
                    if not document_id:
                        logger.error(f"No ID in document object: {document}")
                        raise Exception("No document ID returned from Doctly API")
                    
                    status = document.get('status', 'UNKNOWN')
                    logger.info(f"Document uploaded with ID {document_id}, status: {status}")
                    
                    # Poll until completion and return result
                    return self.poll_until_complete(document_id)
                else:
                    logger.error(f"Unexpected response format from Doctly: {result}")
                    raise Exception("Invalid response format from Doctly API")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP error processing PDF with Doctly: {str(e)}")
            raise Exception(f"Doctly processing failed: {str(e)}")
        except Exception as e:
            logger.error(f"Error processing PDF with Doctly: {str(e)}")
            raise 
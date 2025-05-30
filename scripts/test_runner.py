#!/usr/bin/env python3
"""
Test Runner for PDF Parser Microservice
Handles end-to-end testing including S3 upload, API calls, and webhook monitoring
"""

import os
import sys
import time
import json
import logging
import argparse
import tempfile
from typing import Optional
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

import requests
import boto3
from botocore.exceptions import ClientError

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class WebhookHandler(BaseHTTPRequestHandler):
    """HTTP handler for receiving webhook notifications"""
    
    received_webhooks = []
    
    def do_POST(self):
        """Handle POST requests (webhooks)"""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            webhook_data = json.loads(post_data.decode('utf-8'))
            self.received_webhooks.append({
                'timestamp': time.time(),
                'data': webhook_data
            })
            
            logger.info(f"Received webhook: {json.dumps(webhook_data, indent=2)}")
            
            # Send response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "received"}')
            
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            self.send_response(400)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Suppress default HTTP server logging"""
        pass


class PDFParserTester:
    """Main test runner class"""
    
    def __init__(self, api_url: str, s3_bucket: str, webhook_port: int = 8080):
        self.api_url = api_url.rstrip('/')
        self.s3_bucket = s3_bucket
        self.webhook_port = webhook_port
        self.webhook_server = None
        self.webhook_thread = None
        
        # Initialize S3 client
        self.s3_client = boto3.client('s3')
        
        # Test webhook URL
        self.webhook_url = f"http://localhost:{webhook_port}/webhook"
    
    def start_webhook_server(self):
        """Start the webhook listener server"""
        try:
            self.webhook_server = HTTPServer(('localhost', self.webhook_port), WebhookHandler)
            self.webhook_thread = Thread(target=self.webhook_server.serve_forever, daemon=True)
            self.webhook_thread.start()
            logger.info(f"Webhook server started on port {self.webhook_port}")
        except Exception as e:
            logger.error(f"Failed to start webhook server: {str(e)}")
            raise
    
    def stop_webhook_server(self):
        """Stop the webhook listener server"""
        if self.webhook_server:
            self.webhook_server.shutdown()
            self.webhook_server.server_close()
            logger.info("Webhook server stopped")
    
    def upload_test_pdf(self, pdf_path: str) -> str:
        """
        Upload a test PDF to S3
        
        Args:
            pdf_path: Local path to PDF file
            
        Returns:
            S3 key of uploaded file
        """
        try:
            if not os.path.exists(pdf_path):
                raise FileNotFoundError(f"Test PDF not found: {pdf_path}")
            
            # Generate unique S3 key
            filename = os.path.basename(pdf_path)
            s3_key = f"test-uploads/{int(time.time())}-{filename}"
            
            logger.info(f"Uploading {pdf_path} to s3://{self.s3_bucket}/{s3_key}")
            
            self.s3_client.upload_file(pdf_path, self.s3_bucket, s3_key)
            logger.info(f"Upload successful: {s3_key}")
            
            return s3_key
            
        except Exception as e:
            logger.error(f"Failed to upload PDF to S3: {str(e)}")
            raise
    
    def trigger_parse_job(self, s3_key: str) -> dict:
        """
        Trigger a parse job via the API
        
        Args:
            s3_key: S3 key of the PDF to process
            
        Returns:
            API response data
        """
        try:
            payload = {
                "s3_bucket": self.s3_bucket,
                "s3_key": s3_key,
                "webhook_url": self.webhook_url
            }
            
            logger.info(f"Triggering parse job: {json.dumps(payload, indent=2)}")
            
            response = requests.post(
                f"{self.api_url}/parse",
                json=payload,
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"Parse job triggered: {json.dumps(result, indent=2)}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to trigger parse job: {str(e)}")
            raise
    
    def wait_for_webhook(self, timeout: int = 600) -> Optional[dict]:
        """
        Wait for webhook notification
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            Webhook data or None if timeout
        """
        start_time = time.time()
        logger.info(f"Waiting for webhook (timeout: {timeout}s)")
        
        while time.time() - start_time < timeout:
            if WebhookHandler.received_webhooks:
                webhook = WebhookHandler.received_webhooks[-1]
                logger.info("Webhook received!")
                return webhook['data']
            
            time.sleep(2)
        
        logger.warning("Webhook timeout reached")
        return None
    
    def check_api_health(self) -> bool:
        """
        Check if the API is healthy
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            response = requests.get(f"{self.api_url}/health", timeout=10)
            response.raise_for_status()
            
            health_data = response.json()
            logger.info(f"API health check: {json.dumps(health_data, indent=2)}")
            
            return health_data.get('status') == 'healthy'
            
        except Exception as e:
            logger.error(f"API health check failed: {str(e)}")
            return False
    
    def cleanup_s3_file(self, s3_key: str):
        """Clean up uploaded test file from S3"""
        try:
            self.s3_client.delete_object(Bucket=self.s3_bucket, Key=s3_key)
            logger.info(f"Cleaned up S3 file: {s3_key}")
        except Exception as e:
            logger.warning(f"Failed to cleanup S3 file {s3_key}: {str(e)}")
    
    def run_test(self, pdf_path: str, cleanup: bool = True) -> bool:
        """
        Run complete end-to-end test
        
        Args:
            pdf_path: Path to test PDF file
            cleanup: Whether to cleanup uploaded files
            
        Returns:
            True if test passed, False otherwise
        """
        s3_key = None
        
        try:
            # Step 1: Check API health
            logger.info("=== Step 1: API Health Check ===")
            if not self.check_api_health():
                logger.error("API health check failed")
                return False
            
            # Step 2: Start webhook server
            logger.info("=== Step 2: Start Webhook Server ===")
            self.start_webhook_server()
            time.sleep(1)  # Give server time to start
            
            # Step 3: Upload PDF to S3
            logger.info("=== Step 3: Upload PDF to S3 ===")
            s3_key = self.upload_test_pdf(pdf_path)
            
            # Step 4: Trigger parse job
            logger.info("=== Step 4: Trigger Parse Job ===")
            job_response = self.trigger_parse_job(s3_key)
            
            if job_response.get('status') != 'queued':
                logger.error(f"Unexpected job status: {job_response.get('status')}")
                return False
            
            # Step 5: Wait for webhook
            logger.info("=== Step 5: Wait for Webhook ===")
            webhook_data = self.wait_for_webhook()
            
            if not webhook_data:
                logger.error("No webhook received")
                return False
            
            # Step 6: Validate results
            logger.info("=== Step 6: Validate Results ===")
            if webhook_data.get('status') == 'success':
                csv_url = webhook_data.get('csv_url')
                if csv_url:
                    logger.info(f"✅ Test PASSED! CSV available at: {csv_url}")
                    return True
                else:
                    logger.error("Success webhook missing csv_url")
                    return False
            else:
                logger.error(f"Job failed: {webhook_data.get('message', 'Unknown error')}")
                return False
                
        except Exception as e:
            logger.error(f"Test failed with exception: {str(e)}")
            return False
            
        finally:
            # Cleanup
            if cleanup and s3_key:
                self.cleanup_s3_file(s3_key)
            
            self.stop_webhook_server()


def create_sample_pdf(output_path: str):
    """Create a simple sample PDF for testing"""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        
        c = canvas.Canvas(output_path, pagesize=letter)
        c.drawString(100, 750, "Sample PDF for Testing")
        c.drawString(100, 700, "This is a test document with some sample content.")
        
        # Add a simple table
        c.drawString(100, 650, "Sample Table:")
        c.drawString(100, 620, "Name | Age | City")
        c.drawString(100, 600, "John | 25 | New York")
        c.drawString(100, 580, "Jane | 30 | Los Angeles")
        
        c.save()
        logger.info(f"Created sample PDF: {output_path}")
        
    except ImportError:
        logger.warning("reportlab not installed, cannot create sample PDF")
        logger.info("Install with: pip install reportlab")
        raise


def main():
    parser = argparse.ArgumentParser(description='Test PDF Parser Microservice')
    parser.add_argument('--api-url', default='http://localhost:8000', 
                       help='API base URL (default: http://localhost:8000)')
    parser.add_argument('--s3-bucket', required=True, 
                       help='S3 bucket name for testing')
    parser.add_argument('--pdf-path', 
                       help='Path to test PDF file')
    parser.add_argument('--create-sample', action='store_true',
                       help='Create a sample PDF for testing')
    parser.add_argument('--webhook-port', type=int, default=8080,
                       help='Port for webhook server (default: 8080)')
    parser.add_argument('--no-cleanup', action='store_true',
                       help='Skip cleanup of uploaded files')
    
    args = parser.parse_args()
    
    # Handle sample PDF creation
    if args.create_sample:
        sample_path = "sample_test.pdf"
        create_sample_pdf(sample_path)
        if not args.pdf_path:
            args.pdf_path = sample_path
    
    if not args.pdf_path:
        logger.error("No PDF file specified. Use --pdf-path or --create-sample")
        return 1
    
    # Run the test
    tester = PDFParserTester(args.api_url, args.s3_bucket, args.webhook_port)
    
    success = tester.run_test(args.pdf_path, cleanup=not args.no_cleanup)
    
    if success:
        logger.info("🎉 All tests PASSED!")
        return 0
    else:
        logger.error("❌ Tests FAILED!")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 
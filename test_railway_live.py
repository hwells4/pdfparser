#!/usr/bin/env python3
"""
Test script for live Railway PDF Parser instance
Tests with real PDFs from the converseinsurance S3 bucket
"""

import requests
import json
import time
import logging
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RailwayTester:
    def __init__(self, railway_url: str, s3_bucket: str = "converseinsurance"):
        """
        Initialize the Railway tester
        
        Args:
            railway_url: Your Railway app URL (e.g., https://your-app.railway.app)
            s3_bucket: S3 bucket name (default: converseinsurance)
        """
        self.railway_url = railway_url.rstrip('/')
        self.s3_bucket = s3_bucket
        
    def test_health(self) -> bool:
        """Test if the Railway app is healthy"""
        try:
            logger.info("🏥 Testing Railway app health...")
            response = requests.get(f"{self.railway_url}/health", timeout=10)
            response.raise_for_status()
            
            health_data = response.json()
            logger.info(f"✅ Health check passed: {json.dumps(health_data, indent=2)}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Health check failed: {str(e)}")
            return False
    
    def trigger_parse_job(self, s3_key: str, webhook_url: str) -> Optional[dict]:
        """
        Trigger a parse job on Railway
        
        Args:
            s3_key: S3 key of the PDF to process (e.g., "documents/sample.pdf")
            webhook_url: URL to receive webhook notifications
            
        Returns:
            API response or None if failed
        """
        try:
            payload = {
                "s3_bucket": self.s3_bucket,
                "s3_key": s3_key,
                "webhook_url": webhook_url
            }
            
            logger.info(f"🚀 Triggering parse job...")
            logger.info(f"   S3 Bucket: {self.s3_bucket}")
            logger.info(f"   S3 Key: {s3_key}")
            logger.info(f"   Webhook URL: {webhook_url}")
            
            response = requests.post(
                f"{self.railway_url}/parse",
                json=payload,
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"✅ Parse job triggered successfully!")
            logger.info(f"   Status: {result.get('status')}")
            logger.info(f"   Queue Position: {result.get('position')}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Failed to trigger parse job: {str(e)}")
            if hasattr(e, 'response') and e.response:
                try:
                    error_detail = e.response.json()
                    logger.error(f"   Error details: {json.dumps(error_detail, indent=2)}")
                except:
                    logger.error(f"   Response text: {e.response.text}")
            return None

def main():
    """Main test function"""
    print("🧪 Railway PDF Parser Live Test")
    print("=" * 50)
    
    # Configuration - UPDATE THESE VALUES
    RAILWAY_URL = input("Enter your Railway app URL (e.g., https://your-app.railway.app): ").strip()
    S3_KEY = input("Enter the S3 key of your PDF (e.g., documents/sample.pdf): ").strip()
    WEBHOOK_URL = input("Enter webhook URL (or press Enter for webhook.site): ").strip()
    
    # Generate a webhook.site URL if none provided
    if not WEBHOOK_URL:
        import uuid
        webhook_id = str(uuid.uuid4())[:8]
        WEBHOOK_URL = f"https://webhook.site/{webhook_id}"
        print(f"📡 Generated webhook URL: {WEBHOOK_URL}")
        print("   Visit this URL in your browser to see webhook notifications!")
    
    # Initialize tester
    tester = RailwayTester(RAILWAY_URL)
    
    # Step 1: Health check
    print("\n🏥 Step 1: Health Check")
    if not tester.test_health():
        print("❌ Health check failed. Please check your Railway deployment.")
        return
    
    # Step 2: Trigger parse job
    print("\n🚀 Step 2: Trigger Parse Job")
    result = tester.trigger_parse_job(S3_KEY, WEBHOOK_URL)
    
    if not result:
        print("❌ Failed to trigger parse job.")
        return
    
    # Step 3: Instructions for monitoring
    print("\n📋 Step 3: Monitor Progress")
    print("Your job has been queued! Here's what happens next:")
    print(f"   1. 📥 Railway downloads PDF from s3://converseinsurance/{S3_KEY}")
    print(f"   2. 🔄 Sends PDF to Doctly for processing")
    print(f"   3. ⏳ Waits for Doctly to convert PDF to Markdown")
    print(f"   4. 📊 Converts Markdown tables to CSV")
    print(f"   5. 📤 Uploads CSV to s3://converseinsurance/processed/{S3_KEY.replace('.pdf', '.csv')}")
    print(f"   6. 📡 Sends webhook notification to: {WEBHOOK_URL}")
    
    print(f"\n🔍 Monitor your webhook at: {WEBHOOK_URL}")
    print("   The webhook will contain:")
    print("   - status: 'success' or 'error'")
    print("   - csv_url: Direct S3 URL to download the CSV (if successful)")
    print("   - original_filename: Name of the original PDF")
    
    print(f"\n📁 Expected CSV location:")
    print(f"   s3://converseinsurance/processed/{S3_KEY.replace('.pdf', '.csv')}")
    
    print("\n✅ Test completed! Check your webhook URL for results.")

if __name__ == "__main__":
    main() 
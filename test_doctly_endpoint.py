#!/usr/bin/env python3
"""
Test script to verify Doctly API endpoint accessibility
"""

import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_doctly_endpoint():
    """Test if the Doctly API endpoint is accessible"""
    
    api_key = os.getenv('DOCTLY_API_KEY')
    if not api_key:
        print("❌ DOCTLY_API_KEY not found in environment")
        return False
    
    # Test the correct endpoint
    base_url = "https://api.doctly.ai/api/v1"
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    try:
        print(f"🔍 Testing Doctly API endpoint: {base_url}")
        
        # Try a simple GET request to see if the endpoint exists
        # This might return 404 or 405, but should not give SSL errors
        response = requests.get(f"{base_url}/documents/", headers=headers, timeout=10)
        
        print(f"✅ Successfully connected to Doctly API")
        print(f"   Status Code: {response.status_code}")
        print(f"   Response Headers: {dict(response.headers)}")
        
        if response.status_code == 404:
            print("   (404 is expected for GET on documents endpoint)")
        elif response.status_code == 405:
            print("   (405 Method Not Allowed is expected for GET on documents endpoint)")
        
        return True
        
    except requests.exceptions.SSLError as e:
        print(f"❌ SSL Error connecting to Doctly API: {e}")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Connection Error: {e}")
        return False
    except requests.exceptions.Timeout as e:
        print(f"❌ Timeout Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_old_endpoint():
    """Test the old (incorrect) endpoint to confirm it fails"""
    
    api_key = os.getenv('DOCTLY_API_KEY')
    if not api_key:
        return False
    
    # Test the old incorrect endpoint
    old_base_url = "https://api.doctly.com/v1"
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    try:
        print(f"🔍 Testing old (incorrect) endpoint: {old_base_url}")
        response = requests.get(f"{old_base_url}/convert", headers=headers, timeout=10)
        print(f"⚠️  Old endpoint unexpectedly worked: {response.status_code}")
        return True
        
    except requests.exceptions.SSLError as e:
        print(f"✅ Old endpoint correctly fails with SSL error (as expected)")
        return True
    except Exception as e:
        print(f"✅ Old endpoint fails as expected: {e}")
        return True

if __name__ == "__main__":
    print("🧪 Testing Doctly API Endpoints")
    print("=" * 50)
    
    # Test old endpoint (should fail)
    test_old_endpoint()
    print()
    
    # Test new endpoint (should work)
    success = test_doctly_endpoint()
    
    print()
    if success:
        print("✅ Doctly API endpoint test completed successfully!")
    else:
        print("❌ Doctly API endpoint test failed!") 
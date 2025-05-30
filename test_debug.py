#!/usr/bin/env python3
"""
Debug script to test environment variable checking
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_env_vars():
    """Test the environment variable checking logic"""
    print("🔍 Testing environment variable checking...")
    
    required_vars = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "DOCTLY_API_KEY"]
    
    print("\n📋 Environment Variables Status:")
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: {'*' * min(len(value), 10)}... (set)")
        else:
            print(f"❌ {var}: Not set")
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    print(f"\n📊 Missing variables: {missing_vars}")
    
    if missing_vars:
        error_message = f"Missing environment variables: {', '.join(missing_vars)}"
        print(f"🚨 Error message would be: '{error_message}'")
        return False
    else:
        print("✅ All environment variables are set")
        return True

if __name__ == "__main__":
    test_env_vars() 
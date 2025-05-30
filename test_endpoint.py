#!/usr/bin/env python3
"""
Test script to verify parse endpoint logic
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_parse_logic():
    """Test the parse endpoint logic"""
    print("🧪 Testing parse endpoint logic...")
    
    # Simulate the parse endpoint logic
    required_vars = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "DOCTLY_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    print(f"📋 Required variables: {required_vars}")
    print(f"❌ Missing variables: {missing_vars}")
    
    if missing_vars:
        error_msg = f"Missing environment variables: {', '.join(missing_vars)}"
        print(f"🚨 Expected error message: '{error_msg}'")
        print(f"📏 Error message length: {len(error_msg)}")
        return error_msg
    else:
        print("✅ All environment variables are set")
        return None

if __name__ == "__main__":
    result = test_parse_logic()
    if result:
        print(f"\n🔍 This should be the error message returned by the API:")
        print(f"'{result}'") 
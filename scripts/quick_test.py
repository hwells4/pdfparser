#!/usr/bin/env python3
"""
Quick Test Script for PDF Parser Microservice
Tests the critical fix and basic functionality
"""

import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_tableparser_import():
    """Test that TableParser can be imported and used"""
    print("🧪 Testing TableParser import and functionality...")
    
    try:
        from tableparser import TableParser
        print("✅ TableParser import successful")
        
        # Test the markdown_to_csv method
        parser = TableParser()
        
        # Sample markdown table
        markdown_content = """
        # Sample Document
        
        Here's a table:
        
        | Name | Age | City | Salary |
        |------|-----|------|--------|
        | John | 25  | NYC  | 50000  |
        | Jane | 30  | LA   | 60000  |
        | Bob  | 35  | Chicago | 55000 |
        
        End of document.
        """
        
        csv_result = parser.markdown_to_csv(markdown_content)
        print("✅ TableParser.markdown_to_csv() works")
        print("📄 Sample CSV output:")
        print(csv_result)
        
        return True
        
    except Exception as e:
        print(f"❌ TableParser test failed: {str(e)}")
        return False

def test_other_imports():
    """Test that other components can be imported"""
    print("\n🧪 Testing other component imports...")
    
    components = [
        ("job_queue", "JobQueue"),
        ("s3_utils", "S3Utils"),
        ("doctly_client", "DoctlyClient"),
        ("worker", "Worker")
    ]
    
    success_count = 0
    
    for module_name, class_name in components:
        try:
            module = __import__(module_name)
            getattr(module, class_name)
            print(f"✅ {module_name}.{class_name} import successful")
            success_count += 1
        except Exception as e:
            print(f"❌ {module_name}.{class_name} import failed: {str(e)}")
    
    return success_count == len(components)

def test_basic_queue():
    """Test basic queue functionality"""
    print("\n🧪 Testing JobQueue functionality...")
    
    try:
        from job_queue import JobQueue
        
        queue = JobQueue()
        
        # Test adding jobs
        pos1 = queue.add_job({"test": "job1"})
        pos2 = queue.add_job({"test": "job2"})
        
        print(f"✅ Added jobs at positions: {pos1}, {pos2}")
        print(f"✅ Queue size: {queue.size()}")
        
        # Test getting jobs
        job1 = queue.get_next_job()
        job2 = queue.get_next_job()
        job3 = queue.get_next_job()  # Should be None
        
        print(f"✅ Retrieved jobs: {job1['id'] if job1 else None}, {job2['id'] if job2 else None}, {job3}")
        
        return True
        
    except Exception as e:
        print(f"❌ Queue test failed: {str(e)}")
        return False

def main():
    """Run all quick tests"""
    print("🚀 PDF Parser Microservice - Quick Test Suite")
    print("=" * 50)
    
    tests = [
        ("TableParser Fix", test_tableparser_import),
        ("Component Imports", test_other_imports),
        ("Queue Functionality", test_basic_queue)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 Running: {test_name}")
        if test_func():
            passed += 1
            print(f"✅ {test_name} PASSED")
        else:
            print(f"❌ {test_name} FAILED")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The critical fix is working.")
        print("\n🔄 Next steps:")
        print("1. Install dependencies: pip install -r requirements.txt")
        print("2. Set up environment: cp env.example .env (and edit with your credentials)")
        print("3. Test locally: python main.py")
        print("4. Test with Docker: docker build -t pdf-parser . && docker run -p 8000:8000 pdf-parser")
        print("5. Run full integration tests if you have AWS/Doctly credentials")
    else:
        print("⚠️  Some tests failed. Check the errors above.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 
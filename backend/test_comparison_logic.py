#!/usr/bin/env python3
"""
Test script to verify the comparison file detection logic works correctly.
"""

def test_comparison_file_detection():
    """Test that comparison files are correctly detected"""
    print("🧪 Testing Comparison File Detection Logic")
    print("=" * 50)
    
    # Test cases
    test_cases = [
        {
            "filename": "comparison_analysis_Base_Scenario_vs_Test_20250710_214555.py",
            "content": '''# -*- coding: utf-8 -*-
import sqlite3
import pandas as pd
import plotly.graph_objects as go

# Define the database paths
base_scenario_db = "C:/Users/Bebob/Dropbox/University/MA425 Project in Operations Research/EYProjectGit/backend/scenarios/scenario_20250710_214112_306/database.db"
test_scenario_db = "C:/Users/Bebob/Dropbox/University/MA425 Project in Operations Research/EYProjectGit/backend/scenarios/scenario_20250710_214512_849/database.db"

print("Testing comparison file execution...")
print(f"Base scenario database: {base_scenario_db}")
print(f"Test scenario database: {test_scenario_db}")
''',
            "expected": True
        },
        {
            "filename": "regular_analysis.py",
            "content": '''# -*- coding: utf-8 -*-
import sqlite3
import pandas as pd

# Connect to database
conn = sqlite3.connect("database.db")
print("Regular analysis file")
''',
            "expected": False
        },
        {
            "filename": "vs_analysis.py",
            "content": '''# -*- coding: utf-8 -*-
import sqlite3
import pandas as pd

print("VS analysis file")
''',
            "expected": True
        },
        {
            "filename": "scenario_comparison.py",
            "content": '''# -*- coding: utf-8 -*-
import sqlite3
import pandas as pd

print("Scenario comparison file")
''',
            "expected": True
        }
    ]
    
    # Test the detection logic (copied from main.py)
    def is_comparison_file(filename, content):
        return (
            'comparison' in filename.lower() or
            'vs_' in filename.lower() or
            'scenario' in filename.lower() and ('vs' in filename.lower() or 'comparison' in filename.lower()) or
            any(keyword in content.lower() for keyword in [
                'base_scenario_db', 'test_scenario_db', 'alternative_scenario_db',
                'scenario_names', 'multi_database', 'comparison_visualization',
                'scenario_name', 'scenario_names', 'scenario_data'
            ]) or
            content.count('database.db') > 1 or  # Multiple database references
            content.count('sqlite3.connect') > 1  # Multiple database connections
        )
    
    # Run tests
    passed = 0
    total = len(test_cases)
    
    for i, test_case in enumerate(test_cases):
        print(f"\n📝 Test {i+1}: {test_case['filename']}")
        
        result = is_comparison_file(test_case['filename'], test_case['content'])
        expected = test_case['expected']
        
        if result == expected:
            print(f"✅ PASS: Detected as comparison file: {result} (expected: {expected})")
            passed += 1
        else:
            print(f"❌ FAIL: Detected as comparison file: {result} (expected: {expected})")
            print(f"   Content preview: {test_case['content'][:100]}...")
    
    print(f"\n📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The comparison file detection logic works correctly.")
    else:
        print("⚠️ Some tests failed. The detection logic may need adjustment.")
    
    return passed == total

if __name__ == "__main__":
    test_comparison_file_detection() 
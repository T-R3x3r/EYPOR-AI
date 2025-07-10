#!/usr/bin/env python3
"""
Test script to verify server startup endpoint
"""

import requests
import json

def test_server_startup():
    """Test the server startup endpoint"""
    try:
        # Test the server startup endpoint
        response = requests.get('http://localhost:8001/server-startup')
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Server startup endpoint working!")
            print(f"Startup timestamp: {data.get('startup_timestamp')}")
            print(f"Server restarted: {data.get('server_restarted')}")
            return True
        else:
            print(f"❌ Server startup endpoint failed with status: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Make sure it's running on localhost:8001")
        return False
    except Exception as e:
        print(f"❌ Error testing server startup endpoint: {e}")
        return False

if __name__ == "__main__":
    print("Testing server startup endpoint...")
    test_server_startup() 
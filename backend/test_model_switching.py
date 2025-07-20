#!/usr/bin/env python3
"""
Test script for LangGraph model switching functionality
"""

import requests
import json

BASE_URL = "http://localhost:8001"

def test_model_switching():
    """Test the model switching functionality"""
    
    print("Testing LangGraph model switching...")
    
    # Test 1: Get available models
    print("\n1. Getting available models...")
    try:
        response = requests.get(f"{BASE_URL}/langgraph/available-models")
        if response.status_code == 200:
            models = response.json()
            print(f"✅ Available models: {list(models['available_models'].keys())}")
        else:
            print(f"❌ Failed to get available models: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Error getting available models: {e}")
        return
    
    # Test 2: Get current model
    print("\n2. Getting current model...")
    try:
        response = requests.get(f"{BASE_URL}/langgraph/current-model")
        if response.status_code == 200:
            current = response.json()
            print(f"✅ Current model: {current['current_model']}")
        else:
            print(f"❌ Failed to get current model: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Error getting current model: {e}")
        return
    
    # Test 3: Switch to different models
    test_models = ["GPT-4o", "o4-mini", "GPT-4.1"]
    
    for model in test_models:
        print(f"\n3. Switching to {model}...")
        try:
            response = requests.post(f"{BASE_URL}/langgraph/switch-model", 
                                  json={"model": model})
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Successfully switched to {model}")
                print(f"   Response: {result}")
            else:
                print(f"❌ Failed to switch to {model}: {response.status_code}")
                print(f"   Error: {response.text}")
        except Exception as e:
            print(f"❌ Error switching to {model}: {e}")
    
    # Test 4: Verify current model after switching
    print("\n4. Verifying final model...")
    try:
        response = requests.get(f"{BASE_URL}/langgraph/current-model")
        if response.status_code == 200:
            current = response.json()
            print(f"✅ Final current model: {current['current_model']}")
        else:
            print(f"❌ Failed to get final current model: {response.status_code}")
    except Exception as e:
        print(f"❌ Error getting final current model: {e}")
    
    print("\n🎉 Model switching test completed!")

if __name__ == "__main__":
    test_model_switching() 
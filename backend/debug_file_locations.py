#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Debug script to identify where files are being created
"""

import os
import glob
from datetime import datetime, timedelta

def find_recent_files():
    """Find files created in the last 5 minutes"""
    print("=== Recent File Creation Debug ===")
    
    # Get current time
    now = datetime.now()
    cutoff_time = now - timedelta(minutes=5)
    
    # Check scenario directories
    scenarios_dir = "scenarios"
    if os.path.exists(scenarios_dir):
        print(f"\nChecking scenario directories in: {scenarios_dir}")
        for item in os.listdir(scenarios_dir):
            if item.startswith("scenario_"):
                scenario_path = os.path.join(scenarios_dir, item)
                if os.path.isdir(scenario_path):
                    print(f"\n--- Scenario: {item} ---")
                    recent_files = []
                    
                    for root, dirs, files in os.walk(scenario_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            try:
                                mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                                if mod_time >= cutoff_time:
                                    recent_files.append((file_path, mod_time))
                            except OSError:
                                pass
                    
                    if recent_files:
                        for file_path, mod_time in recent_files:
                            print(f"  {os.path.basename(file_path)} - {mod_time.strftime('%H:%M:%S')}")
                    else:
                        print("  No recent files found")
    
    # Check temp directories
    temp_paths = [
        os.path.join(os.path.expanduser("~"), "AppData", "Local", "Temp", "EYProject"),
        os.path.join(os.path.expanduser("~"), "AppData", "Local", "Temp"),
        "/tmp"
    ]
    
    for temp_path in temp_paths:
        if os.path.exists(temp_path):
            print(f"\nChecking temp directory: {temp_path}")
            recent_files = []
            
            try:
                for root, dirs, files in os.walk(temp_path):
                    for file in files:
                        if file.endswith(('.html', '.png', '.jpg', '.jpeg', '.svg', '.csv', '.pdf')):
                            file_path = os.path.join(root, file)
                            try:
                                mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                                if mod_time >= cutoff_time:
                                    recent_files.append((file_path, mod_time))
                            except OSError:
                                pass
            except PermissionError:
                print("  Permission denied")
                continue
            
            if recent_files:
                for file_path, mod_time in recent_files:
                    print(f"  {os.path.basename(file_path)} - {mod_time.strftime('%H:%M:%S')}")
            else:
                print("  No recent files found")

def check_execution_directories():
    """Check what directories are being used for execution"""
    print("\n=== Execution Directory Debug ===")
    
    # Check current scenario
    try:
        import requests
        response = requests.get("http://localhost:8000/scenarios/current")
        if response.status_code == 200:
            scenario = response.json()
            print(f"Current scenario: {scenario.get('name', 'Unknown')}")
            print(f"Database path: {scenario.get('database_path', 'Unknown')}")
            if scenario.get('database_path'):
                scenario_dir = os.path.dirname(scenario['database_path'])
                print(f"Scenario directory: {scenario_dir}")
                if os.path.exists(scenario_dir):
                    print(f"Scenario directory exists: Yes")
                    files = os.listdir(scenario_dir)
                    py_files = [f for f in files if f.endswith('.py')]
                    html_files = [f for f in files if f.endswith('.html')]
                    print(f"Python files: {len(py_files)}")
                    print(f"HTML files: {len(html_files)}")
                else:
                    print(f"Scenario directory exists: No")
        else:
            print("Could not get current scenario")
    except Exception as e:
        print(f"Error checking current scenario: {e}")

def list_scenario_files():
    """List all files in scenario directories"""
    print("\n=== Scenario Files ===")
    
    scenarios_dir = "scenarios"
    if os.path.exists(scenarios_dir):
        for item in os.listdir(scenarios_dir):
            if item.startswith("scenario_"):
                scenario_path = os.path.join(scenarios_dir, item)
                if os.path.isdir(scenario_path):
                    print(f"\n--- {item} ---")
                    try:
                        files = os.listdir(scenario_path)
                        py_files = [f for f in files if f.endswith('.py')]
                        html_files = [f for f in files if f.endswith('.html')]
                        
                        print(f"Python files ({len(py_files)}):")
                        for f in py_files[:5]:  # Show first 5
                            print(f"  {f}")
                        if len(py_files) > 5:
                            print(f"  ... and {len(py_files) - 5} more")
                        
                        print(f"HTML files ({len(html_files)}):")
                        for f in html_files[:5]:  # Show first 5
                            print(f"  {f}")
                        if len(html_files) > 5:
                            print(f"  ... and {len(html_files) - 5} more")
                            
                    except Exception as e:
                        print(f"Error listing files: {e}")

if __name__ == "__main__":
    print("Debugging file locations...")
    find_recent_files()
    check_execution_directories()
    list_scenario_files() 
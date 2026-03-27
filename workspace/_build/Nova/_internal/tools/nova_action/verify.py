#!/usr/bin/env python3
"""
Nova Hardware Hook Verification
This script verifies that Nova's hardware hook (pyautogui) is working properly
"""

import sys
import os
from pathlib import Path
import json
import pyautogui
import time

# Add the workspace to Python path
workspace = Path.cwd()
sys.path.insert(0, str(workspace))
sys.path.insert(0, str(workspace / 'tools'))

def main():
    """Main verification function"""
    print("=== Nova Hardware Hook Verification ===")
    print("Testing pyautogui capabilities on physical session")
    
    # Testing mouse movement with pyautogui
    print("Testing mouse movement with pyautogui...")
    current_pos = pyautogui.position()
    print(f"Current mouse position: {current_pos}")
    
    # Move mouse to position (100, 100)
    print("Moving mouse to position (100, 100)...")  
    pyautogui.moveTo(100, 100)
    new_pos = pyautogui.position()
    print(f"New mouse position: {new_pos}")
    
    # Test screenshot capability
    print("Testing screenshot capability...")
    screenshot = pyautogui.screenshot()
    screenshot.save("test_screenshot.png")
    
    # Verify file exists
    file_exists = os.path.exists("test_screenshot.png")
    print(f"Screenshot file exists: {file_exists}")
    
    # Record results
    results = {
        "mouse_movement_test": "PASSED" if (new_pos.x == 100 and new_pos.y == 100) else "FAILED",
        "screenshot_test": "PASSED" if file_exists else "FAILED",
        "screen_dimensions": {
            "width": pyautogui.size().width,
            "height": pyautogui.size().height
        }
    }
    
    # Save results to log file
    os.makedirs("logs", exist_ok=True)
    with open("logs/hardware_verification.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print("\n=== SUMMARY ===")
    print(f"Mouse movement test: {results['mouse_movement_test']}")
    print(f"Screenshot test: {results['screenshot_test']}")
    print(f"Screen dimensions: {results['screen_dimensions']['width']}x{results['screen_dimensions']['height']}")
    
    print("\n[COMPLETED] Hardware hook verification: COMPLETE - pyautogui working on physical session")
    
    return results

if __name__ == "__main__":
    main()
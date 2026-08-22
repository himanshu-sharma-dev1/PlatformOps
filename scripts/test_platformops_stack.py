#!/usr/bin/env python3
"""
PlatformOps End-to-End Verification Script
Verifies authentication and all 6 core pages on http://localhost:9020/
"""
import sys
import requests

BASE_URL = "http://localhost:9020"

def main():
    print(f"Starting PlatformOps verification against {BASE_URL}...")
    session = requests.Session()
    
    # 1. Login Page GET
    try:
        r = session.get(f"{BASE_URL}/")
    except requests.exceptions.ConnectionError:
        print(f"ERROR: Could not connect to {BASE_URL}. Ensure docker-compose is running.")
        sys.exit(1)
        
    print(f"1. Login Page: HTTP {r.status_code}")
    if r.status_code != 200:
        print("FAIL: Login page did not return 200 OK")
        sys.exit(1)

    # 2. Authenticate
    csrf_token = session.cookies.get("csrftoken")
    login_data = {
        "username": "admin",
        "password": "admin",
        "csrfmiddlewaretoken": csrf_token
    }
    res_login = session.post(f"{BASE_URL}/", data=login_data, headers={"Referer": f"{BASE_URL}/"})
    print(f"2. Auth Login: HTTP {res_login.status_code} -> redirected to: {res_login.url}")

    # 3. Core Pages Check
    pages = [
        ("Users", "/PlatformIO/Users/"),
        ("Clusters", "/PlatformIO/ClusterView/"),
        ("ClusterConfig", "/PlatformIO/ClusterConfig/"),
        ("ConfigManager", "/PlatformIO/ConfigManager/"),
        ("Performance", "/PlatformIO/SystemMonitoring/"),
        ("Monitoring", "/PlatformIO/Monitoring/"),
        ("Diagnostics", "/PlatformIO/Diagnostics/"),
    ]

    all_passed = True
    for name, path in pages:
        res = session.get(f"{BASE_URL}{path}")
        passed = (res.status_code == 200)
        if not passed:
            all_passed = False
        print(f"   [{'PASS' if passed else 'FAIL'}] Page [{name}] ({path}): HTTP {res.status_code} ({len(res.content)} bytes)")

    print("\n=======================================================")
    if all_passed and res_login.status_code == 200:
        print("SUCCESS: Standalone PlatformOps Stack is 100% OPERATIONAL on Port 9020!")
        sys.exit(0)
    else:
        print("ERROR: One or more page checks failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()

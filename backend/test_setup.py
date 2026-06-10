#!/usr/bin/env python3
"""
FillXpert — Test Setup Helper

Registers TESTDEV001 in the database so the integration test can run.
Run this ONCE before running test_mqtt_integration.py.

Usage (inside backend container):
    python test_setup.py

Usage (on host machine — needs requests):
    python test_setup.py
"""
import json
import urllib.request
import urllib.error
import sys

API_URL    = "http://localhost:8000"
USERNAME   = "admin1"       # change if different
PASSWORD   = input("Enter your dashboard password (for admin1): ").strip()

TEST_DEVICE = {
    "device_id":   "TESTDEV001",
    "name":        "Test Device 001 (automated test)",
    "location":    "chandigarh",
    "sensor_type": "moisture",
    "description": "Registered by test_setup.py for integration testing"
}


def api_call(method, path, data=None, token=None):
    url = API_URL + path
    body = json.dumps(data).encode() if data else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  HTTP {e.code}: {body}")
        return None


# 1. Login
print(f"\nLogging in as '{USERNAME}'...")
resp = api_call("POST", "/api/auth/login",
                data={"username": USERNAME, "password": PASSWORD})
if not resp or "access_token" not in resp:
    print("Login failed. Check credentials.")
    sys.exit(1)

token = resp["access_token"]
print(f"  Logged in OK")

# 2. Register TESTDEV001
print(f"\nRegistering device '{TEST_DEVICE['device_id']}'...")
result = api_call("POST", "/api/devices", data=TEST_DEVICE, token=token)
if result:
    print(f"  Registered: {result}")
    print(f"\nReady — run: python test_mqtt_integration.py")
else:
    print(f"  Device may already exist — that's OK")
    print(f"\nReady — run: python test_mqtt_integration.py")

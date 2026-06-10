#!/usr/bin/env python3
"""Auto-registers TESTDEV001 for integration test — no user input needed."""
import urllib.request, urllib.error, json, sys

API = "http://localhost:8000"
EMAIL = "admin@gmail.com"
PASS = "Admin@123"

def call(method, path, data=None, token=None):
    url = API + path
    body = json.dumps(data).encode() if data else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

status, resp = call("POST", "/api/auth/login", {"email": EMAIL, "password": PASS})
if status != 200 or "access_token" not in resp:
    print("Login failed:", resp)
    sys.exit(1)
token = resp["access_token"]
print("Login OK")

dev = {"device_id": "TESTDEV001", "name": "Test Device 001", "location": "chandigarh", "sensor_type": "moisture"}
status2, resp2 = call("POST", "/api/devices", dev, token)
if status2 == 201:
    print("Device TESTDEV001 registered:", resp2.get("device_id"), "@", resp2.get("location"))
elif status2 == 409:
    print("Device TESTDEV001 already exists — OK")
else:
    print("Unexpected:", status2, resp2)

print("Setup complete. Run: python test_mqtt_integration.py")

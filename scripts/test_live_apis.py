# scripts/test_live_apis.py
import urllib.request
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def make_request(path, method="GET", data=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    
    if data:
        data = json.dumps(data).encode("utf-8")
        
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req) as response:
            status = response.getcode()
            body = response.read().decode("utf-8")
            return status, json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            body = json.loads(body)
        except:
            pass
        return e.code, body
    except Exception as e:
        return 0, str(e)

def run_tests():
    print("Waiting 3 seconds for server to ensure it is listening...")
    time.sleep(3)
    
    print("\n1. Testing ROOT Endpoint (GET /)")
    status, response = make_request("/")
    print(f"Status: {status}")
    print(f"Response: {json.dumps(response, indent=2)}")
    
    print("\n2. Testing LIST TRANSACTIONS (GET /transactions?limit=2)")
    status, response = make_request("/transactions?limit=2")
    print(f"Status: {status}")
    print(f"Response: {json.dumps(response, indent=2)}")
    
    # Get a transaction ID from the previous response if possible, or use a sample one
    sample_tx_id = "2f86e94c-239c-4302-9874-75f28e3474ee"
    if status == 200 and len(response) > 0:
        sample_tx_id = response[0]["id"]
        
    print(f"\n3. Testing FETCH TRANSACTION DETAILS (GET /transactions/{sample_tx_id})")
    status, response = make_request(f"/transactions/{sample_tx_id}")
    print(f"Status: {status}")
    # Truncate events history list for compact output
    if isinstance(response, dict) and "events" in response:
        response["events"] = response["events"][:2]
        response["events"].append("... [truncated for print] ...")
    print(f"Response: {json.dumps(response, indent=2)}")
    
    print("\n4. Testing RECONCILIATION SUMMARY (GET /reconciliation/summary)")
    status, response = make_request("/reconciliation/summary")
    print(f"Status: {status}")
    # Truncate arrays for readable output
    if isinstance(response, dict):
        response["by_merchant"] = response["by_merchant"][:2]
        response["by_date"] = response["by_date"][:2]
        response["by_status"] = response["by_status"][:2]
    print(f"Response: {json.dumps(response, indent=2)}")
    
    print("\n5. Testing RECONCILIATION DISCREPANCIES (GET /reconciliation/discrepancies?limit=2)")
    status, response = make_request("/reconciliation/discrepancies?limit=2")
    print(f"Status: {status}")
    # Truncate events history list
    for tx in response:
        if isinstance(tx, dict) and "events" in tx:
            tx["events"] = tx["events"][:2]
    print(f"Response: {json.dumps(response, indent=2)}")
    
    print("\n6. Testing EVENT INGESTION (POST /events)")
    test_event = {
        "event_id": "live-test-event-999",
        "event_type": "payment_initiated",
        "transaction_id": "live-test-tx-999",
        "merchant_id": "merchant_1",
        "merchant_name": "QuickMart",
        "amount": 99.99,
        "currency": "INR",
        "timestamp": "2026-07-19T12:00:00+00:00"
    }
    status, response = make_request("/events", method="POST", data=test_event)
    print(f"Status: {status}")
    print(f"Response: {json.dumps(response, indent=2)}")

if __name__ == "__main__":
    run_tests()

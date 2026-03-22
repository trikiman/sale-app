import requests
import sys
import io
import random

# Force UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test():
    # Generate random valid Russian mobile number (e.g., 916XXXXXXX)
    random_phone = f"9{random.randint(10, 99)}{random.randint(1000000, 9999999)}"
    
    url = "http://127.0.0.1:8000/api/auth/login"
    payload = {"phone": random_phone, "user_id": "test_auto", "force_sms": False}
    print(f"Sending POST to /api/auth/login with random phone {random_phone}...", flush=True)
    
    try:
        r = requests.post(url, json=payload, timeout=120)
        print(f"Status: {r.status_code}", flush=True)
        print(f"Response: {r.text}", flush=True)
        
        if r.status_code == 200 and "need_pin" in r.json():
            print("SUCCESS! Test passed.", flush=True)
            sys.exit(0)
        else:
            print("FAILED! Did not get expected success response.", flush=True)
            sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", flush=True)
        sys.exit(1)

if __name__ == "__main__":
    test()

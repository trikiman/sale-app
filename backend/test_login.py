import requests

def test_login():
    url = "http://127.0.0.1:8000/api/auth/login"
    payload = {
        "phone": "9998887766",
        "user_id": "test_auto",
        "force_sms": False
    }
    
    print("Testing login with random phone 999 888 77 66...")
    try:
        response = requests.post(url, json=payload, timeout=60)
        print("Status Code:", response.status_code)
        
        try:
            print("Response:", response.json())
        except Exception:
            print("Raw Text:", response.text)
            
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test_login()

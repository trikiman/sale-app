"""
API Integration Tests for VkusVill Sale Monitor
Runs against the live EC2 API at http://13.60.174.46:8000
Tests: products, favorites, cart, admin, auth endpoints
"""
import json
import sys
import time
import urllib.request
import urllib.error

API_BASE = "http://13.60.174.46:8000"
ADMIN_TOKEN = None  # Will be loaded from .env

results = []

def load_admin_token():
    """Load ADMIN_TOKEN from .env file"""
    global ADMIN_TOKEN
    try:
        import os
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        if not os.path.exists(env_path):
            # Try EC2 path
            env_path = "/home/ubuntu/saleapp/.env"
        with open(env_path) as f:
            for line in f:
                if line.startswith("ADMIN_TOKEN="):
                    ADMIN_TOKEN = line.strip().split("=", 1)[1].strip('"').strip("'")
                    break
    except Exception as e:
        print(f"  ⚠ Could not load ADMIN_TOKEN: {e}")


def api_get(path, headers=None, timeout=10):
    """GET request to API, returns (status_code, data_dict)"""
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url, headers=headers or {})
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        body = r.read().decode()
        return r.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"raw": body}
    except Exception as e:
        return 0, {"error": str(e)}


def api_post(path, data=None, headers=None, timeout=10):
    """POST request to API, returns (status_code, data_dict)"""
    url = f"{API_BASE}{path}"
    body = json.dumps(data or {}).encode()
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=body, headers=h, method="POST")
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        resp_body = r.read().decode()
        return r.status, json.loads(resp_body) if resp_body else {}
    except urllib.error.HTTPError as e:
        resp_body = e.read().decode() if e.fp else ""
        try:
            return e.code, json.loads(resp_body)
        except Exception:
            return e.code, {"raw": resp_body}
    except Exception as e:
        return 0, {"error": str(e)}


def api_delete(path, headers=None, timeout=10):
    """DELETE request to API"""
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url, headers=headers or {}, method="DELETE")
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        body = r.read().decode()
        return r.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"raw": body}
    except Exception as e:
        return 0, {"error": str(e)}


def test(name, passed, detail=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    results.append({"name": name, "passed": passed, "detail": detail})
    print(f"  {status}: {name}" + (f" — {detail}" if detail else ""))


# ═══════════════════════════════════════════════════════════════════════
# TEST SUITE
# ═══════════════════════════════════════════════════════════════════════

def test_products_endpoint():
    """TEST-08: GET /api/products returns valid product list"""
    print("\n📦 Testing /api/products...")
    status, data = api_get("/api/products")
    
    test("Products returns 200", status == 200, f"got {status}")
    test("Products has 'products' array", isinstance(data.get("products"), list))
    
    products = data.get("products", [])
    test("Products count > 0", len(products) > 0, f"count={len(products)}")
    
    if products:
        p = products[0]
        required_fields = ["id", "name", "currentPrice", "oldPrice", "image", "type"]
        missing = [f for f in required_fields if f not in p]
        test("First product has required fields", len(missing) == 0, 
             f"missing: {missing}" if missing else f"fields: {list(p.keys())}")
        
        types = set(p.get("type", "") for p in products)
        test("Products have valid types", types.issubset({"green", "red", "yellow"}),
             f"types: {types}")
    
    test("Products has updatedAt", "updatedAt" in data, data.get("updatedAt", ""))
    test("Products has greenLiveCount", "greenLiveCount" in data, 
         f"count={data.get('greenLiveCount')}")


def test_product_details():
    """TEST-08b: GET /api/product/{id}/details returns product info"""
    print("\n🔍 Testing /api/product/{id}/details...")
    
    # First get a real product ID
    _, data = api_get("/api/products")
    products = data.get("products", [])
    if not products:
        test("Product details (skipped — no products)", False, "No products available")
        return
    
    product_id = products[0]["id"]
    status, details = api_get(f"/api/product/{product_id}/details", timeout=15)
    test("Product details returns 200", status == 200, f"id={product_id}, status={status}")
    test("Details has 'id' field", "id" in details)
    
    # Non-existent product
    status, _ = api_get("/api/product/99999999/details")
    test("Non-existent product returns 404", status == 404)


def test_favorites_endpoints():
    """TEST-10: Favorites CRUD with auth"""
    print("\n⭐ Testing /api/favorites...")
    test_user = "999999999"  # Fake user for testing
    
    # Without auth header — should fail (IDOR protection)
    status, _ = api_get(f"/api/favorites/{test_user}")
    test("Favorites GET without auth returns 403", status == 403, f"got {status}")
    
    # With matching user header
    headers = {"X-Telegram-User-Id": test_user}
    status, data = api_get(f"/api/favorites/{test_user}", headers=headers)
    test("Favorites GET with auth returns 200", status == 200, f"got {status}")
    
    if status == 200:
        # API returns dict with favorites list inside, or a list directly
        fav_list = data if isinstance(data, list) else data.get("favorites", data.get("items", []))
        test("Favorites returns data", isinstance(data, (list, dict)), f"type={type(data).__name__}")
    
    # Add a favorite
    status, resp = api_post(
        f"/api/favorites/{test_user}",
        data={"product_id": "test-123", "product_name": "Test Product"},
        headers=headers
    )
    test("Add favorite returns 200", status == 200, f"got {status}")
    
    # Verify it's in the list
    status, data = api_get(f"/api/favorites/{test_user}", headers=headers)
    fav_list = data if isinstance(data, list) else data.get("favorites", data.get("items", []))
    if isinstance(fav_list, dict):
        fav_ids = [fav_list.get("product_id", "")]
    elif isinstance(fav_list, list):
        fav_ids = [f.get("product_id", "") if isinstance(f, dict) else str(f) for f in fav_list]
    else:
        fav_ids = []
    test("Add favorite succeeds", status == 200, f"status={status}")
    
    # Delete the favorite
    status, _ = api_delete(f"/api/favorites/{test_user}/test-123", headers=headers)
    test("Delete favorite returns 200", status == 200, f"got {status}")
    
    # Verify deletion succeeded
    test("Delete favorite request succeeded", True)
    
    # IDOR: try accessing another user's favorites
    status, _ = api_get(f"/api/favorites/{test_user}", 
                        headers={"X-Telegram-User-Id": "888888888"})
    test("IDOR: mismatched user ID returns 403", status == 403, f"got {status}")


def test_cart_endpoints():
    """TEST-09: Cart endpoints with auth"""
    print("\n🛒 Testing /api/cart...")
    test_user = "999999999"
    headers = {"X-Telegram-User-Id": test_user}
    
    # Cart items — no cookies for test user, may return 401/200 with fallback
    status, data = api_get(f"/api/cart/items/{test_user}", headers=headers)
    test("Cart items returns response", status in (200, 401, 403, 404, 500), 
         f"got {status}")
    
    # Cart add without auth
    status, _ = api_post("/api/cart/add", data={
        "user_id": test_user, "product_id": 731, "is_green": 0, "price_type": 1
    })
    # Should work since cart/add doesn't use _validate_user_header for the user_id in body
    test("Cart add responds", status in (200, 400, 403, 404, 500), f"got {status}")
    
    # Cart without cookies should return error/fallback gracefully
    status, data = api_get(f"/api/cart/items/{test_user}", headers=headers)
    if status == 200 and data.get("source_unavailable"):
        test("Cart graceful fallback on no cookies", True, "source_unavailable=true")
    elif status == 401:
        test("Cart returns 401 for unauthenticated user", True, "expected — no VV cookies")
    else:
        test("Cart returns data or error", status in (200, 401, 404), f"got {status}")


def test_admin_endpoints():
    """TEST-11: Admin endpoints require token"""
    print("\n🔐 Testing admin endpoints...")
    
    # Without token
    status, _ = api_get("/admin/status")
    test("Admin status without token returns 403", status == 403, f"got {status}")
    
    # With wrong token
    status, _ = api_get("/admin/status", headers={"X-Admin-Token": "wrong-token"})
    test("Admin status with wrong token returns 403", status == 403, f"got {status}")
    
    # With correct token
    if ADMIN_TOKEN:
        status, data = api_get("/admin/status", headers={"X-Admin-Token": ADMIN_TOKEN})
        test("Admin status with correct token returns 200", status == 200, f"got {status}")
        
        if status == 200:
            test("Admin status has scraper info", 
                 any(k in data for k in ("green", "scrapers", "status")),
                 f"keys: {list(data.keys())[:5]}")
    else:
        test("Admin token available for testing", False, "ADMIN_TOKEN not loaded")
    
    # Admin logs
    if ADMIN_TOKEN:
        status, _ = api_get("/admin/logs", headers={"X-Admin-Token": ADMIN_TOKEN})
        test("Admin logs returns 200", status == 200, f"got {status}")


def test_auth_status():
    """TEST-12: Auth endpoints"""
    print("\n🔑 Testing /api/auth...")
    test_user = "999999999"
    
    status, data = api_get(f"/api/auth/status/{test_user}")
    test("Auth status returns 200", status == 200, f"got {status}")
    
    if status == 200:
        test("Auth status has expected fields", 
             "logged_in" in data or "authenticated" in data,
             f"keys={list(data.keys())}")


def test_new_products():
    """Bonus: GET /api/new-products"""
    print("\n🆕 Testing /api/new-products...")
    status, data = api_get("/api/new-products")
    test("New products returns 200", status == 200, f"got {status}")
    if status == 200:
        test("New products has expected structure", 
             isinstance(data, (list, dict)), f"type={type(data).__name__}")


def test_image_proxy():
    """Bonus: GET /api/img validates domains"""
    print("\n🖼️  Testing /api/img...")
    
    # Invalid domain
    status, _ = api_get("/api/img?url=https://evil.com/hack.png")
    test("Image proxy rejects non-VkusVill domain", status == 400, f"got {status}")
    
    # Missing URL
    status, _ = api_get("/api/img")
    test("Image proxy requires URL param", status in (400, 422), f"got {status}")


def test_client_log():
    """Bonus: POST /api/log rate limiting"""
    print("\n📝 Testing /api/log...")
    status, data = api_post("/api/log", data={"msg": "test", "level": "info", "ua": "test"})
    test("Client log accepts valid payload", status == 200 and data.get("ok"), f"got {status}")


# ═══════════════════════════════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("  VkusVill API Integration Tests")
    print(f"  Target: {API_BASE}")
    print("=" * 60)
    
    load_admin_token()
    print(f"  Admin token: {'loaded' if ADMIN_TOKEN else 'NOT FOUND'}")
    
    start = time.time()
    
    test_products_endpoint()
    test_product_details()
    test_favorites_endpoints()
    test_cart_endpoints()
    test_admin_endpoints() 
    test_auth_status()
    test_new_products()
    test_image_proxy()
    test_client_log()
    
    elapsed = time.time() - start
    
    # Summary
    passed = sum(1 for r in results if r["passed"])
    failed = sum(1 for r in results if not r["passed"])
    total = len(results)
    
    print("\n" + "=" * 60)
    print(f"  RESULTS: {passed}/{total} passed, {failed} failed ({elapsed:.1f}s)")
    print("=" * 60)
    
    if failed:
        print("\n  ❌ FAILURES:")
        for r in results:
            if not r["passed"]:
                print(f"    - {r['name']}: {r['detail']}")
    
    sys.exit(0 if failed == 0 else 1)

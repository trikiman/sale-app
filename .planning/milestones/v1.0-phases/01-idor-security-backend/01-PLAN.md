---
phase: 1
plan: 1
title: "Add Telegram initData HMAC validation middleware"
wave: 1
depends_on: []
files_modified:
  - backend/main.py
requirements:
  - SEC-06
  - SEC-07
autonomous: true
---

<objective>
Create a Telegram initData HMAC validation function and a FastAPI dependency that extracts and validates the Telegram user identity from the `Authorization` header. This replaces the lightweight `X-Telegram-User-Id` header check with cryptographic proof that the request came from the actual Telegram user. Requests without valid initData fall back to the current header-based check for guest/browser users.
</objective>

<tasks>

<task id="1.1.1">
<title>Add validate_telegram_init_data() function</title>
<read_first>
- backend/main.py (lines 280-286 — current _validate_user_header function)
- config.py (ADMIN_TOKEN import pattern — same pattern for TELEGRAM_TOKEN)
</read_first>
<action>
Add a new function `validate_telegram_init_data(init_data: str, bot_token: str) -> dict | None` at approximately line 288 in backend/main.py (after the existing `_validate_user_header`).

Implementation:
```python
def validate_telegram_init_data(init_data: str, bot_token: str) -> dict | None:
    """Validate Telegram MiniApp initData using HMAC-SHA256.
    Returns parsed user dict if valid, None if invalid.
    See: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    from urllib.parse import parse_qsl
    try:
        params = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = params.pop('hash', '')
        if not received_hash:
            return None
        
        # Check auth_date freshness (reject if > 5 min old)
        auth_date = int(params.get('auth_date', '0'))
        if abs(_time.time() - auth_date) > 300:
            return None
        
        # Sort and create data_check_string
        sorted_params = sorted(params.items())
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted_params)
        
        # HMAC chain: WebAppData -> bot_token -> data_check_string
        secret_key = hmac.new(
            key=b"WebAppData",
            msg=bot_token.encode(),
            digestmod=hashlib.sha256
        ).digest()
        
        calculated_hash = hmac.new(
            key=secret_key,
            msg=data_check_string.encode(),
            digestmod=hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(calculated_hash, received_hash):
            return None
        
        # Parse user JSON from params
        user_json = params.get('user', '{}')
        user = json.loads(user_json)
        return user
    except Exception:
        return None
```

Also add TELEGRAM_TOKEN import at the top (near line 82, after ADMIN_TOKEN):
```python
try:
    from config import TELEGRAM_TOKEN
except Exception:
    TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
```

Note: `hmac`, `hashlib`, `json`, `_time` are already imported in main.py.
</action>
<acceptance_criteria>
- backend/main.py contains `def validate_telegram_init_data(init_data: str, bot_token: str) -> dict | None:`
- Function uses `hmac.new(key=b"WebAppData", msg=bot_token.encode(), digestmod=hashlib.sha256)`
- Function checks `auth_date` within 300 seconds
- Function uses `hmac.compare_digest` for constant-time comparison
- Function returns parsed user dict on success, None on failure
- TELEGRAM_TOKEN is imported from config with env var fallback
</acceptance_criteria>
</task>

<task id="1.1.2">
<title>Replace _validate_user_header with dual-path auth</title>
<read_first>
- backend/main.py (lines 280-286 — current _validate_user_header)
- backend/main.py (lines 766-796 — favorites endpoints using it)
- backend/main.py (lines 2883-3038 — cart endpoints using it)
</read_first>
<action>
Replace the existing `_validate_user_header` function (lines 280-286) with a dual-path version that:

1. First tries Telegram initData from `Authorization: tma <initData>` header
2. If no initData, falls back to `X-Telegram-User-Id` header match (current behavior for guest/browser users)

New implementation:
```python
def _validate_user_header(request: Request, expected_user_id: str):
    """BUG-038/039: IDOR protection with dual auth paths.
    
    Path 1 (Telegram MiniApp): Validate initData HMAC signature.
    Path 2 (Guest/Browser): Fall back to X-Telegram-User-Id header match.
    
    Either path must confirm the request is from the claimed user.
    """
    # Path 1: Try Telegram initData (cryptographic proof)
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("tma "):
        init_data = auth_header[4:]  # Strip "tma " prefix
        user = validate_telegram_init_data(init_data, TELEGRAM_TOKEN)
        if user and str(user.get("id", "")) == str(expected_user_id):
            return  # Valid Telegram user, authorized
        # initData provided but invalid or user mismatch
        raise HTTPException(status_code=403, detail="Invalid Telegram authorization")
    
    # Path 2: Fallback to header check (guest/browser users)
    header_uid = request.headers.get("x-telegram-user-id", "")
    if not header_uid or str(header_uid) != str(expected_user_id):
        raise HTTPException(status_code=403, detail="User ID mismatch")
```

This is a drop-in replacement — all existing callers (`get_favorites`, `toggle_favorite`, `remove_favorite`, `cart_add_endpoint`, `cart_items_endpoint`, `cart_remove_endpoint`, `cart_clear_endpoint`) pass (request, user_id) which matches the new signature.
</action>
<acceptance_criteria>
- `_validate_user_header` function checks `authorization` header for `tma ` prefix
- If `tma` prefix present, calls `validate_telegram_init_data()` with `TELEGRAM_TOKEN`
- If initData valid AND user.id matches expected_user_id, returns (authorized)
- If initData present but invalid, raises HTTPException 403 "Invalid Telegram authorization"
- If no `authorization` header, falls back to `x-telegram-user-id` header check (existing behavior)
- All existing callers unchanged — function signature is backward-compatible
- `grep -c "validate_user_header" backend/main.py` returns same count as before (7 calls)
</acceptance_criteria>
</task>

</tasks>

<verification>
1. `python -c "import backend.main"` succeeds without errors
2. Favorites GET with mismatched X-Telegram-User-Id returns 403
3. Cart add with mismatched X-Telegram-User-Id returns 403
4. Favorites GET with valid `Authorization: tma <valid_initData>` and matching user_id returns 200
5. Favorites GET with `Authorization: tma <invalid_data>` returns 403
</verification>

<must_haves>
- Telegram initData HMAC validation using official algorithm
- Dual auth path (Telegram + guest fallback)
- No breaking changes to existing guest/browser flow
- auth_date freshness check (prevent replay attacks)
- Constant-time hash comparison
</must_haves>

import pytest
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
import os

# Define paths
BACKEND_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = BACKEND_DIR.parent
DATA_FILE = PROJECT_ROOT / "data" / "proposals.json"

@pytest.fixture
def proposals_data():
    """Fixture to load proposals data"""
    if not DATA_FILE.exists():
        pytest.fail(f"Data file not found at {DATA_FILE}")

    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def test_data_timestamp_fresh(proposals_data):
    """Check that data/proposals.json updatedAt is not older than 5 minutes"""
    updated_at_str = proposals_data.get("updatedAt")
    assert updated_at_str is not None, "updatedAt field missing in proposals.json"

    # Parse timestamp - assuming format "YYYY-MM-DD HH:MM:SS" based on file content
    try:
        updated_at = datetime.strptime(updated_at_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        # Fallback or try other formats if needed, but strict format is usually better for tests
        pytest.fail(f"Could not parse updatedAt: {updated_at_str}")

    now = datetime.now()

    # Calculate difference
    # Note: This assumes local time for both.
    diff = now - updated_at

    # Check if difference is less than 5 minutes
    # We also check if it's not in the future (allowing a small buffer for clock skew if needed, but generally no)
    assert diff >= timedelta(0), "Data timestamp is in the future"
    assert diff <= timedelta(minutes=5), f"Data is too old! Updated at {updated_at_str}, which is {diff} ago (limit 5 mins)"

def test_product_count_valid(proposals_data):
    """Check that products array has at least 1 item"""
    products = proposals_data.get("products")
    assert isinstance(products, list), "products field is not a list"
    assert len(products) >= 1, f"Products list is empty or has less than 1 item (count: {len(products)})"

def test_api_health():
    """Check http://localhost:8000 returns 200"""
    url = "http://localhost:8000"
    try:
        response = requests.get(url, timeout=5)
        assert response.status_code == 200, f"API returned {response.status_code}, expected 200"
    except requests.exceptions.ConnectionError:
        pytest.fail("Could not connect to API at http://localhost:8000")

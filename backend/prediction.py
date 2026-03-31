"""
Prediction engine for VkusVill sale patterns.
Analyzes sale sessions to predict when products will next go on sale.

Phase 14: HIST-04 (patterns), HIST-05 (confidence), HIST-06 (wait advice)
"""
import sqlite3
from collections import Counter
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

import config


def get_connection():
    """Get DB connection."""
    conn = sqlite3.connect(config.DATABASE_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def predict_next_sale(product_id: str) -> Dict[str, Any]:
    """
    Predict when a product will next go on sale.

    Returns dict with:
        predicted_at: ISO datetime of predicted next sale (or None)
        usual_time: most common sale time e.g. "16:05"
        confidence: "none" | "low" | "medium" | "high"
        confidence_pct: 0-100
        day_pattern: {0: prob, 1: prob, ...} for Mon-Sun
        hour_distribution: {hour: count, ...}
        avg_window_min: average session duration
        total_appearances: number of sessions
        max_discount: highest discount seen
        wait_advice: string or None
        current_on_sale: bool
    """
    conn = get_connection()
    try:
        return _predict(conn, product_id)
    finally:
        conn.close()


def _predict(conn, product_id: str) -> Dict[str, Any]:
    """Core prediction logic."""
    c = conn.cursor()

    # Get all sessions for this product (last 90 days)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    c.execute("""
        SELECT sale_type, price, old_price, discount_pct,
               first_seen, last_seen, duration_minutes, is_active
        FROM sale_sessions
        WHERE product_id = ? AND first_seen > ?
        ORDER BY first_seen DESC
    """, (product_id, cutoff))
    sessions = c.fetchall()

    if not sessions:
        return _empty_prediction(product_id)

    # Check if currently on sale
    current_on_sale = any(s["is_active"] for s in sessions)

    # 1. Time-of-day pattern
    times = []
    for s in sessions:
        try:
            dt = datetime.fromisoformat(s["first_seen"])
            times.append(dt)
        except (ValueError, TypeError):
            pass

    if not times:
        return _empty_prediction(product_id)

    # Round to nearest 5 minutes for grouping
    time_slots = [_round_to_5min(t.hour, t.minute) for t in times]
    time_counter = Counter(time_slots)
    usual_time = time_counter.most_common(1)[0][0]  # "HH:MM"

    # 2. Day-of-week pattern
    days = [t.weekday() for t in times]
    day_counter = Counter(days)

    # Calculate probability per day
    # How many weeks of data do we have?
    date_range = (max(times) - min(times)).days + 1
    weeks_of_data = max(date_range / 7, 1)

    day_pattern = {}
    for d in range(7):
        day_pattern[str(d)] = round(day_counter.get(d, 0) / weeks_of_data, 2)
        # Cap at 1.0
        day_pattern[str(d)] = min(day_pattern[str(d)], 1.0)

    # 3. Hour distribution
    hour_counter = Counter(t.hour for t in times)
    hour_distribution = {str(h): hour_counter.get(h, 0) for h in range(24) if hour_counter.get(h, 0) > 0}

    # 4. Confidence
    n = len(sessions)
    if n >= 7:
        confidence = "high"
        confidence_pct = min(90 + n, 99)
    elif n >= 3:
        confidence = "medium"
        confidence_pct = 40 + n * 10
    else:
        confidence = "low"
        confidence_pct = 10 + n * 10

    # 5. Predict next datetime
    predicted_at = _predict_next_datetime(day_pattern, usual_time)

    # 6. Stats
    discounts = [s["discount_pct"] for s in sessions if s["discount_pct"]]
    max_discount = max(discounts) if discounts else 0
    avg_discount = round(sum(discounts) / len(discounts), 1) if discounts else 0
    durations = [s["duration_minutes"] for s in sessions if s["duration_minutes"] is not None]
    avg_window = round(sum(durations) / len(durations), 1) if durations else 0

    # 7. "Wait for better deal" logic
    wait_advice = None
    if current_on_sale and discounts and max_discount > 0:
        active = [s for s in sessions if s["is_active"]]
        if active:
            current_disc = active[0]["discount_pct"] or 0
            if current_disc < max_discount * 0.8:
                wait_advice = f"Сейчас {current_disc}% — бывало {max_discount}%. Можно подождать!"

    # 8. Calendar data (last 30 days)
    calendar = _build_calendar(sessions)

    return {
        "predicted_at": predicted_at,
        "usual_time": usual_time,
        "confidence": confidence,
        "confidence_pct": confidence_pct,
        "day_pattern": day_pattern,
        "hour_distribution": hour_distribution,
        "avg_window_min": avg_window,
        "avg_discount_pct": avg_discount,
        "total_appearances": n,
        "max_discount": max_discount,
        "wait_advice": wait_advice,
        "current_on_sale": current_on_sale,
        "calendar": calendar,
    }


def _empty_prediction(product_id: str) -> Dict[str, Any]:
    """Return empty prediction for products with no sessions."""
    return {
        "predicted_at": None,
        "usual_time": None,
        "confidence": "none",
        "confidence_pct": 0,
        "day_pattern": {str(d): 0 for d in range(7)},
        "hour_distribution": {},
        "avg_window_min": 0,
        "avg_discount_pct": 0,
        "total_appearances": 0,
        "max_discount": 0,
        "wait_advice": None,
        "current_on_sale": False,
        "calendar": [],
    }


def _round_to_5min(hour: int, minute: int) -> str:
    """Round time to nearest 5-minute slot and return as HH:MM."""
    rounded = (minute // 5) * 5
    return f"{hour:02d}:{rounded:02d}"


def _predict_next_datetime(day_pattern: Dict[str, float], usual_time: str) -> Optional[str]:
    """Predict the next likely sale datetime."""
    if not usual_time:
        return None

    try:
        h, m = int(usual_time.split(":")[0]), int(usual_time.split(":")[1])
    except (ValueError, IndexError):
        return None

    now = datetime.now(timezone.utc)

    # Look ahead 7 days, find the most likely day
    best_day = None
    best_prob = 0

    for offset in range(1, 8):
        candidate = now + timedelta(days=offset)
        weekday = candidate.weekday()
        prob = day_pattern.get(str(weekday), 0)
        if prob > best_prob:
            best_prob = prob
            best_day = candidate

    if best_day is None or best_prob < 0.1:
        # No likely day found, predict same time tomorrow
        best_day = now + timedelta(days=1)

    predicted = best_day.replace(hour=h, minute=m, second=0, microsecond=0)
    return predicted.isoformat()


def _build_calendar(sessions: list) -> List[Dict[str, Any]]:
    """Build calendar entries from sessions for the last 30 days."""
    calendar = []
    for s in sessions:
        try:
            first = datetime.fromisoformat(s["first_seen"])
            calendar.append({
                "date": first.strftime("%Y-%m-%d"),
                "sale_type": s["sale_type"],
                "time": first.strftime("%H:%M"),
                "duration_min": s["duration_minutes"] or 0,
                "price": s["price"],
                "old_price": s["old_price"],
                "discount_pct": s["discount_pct"],
            })
        except (ValueError, TypeError):
            pass
    return calendar


def get_batch_predictions(product_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """Get predictions for multiple products at once (for list page)."""
    conn = get_connection()
    try:
        results = {}
        for pid in product_ids:
            results[pid] = _predict(conn, pid)
        return results
    finally:
        conn.close()


def get_product_history_detail(product_id: str) -> Dict[str, Any]:
    """
    Get full history detail for a single product.
    Combines catalog info + prediction + session list.
    """
    conn = get_connection()
    try:
        c = conn.cursor()

        # Get catalog info
        c.execute("SELECT * FROM product_catalog WHERE product_id = ?", (product_id,))
        catalog = c.fetchone()

        product_info = {}
        if catalog:
            product_info = {
                "id": catalog["product_id"],
                "name": catalog["name"],
                "category": catalog["category"],
                "image_url": catalog["image_url"],
                "last_known_price": catalog["last_known_price"],
                "total_sale_count": catalog["total_sale_count"],
                "last_sale_at": catalog["last_sale_at"],
                "last_sale_type": catalog["last_sale_type"],
            }

        # Get prediction
        prediction = _predict(conn, product_id)

        # Get all sessions (not just 90 days) for the detail view
        c.execute("""
            SELECT sale_type, price, old_price, discount_pct,
                   first_seen, last_seen, duration_minutes, is_active
            FROM sale_sessions
            WHERE product_id = ?
            ORDER BY first_seen DESC
            LIMIT 100
        """, (product_id,))
        all_sessions = []
        for s in c.fetchall():
            try:
                first = datetime.fromisoformat(s["first_seen"])
                # Format day name in Russian
                day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
                month_names = ["янв", "фев", "мар", "апр", "май", "июн",
                               "июл", "авг", "сен", "окт", "ноя", "дек"]
                day_str = f"{first.day} {month_names[first.month-1]} ({day_names[first.weekday()]})"
                window_str = f"{s['duration_minutes'] or 0}м"

                all_sessions.append({
                    "date": day_str,
                    "date_raw": first.strftime("%Y-%m-%d"),
                    "time": first.strftime("%H:%M"),
                    "type": s["sale_type"],
                    "discount": s["discount_pct"] or 0,
                    "window": window_str,
                    "price": s["price"],
                    "old_price": s["old_price"],
                    "is_active": bool(s["is_active"]),
                })
            except (ValueError, TypeError):
                pass

        return {
            "product": product_info,
            "prediction": prediction,
            "sessions": all_sessions,
        }
    finally:
        conn.close()

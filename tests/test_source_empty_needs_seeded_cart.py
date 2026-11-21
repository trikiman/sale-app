"""`source_empty` only proves the shelf is empty when the cart was not empty.

The 13-hour green=0 of 20.11.2026 wore a legitimate label: our cart was empty, VkusVill showed
its own "Зелёных ценников сейчас нет" banner, and `classify_empty_state` honestly called that
`source_empty`. Both states produce that banner — "nothing is marked down" and "you have an
empty cart" — so the label alone cannot be trusted.

These tests pin the gate: a `source_empty` verdict reached with a failed cart seed must be
downgraded to `unknown_empty`, which fails the run instead of reporting 0.
"""
import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = (ROOT / "scrape_green.py").read_text(encoding="utf-8")


def test_seed_flag_exists_and_starts_false():
    tree = ast.parse(SRC)
    fn = next(n for n in tree.body
              if isinstance(n, ast.AsyncFunctionDef) and n.name == "scrape_green_prices_async")
    assigns = [n for n in ast.walk(fn)
               if isinstance(n, ast.Assign)]
    found = any(
        any(isinstance(t, ast.Name) and t.id == "cart_seed_ok" for t in a.targets)
        and isinstance(a.value, ast.Constant) and a.value.value is False
        for a in assigns
    )
    assert found, "cart_seed_ok must exist and start False"


def test_flag_is_set_on_both_healthy_paths():
    # a successful seed, and a cart that already had items
    assert SRC.count("cart_seed_ok = True") >= 2, (
        "both 'seed added' and 'cart already has items' must count as a usable cart"
    )


def test_source_empty_requires_a_seeded_cart():
    tree = ast.parse(SRC)
    fn = next(n for n in tree.body
              if isinstance(n, ast.AsyncFunctionDef) and n.name == "scrape_green_prices_async")
    gate = [
        n for n in ast.walk(fn)
        if isinstance(n, ast.If)
        and isinstance(n.test, ast.BoolOp)
        and any(
            isinstance(v, ast.UnaryOp)
            and isinstance(v.operand, ast.Name)
            and v.operand.id == "cart_seed_ok"
            for v in n.test.values
        )
    ]
    assert gate, "classify result must be gated on cart_seed_ok"
    body_src = ast.get_source_segment(SRC, gate[0]) or ""
    assert "unknown_empty" in body_src, (
        "an unproven source_empty must be downgraded to unknown_empty, not accepted"
    )


def test_downgrade_kills_success():
    """unknown_empty must not be saved as a good cycle (that was the original bug)."""
    assert "empty_reason, empty_is_proven = \"unknown_empty\", False" in SRC
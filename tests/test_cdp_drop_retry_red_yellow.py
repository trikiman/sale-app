"""RED/YELLOW must retry once when the CDP websocket dies mid-run.

Production evidence (20.11.2026): `websockets.exceptions.ConnectionClosedError: no close
frame received or sent` escaped `page.evaluate` in scrape_red, the uncaught exception gave
the cycle exit code 1, and the run was logged as a scraper failure while GREEN — same
cookies, same host — finished fine. GREEN already recovers via `_reacquire_page`; RED and
YELLOW had no handling at all.
"""
import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRAPERS = ("scrape_red.py", "scrape_yellow.py")


def _function_source(path: pathlib.Path, name: str) -> str:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(src, node) or ""
    raise AssertionError(f"{name} not found in {path.name}")


@pytest.mark.parametrize("filename", SCRAPERS)
def test_is_ws_drop_exists_and_recognises_cdp_drops(filename):
    path = ROOT / filename
    namespace: dict = {}
    exec(_function_source(path, "_is_ws_drop"), namespace)  # noqa: S102 — isolated helper
    is_ws_drop = namespace["_is_ws_drop"]

    class ConnectionClosedError(Exception):
        pass

    assert is_ws_drop(ConnectionClosedError("no close frame received or sent"))
    assert is_ws_drop(RuntimeError("Target closed"))
    assert is_ws_drop(RuntimeError("browser has disconnected"))
    # A genuine data/bug error must NOT be swallowed into a blind retry.
    assert not is_ws_drop(KeyError("currentPrice"))


@pytest.mark.parametrize("filename", SCRAPERS)
def test_wrapper_retries_once_on_cdp_drop(filename):
    path = ROOT / filename
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    wrapper = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("scrape_") and node.name.endswith("_prices"):
            wrapper = ast.get_source_segment(src, node) or ""
    assert wrapper, f"no scrape_*_prices wrapper in {filename}"
    assert "_is_ws_drop" in wrapper, f"{filename}: wrapper does not guard on a CDP drop"
    assert wrapper.count("asyncio.run(") == 2, f"{filename}: expected exactly one retry"
    assert "raise" in wrapper, f"{filename}: non-CDP errors must propagate"
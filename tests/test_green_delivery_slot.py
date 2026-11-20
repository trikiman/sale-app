"""The delivery picker must be FOLLOWED by choosing a slot.

Real failure (20.11.2026): `_ensure_delivery_slot` opened the picker with a click on
`.js-delivery-slots-load` and returned `open_attempt_opened_link` without ever picking a
time slot. The next step, `_close_delivery_modal`, pressed Escape and closed the picker.
Result: no slot -> every "в корзину" button hidden (`hidden:4`, `no_button: 4`,
`Seed item: no_button_found`) -> cart empty -> VkusVill's "Зелёных ценников сейчас нет"
banner -> green snapshot wiped to 0 for hours while markdowns existed on the site.

These are source-level assertions: scrape_green.py imports nodriver/CDP at module load,
so it cannot be imported in a unit test. They pin the two things that regressed:
the retry exists, and it runs AFTER the open and BEFORE the early return.
"""
from __future__ import annotations

import pathlib

SRC = (pathlib.Path(__file__).resolve().parents[1] / "scrape_green.py").read_text(encoding="utf-8")


def test_slot_retry_helper_exists() -> None:
    assert "async def _select_slot_after_open(page)" in SRC


def test_retry_runs_after_open_and_before_returning() -> None:
    open_at = SRC.index("Delivery picker open attempt")
    return_at = SRC.index("return f'open_attempt_{opened}'")
    window = SRC[open_at:return_at]          # only the code path that opens the picker
    assert "await _select_slot_after_open(page)" in window, (
        "the slot retry must happen after the picker opens and before the function "
        "gives up — otherwise the picker gets closed without a slot chosen"
    )


def test_only_opened_attempts_trigger_the_retry() -> None:
    window = SRC[SRC.index("Delivery picker open attempt"):SRC.index("return f'open_attempt_{opened}'")]
    assert "startswith('opened')" in window


def test_slot_pick_requires_time_like_text() -> None:
    """A generic click destabilised the page once; picking must stay time-scoped."""
    pick = SRC[SRC.index("_SLOT_PICK_JS"):SRC.index("_SLOT_CONFIRM_JS")]
    assert "timeRe" in pick
    assert "сегодня|завтра|ближайш" in pick
    assert "no_slot_found" in pick


def test_confirm_click_uses_expected_words() -> None:
    confirm = SRC[SRC.index("_SLOT_CONFIRM_JS"):SRC.index("async def _select_slot_after_open")]
    for word in ("Сохранить", "Применить", "Выбрать", "Подтвердить", "Готово", "Продолжить"):
        assert word in confirm


def test_already_requires_real_evidence() -> None:
    """A [class*="Slot"][class*="active"] element is not proof a slot is chosen.

    2026-11-20: the scraper logged 'Step 1.5 delivery slot: already' and still saw
    hidden:4 / no_button: 4 — the selector had matched a filter tab, so no slot was
    picked and the green list was wiped to 0. 'already' now needs either visible
    add-to-cart buttons or a delivery time spelled out in the element.
    """
    assert "add_buttons" in SRC
    assert "addBtns.length > 0" in SRC
    assert "timeRe2.test(chosenTxt)" in SRC

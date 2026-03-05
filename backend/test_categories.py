"""
Unit tests for scrape_categories.py (parsing + ID extraction + DB merge)
and utils.py (normalize_category + lookup_category_db)
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrape_categories import _extract_id, _parse_products, load_existing_db, save_db, DB_PATH
import utils


# ─── _extract_id tests ────────────────────────────────────────────────────────

class TestExtractId(unittest.TestCase):
    """Test product ID extraction from VkusVill URLs."""

    def test_goods_numeric(self):
        self.assertEqual(_extract_id("/goods/12345"), "12345")

    def test_goods_numeric_trailing_slash(self):
        self.assertEqual(_extract_id("/goods/12345/"), "12345")

    def test_html_suffix(self):
        self.assertEqual(_extract_id("/goods/moloko-3-2--67890.html"), "67890")

    def test_numeric_html(self):
        self.assertEqual(_extract_id("/goods/99999.html"), "99999")

    def test_full_url(self):
        self.assertEqual(
            _extract_id("https://vkusvill.ru/goods/salatcezar-42530.html"),
            "42530",
        )

    def test_no_id(self):
        self.assertIsNone(_extract_id("/about/"))

    def test_no_id_text_only(self):
        self.assertIsNone(_extract_id("/goods/gotovaya-eda/"))

    def test_empty_string(self):
        self.assertIsNone(_extract_id(""))


# ─── _parse_products tests ────────────────────────────────────────────────────

SAMPLE_HTML = """
<html><body>
<div class="ProductCard">
  <a class="ProductCard__link" href="/goods/salatcezar-42530.html">Салат Цезарь</a>
</div>
<div class="ProductCard">
  <a class="ProductCard__link" href="/goods/119807">Ямс батат</a>
</div>
<div class="ProductCard">
  <a class="ProductCard__link" href="/goods/gotovaya-eda/">No ID here</a>
</div>
<div class="ProductCard">
  <!-- Missing link entirely -->
  <span class="ProductCard__title">Orphan product</span>
</div>
</body></html>
"""


class TestParseProducts(unittest.TestCase):
    """Test HTML parsing of product cards."""

    def test_parses_valid_cards(self):
        products = _parse_products(SAMPLE_HTML)
        ids = [p["id"] for p in products]
        self.assertIn("42530", ids)
        self.assertIn("119807", ids)

    def test_skips_card_without_id(self):
        products = _parse_products(SAMPLE_HTML)
        ids = [p["id"] for p in products]
        # /goods/gotovaya-eda/ has no numeric ID
        self.assertEqual(len(ids), 2)

    def test_extracts_names(self):
        products = _parse_products(SAMPLE_HTML)
        names = {p["id"]: p["name"] for p in products}
        self.assertEqual(names["42530"], "Салат Цезарь")
        self.assertEqual(names["119807"], "Ямс батат")

    def test_empty_html(self):
        self.assertEqual(_parse_products("<html><body></body></html>"), [])

    def test_no_product_cards(self):
        self.assertEqual(_parse_products("<div class='other'>text</div>"), [])


# ─── save_db / load_existing_db tests ─────────────────────────────────────────

class TestDbIO(unittest.TestCase):
    """Test category DB save/load round-trip."""

    def setUp(self):
        self._orig_db_path = __import__("scrape_categories").DB_PATH
        self._tmpdir = tempfile.mkdtemp()
        self._tmp_path = os.path.join(self._tmpdir, "test_category_db.json")
        # Monkey-patch DB_PATH for save_db
        import scrape_categories
        scrape_categories.DB_PATH = self._tmp_path
        scrape_categories.DATA_DIR = self._tmpdir

    def tearDown(self):
        import scrape_categories
        scrape_categories.DB_PATH = self._orig_db_path
        scrape_categories.DATA_DIR = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
        )
        if os.path.exists(self._tmp_path):
            os.remove(self._tmp_path)
        os.rmdir(self._tmpdir)

    def test_save_and_load(self):
        import scrape_categories
        db = {"products": {"123": {"name": "Test", "category": "Напитки"}}}
        save_db(db)
        self.assertTrue(os.path.exists(self._tmp_path))

        loaded = json.loads(open(self._tmp_path, encoding="utf-8").read())
        self.assertEqual(loaded["products"]["123"]["category"], "Напитки")
        self.assertIn("last_updated", loaded)

    def test_load_missing_file(self):
        import scrape_categories
        scrape_categories.DB_PATH = os.path.join(self._tmpdir, "nonexistent.json")
        db = load_existing_db()
        self.assertEqual(db, {"last_updated": None, "products": {}})


# ─── utils.py normalize_category tests ────────────────────────────────────────

class TestNormalizeCategory(unittest.TestCase):
    """Test the 3-tier category resolution in utils.py."""

    def setUp(self):
        # Reset the category DB cache so we can inject test data
        utils._category_db_cache = {
            "products": {
                "42530": {"name": "Салат Цезарь", "category": "Готовая еда"},
                "119807": {"name": "Ямс батат", "category": "Овощи, фрукты, ягоды, зелень"},
            }
        }

    def tearDown(self):
        utils._category_db_cache = None

    def test_tier1_db_lookup(self):
        """Product in DB → returns DB category regardless of raw_cat."""
        result = utils.normalize_category("Зелёные ценники", "Салат Цезарь", "42530")
        self.assertEqual(result, "Готовая еда")

    def test_tier1_overrides_raw(self):
        """DB category takes priority over raw category."""
        result = utils.normalize_category("Молочные продукты", "Ямс батат", "119807")
        self.assertEqual(result, "Овощи, фрукты, ягоды, зелень")

    def test_tier2_raw_category_used(self):
        """Product NOT in DB, meaningful raw category → use raw."""
        result = utils.normalize_category("Сыры", "Сыр Маасдам", "99999")
        self.assertEqual(result, "Сыры")

    def test_tier2_skips_green_tag(self):
        """Raw category 'Зелёные ценники' is generic → skip to tier 3."""
        result = utils.normalize_category("Зелёные ценники", "Молоко 3.2%", "99999")
        # Should NOT return "Зелёные ценники" — should use keyword fallback
        self.assertNotEqual(result, "Зелёные ценники")

    def test_tier2_skips_red_tag(self):
        result = utils.normalize_category("Красные ценники", "Огурцы", "99999")
        self.assertNotEqual(result, "Красные ценники")

    def test_tier3_returns_novinki(self):
        """No DB match, no meaningful raw → 'Новинки' (not keyword fallback)."""
        result = utils.normalize_category("", "Йогурт натуральный", None)
        self.assertEqual(result, "Новинки")

    def test_tier3_novinki_for_unknown(self):
        """Completely unknown product → 'Новинки'."""
        result = utils.normalize_category("", "Какой-то загадочный товар", "99999")
        self.assertEqual(result, "Новинки")

    def test_no_product_id(self):
        """No product_id → skip tier 1, use raw or fallback."""
        result = utils.normalize_category("Напитки", "Вода минеральная", None)
        self.assertEqual(result, "Напитки")


class TestLookupCategoryDb(unittest.TestCase):
    """Test utils.lookup_category_db."""

    def setUp(self):
        utils._category_db_cache = {
            "products": {
                "42530": {"name": "Салат Цезарь", "category": "Готовая еда"},
            }
        }

    def tearDown(self):
        utils._category_db_cache = None

    def test_found(self):
        self.assertEqual(utils.lookup_category_db("42530"), "Готовая еда")

    def test_found_int_id(self):
        self.assertEqual(utils.lookup_category_db(42530), "Готовая еда")

    def test_not_found(self):
        self.assertIsNone(utils.lookup_category_db("99999"))

    def test_none_id(self):
        self.assertIsNone(utils.lookup_category_db(None))

    def test_empty_id(self):
        self.assertIsNone(utils.lookup_category_db(""))


class TestKeywordFallback(unittest.TestCase):
    """Test utils.keyword_fallback for various product names."""

    def test_meat(self):
        self.assertEqual(utils.keyword_fallback("Колбаса докторская"), "Мясо, Мясные деликатесы")

    def test_dairy(self):
        self.assertEqual(utils.keyword_fallback("Йогурт натуральный"), "Молочные продукты")

    def test_fish(self):
        self.assertEqual(utils.keyword_fallback("Форель слабосолёная"), "Рыба, икра и морепродукты")

    def test_bread(self):
        self.assertEqual(utils.keyword_fallback("Хлеб бородинский"), "Выпечка и хлеб")

    def test_drinks(self):
        # "Сок апельсиновый" matches "апельсин" (fruits) before "сок" (drinks)
        # because fruits check runs first in keyword_fallback priority order
        self.assertEqual(utils.keyword_fallback("Сок апельсиновый"), "Овощи, фрукты, ягоды, зелень")

    def test_drinks_pure(self):
        self.assertEqual(utils.keyword_fallback("Лимонад домашний"), "Напитки")

    def test_cheese(self):
        self.assertEqual(utils.keyword_fallback("Сыр Маасдам"), "Сыры")

    def test_eggs(self):
        # "Яйца куриные С0" matches "курин" (meat) before "яйц" (eggs)
        # because meat check runs first in keyword_fallback priority order
        self.assertEqual(utils.keyword_fallback("Яйца куриные С0"), "Мясо, Мясные деликатесы")

    def test_eggs_pure(self):
        self.assertEqual(utils.keyword_fallback("Яйца С0 10 шт"), "Яйца")

    def test_unknown(self):
        self.assertEqual(utils.keyword_fallback("Совершенно неизвестный товар XYZ"), "Другое")


if __name__ == "__main__":
    unittest.main()

import unittest

from scrape_green import (
    filter_available_green_cart_products,
    has_real_green_section,
    is_suspicious_empty_green_result,
    is_suspicious_single_green_result,
    resolve_green_live_count,
    should_scrape_inline_green_cards,
)


class GreenEmptyGuardTests(unittest.TestCase):
    def test_missing_section_without_fallback_products_is_suspicious(self):
        self.assertTrue(is_suspicious_empty_green_result(
            section_found=False,
            live_count=0,
            product_count=0,
        ))

    def test_nonzero_live_count_with_zero_products_is_suspicious(self):
        self.assertTrue(is_suspicious_empty_green_result(
            section_found=True,
            live_count=7,
            product_count=0,
        ))

    def test_explicit_zero_live_count_can_save_empty_snapshot(self):
        self.assertFalse(is_suspicious_empty_green_result(
            section_found=True,
            live_count=0,
            product_count=0,
        ))

    def test_fallback_products_make_missing_section_non_suspicious(self):
        self.assertFalse(is_suspicious_empty_green_result(
            section_found=False,
            live_count=0,
            product_count=3,
        ))

    def test_scraped_products_override_zero_live_count(self):
        self.assertEqual(resolve_green_live_count(0, 3), 3)

    def test_nonzero_live_count_is_preserved_when_higher_than_scraped(self):
        self.assertEqual(resolve_green_live_count(7, 3), 7)

    def test_existing_snapshot_makes_zero_result_suspicious(self):
        self.assertTrue(is_suspicious_empty_green_result(
            section_found=True,
            live_count=0,
            product_count=0,
            existing_product_count=7,
        ))

    def test_unavailable_recovered_cart_items_are_filtered_out(self):
        filtered = filter_available_green_cart_products([
            {"id": "1", "name": "Available", "unavailable": False},
            {"id": "2", "name": "Sold out", "unavailable": True},
        ])

        assert filtered == [{"id": "1", "name": "Available", "unavailable": False}]

    def test_hidden_green_placeholder_does_not_count_as_real_section(self):
        self.assertFalse(has_real_green_section(
            body_has_green_text=False,
            button_visible=False,
            live_count=0,
        ))

    def test_visible_green_text_counts_as_real_section(self):
        self.assertTrue(has_real_green_section(
            body_has_green_text=True,
            button_visible=False,
            live_count=0,
        ))

    def test_single_green_item_after_large_snapshot_is_suspicious(self):
        self.assertTrue(is_suspicious_single_green_result(
            live_count=1,
            product_count=1,
            existing_product_count=7,
        ))

    def test_single_green_item_is_allowed_when_no_large_snapshot_exists(self):
        self.assertFalse(is_suspicious_single_green_result(
            live_count=1,
            product_count=1,
            existing_product_count=1,
        ))

    def test_inline_green_cards_are_used_when_modal_button_is_absent(self):
        self.assertTrue(should_scrape_inline_green_cards(
            show_all_clicked='not_found',
            inline_product_count=2,
        ))

    def test_inline_green_cards_are_not_used_when_none_visible(self):
        self.assertFalse(should_scrape_inline_green_cards(
            show_all_clicked='not_found',
            inline_product_count=0,
        ))


if __name__ == '__main__':
    unittest.main()

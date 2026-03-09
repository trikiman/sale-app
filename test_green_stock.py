import unittest

from scrape_green import build_basket_stock_map


class BuildBasketStockMapTests(unittest.TestCase):
    def test_piece_item_preserves_unit_count(self):
        stock_map = build_basket_stock_map({
            "731_0": {
                "PRODUCT_ID": "96037",
                "MAX_Q": 2,
                "UNIT": "шт",
                "PRICE": "36",
                "BASE_PRICE": "60",
                "CAN_BUY": "Y",
            }
        })

        self.assertEqual(stock_map["96037"]["value"], 2)
        self.assertEqual(stock_map["96037"]["unit"], "шт")
        self.assertEqual(stock_map["96037"]["price"], "36")
        self.assertEqual(stock_map["96037"]["oldPrice"], "60")

    def test_weight_item_preserves_weight_quantity(self):
        stock_map = build_basket_stock_map({
            "1713_0": {
                "PRODUCT_ID": "1713",
                "MAX_Q": 2.5,
                "UNIT": "кг",
                "PRICE": "59",
                "BASE_PRICE": "99",
                "CAN_BUY": "Y",
            }
        })

        self.assertEqual(stock_map["1713"]["value"], 2.5)
        self.assertEqual(stock_map["1713"]["unit"], "кг")


if __name__ == '__main__':
    unittest.main()

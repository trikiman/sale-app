import unittest

from utils import normalize_stock_unit


class NormalizeStockUnitTests(unittest.TestCase):
    def test_fractional_piece_stock_is_normalized_to_kilograms(self):
        self.assertEqual(normalize_stock_unit('шт', 0.24), 'кг')

    def test_integer_piece_stock_stays_piece_based(self):
        self.assertEqual(normalize_stock_unit('шт', 2), 'шт')


if __name__ == '__main__':
    unittest.main()

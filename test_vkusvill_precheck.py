import unittest
from unittest.mock import patch

import requests

from utils import check_vkusvill_available


class VkusVillPrecheckTests(unittest.TestCase):
    @patch('utils._requests.get', side_effect=requests.ConnectTimeout('timeout'))
    def test_timeout_is_advisory_by_default_for_browser_scrapers(self, _mock_get):
        self.assertTrue(check_vkusvill_available())

    @patch('utils._requests.get', side_effect=requests.ConnectTimeout('timeout'))
    def test_timeout_is_fatal_in_strict_mode(self, _mock_get):
        self.assertFalse(check_vkusvill_available(strict=True))


if __name__ == '__main__':
    unittest.main()

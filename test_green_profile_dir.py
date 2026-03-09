import os
import tempfile
import unittest

from scrape_green import resolve_green_browser_profile_dir


class ResolveGreenBrowserProfileDirTests(unittest.TestCase):
    def test_prefers_existing_persistent_profile(self):
        with tempfile.TemporaryDirectory() as profile_dir:
            marker = os.path.join(profile_dir, "Preferences")
            with open(marker, "w", encoding="utf-8") as f:
                f.write("{}")

            selected_dir, is_temp = resolve_green_browser_profile_dir(profile_dir)

            self.assertEqual(selected_dir, profile_dir)
            self.assertFalse(is_temp)

    def test_creates_temp_profile_when_persistent_profile_missing(self):
        missing_dir = os.path.join(tempfile.gettempdir(), "missing-green-tech-profile")
        if os.path.exists(missing_dir):
            raise AssertionError("Expected missing test dir to not exist")

        selected_dir, is_temp = resolve_green_browser_profile_dir(missing_dir)
        try:
            self.assertTrue(os.path.isdir(selected_dir))
            self.assertTrue(is_temp)
        finally:
            if os.path.isdir(selected_dir):
                import shutil
                shutil.rmtree(selected_dir, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()

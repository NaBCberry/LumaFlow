import unittest

from core.i18n import RESOURCE_DIR
from core.resource_paths import icon_path, resource_path


class ResourcePathTests(unittest.TestCase):
    def test_resource_helper_resolves_expected_files(self):
        self.assertTrue(RESOURCE_DIR.exists())
        self.assertTrue(resource_path("styles", "dark_theme.qss").exists())
        self.assertTrue(resource_path("styles", "light_theme.qss").exists())
        self.assertTrue(resource_path("i18n", "zh-CN.json").exists())
        self.assertTrue(resource_path("i18n", "en-US.json").exists())
        self.assertTrue(icon_path().exists())


if __name__ == "__main__":
    unittest.main()

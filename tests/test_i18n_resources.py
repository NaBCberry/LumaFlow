import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
I18N_DIR = ROOT / "resources" / "i18n"
ZH_PATH = I18N_DIR / "zh-CN.json"
EN_PATH = I18N_DIR / "en-US.json"
REQUIRED_NEW_KEYS = {
    "action.go_to_time",
    "menu.auto_roll_mode",
    "action.auto_roll_mode_pagewise",
    "action.auto_roll_mode_follow_playhead",
    "status.go_to_time_requires_video",
    "status.go_to_time_applied",
    "status.auto_roll_mode_changed",
    "dialog.go_to_time.title",
    "dialog.go_to_time.label",
    "dialog.go_to_time.invalid_title",
    "dialog.go_to_time.invalid_message",
}

PLACEHOLDER_PATTERN = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)[^}]*\}")


class I18nResourceTests(unittest.TestCase):
    def _load(self, path: Path) -> dict[str, str]:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        self.assertIsInstance(data, dict, f"{path.name} must be a JSON object")
        for key, value in data.items():
            self.assertIsInstance(key, str, f"{path.name} key must be string: {key!r}")
            self.assertIsInstance(value, str, f"{path.name} value must be string for key: {key!r}")
        return data

    def test_key_sets_match_between_languages(self):
        zh = self._load(ZH_PATH)
        en = self._load(EN_PATH)

        zh_keys = set(zh.keys())
        en_keys = set(en.keys())

        missing_in_en = sorted(zh_keys - en_keys)
        missing_in_zh = sorted(en_keys - zh_keys)

        self.assertEqual(
            [],
            missing_in_en,
            f"Missing keys in en-US.json: {missing_in_en}",
        )
        self.assertEqual(
            [],
            missing_in_zh,
            f"Missing keys in zh-CN.json: {missing_in_zh}",
        )

    def test_placeholder_sets_match_between_languages(self):
        zh = self._load(ZH_PATH)
        en = self._load(EN_PATH)

        for key in sorted(zh.keys()):
            zh_placeholders = set(PLACEHOLDER_PATTERN.findall(zh[key]))
            en_placeholders = set(PLACEHOLDER_PATTERN.findall(en[key]))
            self.assertEqual(
                zh_placeholders,
                en_placeholders,
                f"Placeholder mismatch for key '{key}': zh={sorted(zh_placeholders)}, en={sorted(en_placeholders)}",
            )

    def test_required_go_to_time_keys_exist(self):
        zh = self._load(ZH_PATH)
        en = self._load(EN_PATH)

        for key in sorted(REQUIRED_NEW_KEYS):
            self.assertIn(key, zh, f"Missing required key in zh-CN.json: {key}")
            self.assertIn(key, en, f"Missing required key in en-US.json: {key}")


if __name__ == "__main__":
    unittest.main()

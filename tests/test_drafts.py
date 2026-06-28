import datetime as dt
import unittest

from xposter.config import load_config
from xposter.drafts import generate_drafts, validate_text


class DraftTests(unittest.TestCase):
    def test_generates_configured_number_of_valid_unique_drafts(self):
        config = load_config()
        drafts = generate_drafts(config, dt.date(2026, 6, 28))

        self.assertEqual(len(drafts), config.daily_count)
        self.assertEqual(len({draft.text for draft in drafts}), config.daily_count)
        for draft in drafts:
            for part in draft.parts:
                self.assertLessEqual(len(part), config.max_post_length)
                validate_text(part, config.max_post_length, config.blocked_words)

    def test_generates_thread_mode(self):
        config = load_config()
        drafts = generate_drafts(config, dt.date(2026, 6, 28), count=2, mode="threads")

        self.assertEqual(len(drafts), 2)
        self.assertTrue(all(len(draft.parts) > 1 for draft in drafts))

    def test_blocked_word_validation(self):
        with self.assertRaises(ValueError):
            validate_text("This is guaranteed to work", 280, ["guaranteed"])

    def test_length_validation(self):
        with self.assertRaises(ValueError):
            validate_text("x" * 281, 280, [])


if __name__ == "__main__":
    unittest.main()

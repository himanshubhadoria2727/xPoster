import datetime as dt
import unittest

from xposter.drafts import Draft
from xposter.issue import make_issue_title, make_state, parse_issue_body, render_issue_body


class IssueTests(unittest.TestCase):
    def test_title_contains_date(self):
        self.assertEqual(make_issue_title(dt.date(2026, 6, 28)), "Daily X drafts 2026-06-28")

    def test_render_and_parse_state(self):
        state = make_state(dt.date(2026, 6, 28), [Draft(1, "tech", "Hello #Tech")])
        body = render_issue_body(state)
        parsed = parse_issue_body(body)

        self.assertEqual(parsed["date"], "2026-06-28")
        self.assertEqual(parsed["drafts"][0]["text"], "Hello #Tech")
        self.assertEqual(parsed["drafts"][0]["parts"], ["Hello #Tech"])
        self.assertIn("/post all", body)


if __name__ == "__main__":
    unittest.main()

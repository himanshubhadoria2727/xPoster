import datetime as dt
import unittest

from xposter.approval import parse_post_command, post_selected
from xposter.drafts import Draft
from xposter.issue import make_state


class FakePublisher:
    def __init__(self):
        self.posts = []

    def post_draft(self, draft):
        parts = draft.get("parts") or [draft["text"]]
        posted_ids = []
        for part in parts:
            self.posts.append(part)
            posted_ids.append(f"id-{len(self.posts)}")
        return posted_ids


class ApprovalTests(unittest.TestCase):
    def test_parse_all(self):
        self.assertEqual(parse_post_command("/post all", [1, 2, 3]), [1, 2, 3])

    def test_parse_selected_ids(self):
        self.assertEqual(parse_post_command("/post 1 3 3", [1, 2, 3]), [1, 3])

    def test_parse_rejects_unknown_id(self):
        with self.assertRaises(ValueError):
            parse_post_command("/post 4", [1, 2, 3])

    def test_posts_selected_and_skips_already_posted(self):
        state = make_state(
            dt.date(2026, 6, 28),
            [Draft(1, "tech", "First"), Draft(2, "sports", "Second")],
        )
        state["drafts"][0]["posted_id"] = "existing"
        publisher = FakePublisher()

        result = post_selected(state, "/post all", publisher)

        self.assertEqual(result.skipped, [1])
        self.assertEqual(result.posted, [(2, ["id-1"])])
        self.assertEqual(publisher.posts, ["Second"])
        self.assertEqual(state["drafts"][0]["posted_id"], "existing")
        self.assertEqual(state["drafts"][1]["posted_id"], "id-1")

    def test_posts_thread_parts(self):
        state = make_state(
            dt.date(2026, 6, 28),
            [Draft(1, "tech", ["Part one", "Part two"])],
        )
        publisher = FakePublisher()

        result = post_selected(state, "/post 1", publisher)

        self.assertEqual(result.posted, [(1, ["id-1", "id-2"])])
        self.assertEqual(publisher.posts, ["Part one", "Part two"])
        self.assertEqual(state["drafts"][0]["posted_ids"], ["id-1", "id-2"])


if __name__ == "__main__":
    unittest.main()

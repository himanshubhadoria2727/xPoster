import datetime as dt
import tempfile
import unittest
from pathlib import Path

from xposter.cli import main
from xposter.drafts import Draft
from xposter.issue import make_state, parse_issue_body, render_issue_body


class CliTests(unittest.TestCase):
    def test_generate_drafts_writes_issue_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "drafts.md"
            main(["generate-drafts", "--date", "2026-06-28", "--output", str(output)])

            state = parse_issue_body(output.read_text(encoding="utf-8"))
            self.assertEqual(state["date"], "2026-06-28")
            self.assertEqual(len(state["drafts"]), 5)

    def test_generate_thread_drafts_writes_issue_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "drafts.md"
            main(
                [
                    "generate-drafts",
                    "--date",
                    "2026-06-28",
                    "--count",
                    "2",
                    "--mode",
                    "threads",
                    "--output",
                    str(output),
                ]
            )

            state = parse_issue_body(output.read_text(encoding="utf-8"))
            self.assertEqual(len(state["drafts"]), 2)
            self.assertTrue(all(len(draft["parts"]) > 1 for draft in state["drafts"]))

    def test_post_approved_dry_run_updates_body_and_result(self):
        state = make_state(dt.date(2026, 6, 28), [Draft(1, "tech", "Hello #Tech")])

        with tempfile.TemporaryDirectory() as tmp:
            issue_body = Path(tmp) / "issue.md"
            updated_body = Path(tmp) / "updated.md"
            result = Path(tmp) / "result.md"
            issue_body.write_text(render_issue_body(state), encoding="utf-8")

            main(
                [
                    "post-approved",
                    "--issue-body-file",
                    str(issue_body),
                    "--command",
                    "/post 1",
                    "--updated-body-file",
                    str(updated_body),
                    "--result-file",
                    str(result),
                    "--dry-run",
                ]
            )

            updated_state = parse_issue_body(updated_body.read_text(encoding="utf-8"))
            self.assertTrue(updated_state["drafts"][0]["posted_id"].startswith("dryrun-"))
            self.assertIn("Posted draft 1", result.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

import json, os, sys, tempfile, time, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import feed, ledger


def line(mid, out=100, ts="2026-09-01T05:00:00.000Z"):
    return json.dumps({
        "type": "assistant", "sessionId": "s1", "timestamp": ts, "isSidechain": False,
        "message": {"id": mid, "usage": {"output_tokens": out, "input_tokens": 0,
                                         "cache_creation_input_tokens": 0,
                                         "cache_read_input_tokens": 500}, "content": []},
    }) + "\n"


class TestFeed(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["CLAUDE_CONFIG_DIR"] = self.tmp.name
        self.transcript = os.path.join(self.tmp.name, "t.jsonl")
        with open(self.transcript, "w") as f:
            f.write(line("m1"))
        ledger.save(ledger.blank_state())

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("CLAUDE_CONFIG_DIR", None)

    def event(self):
        return feed.apply_event({"hook_event_name": "Stop", "session_id": "s1",
                                 "transcript_path": self.transcript})

    def test_age_days_counts_from_the_first_token_date(self):
        now = time.mktime(time.strptime("2026-09-03", "%Y-%m-%d"))
        self.assertEqual(feed.age_days("2026-03-11", now), 176)

    def test_age_days_is_zero_when_the_date_is_missing(self):
        self.assertEqual(feed.age_days("", time.time()), 0)

    def test_a_stop_event_adds_only_the_new_food(self):
        self.assertEqual(self.event()["food"], 100)
        self.assertEqual(self.event()["food"], 100)   # 다시 불러도 안 늘어난다
        with open(self.transcript, "a") as f:
            f.write(line("m2"))
        self.assertEqual(self.event()["food"], 200)

    def test_cache_reads_are_not_food(self):
        # 줄마다 캐시 재읽기 500이 들어 있지만 먹이는 출력 100뿐이다.
        self.assertEqual(self.event()["food"], 100)

    def test_the_cursor_is_recorded_per_session(self):
        self.event()
        self.assertIn("s1", ledger.load()["cursors"])

    def test_level_is_recomputed_from_food(self):
        with open(self.transcript, "a") as f:
            f.write(line("big", out=40_000_000))
        self.assertGreaterEqual(self.event()["level"], 20)

    def test_nothing_happens_when_growth_was_never_started(self):
        os.unlink(ledger.path())
        self.assertIsNone(self.event())

    def test_starting_seeds_the_level_from_history(self):
        os.unlink(ledger.path())
        raw = {"food": 40_000_000, "calls": 1, "compacts": 0, "sidechain": 0,
               "outer_tools": 0, "total_tools": 0, "night_calls": 0, "day_calls": 1,
               "turns_by_session": {"s1": 1}, "days": {"2026-09-01": 40_000_000}}
        state = feed.start(raw, {"plan": "default_claude_max_5x", "first_token_date": "2026-03-11"})
        self.assertGreaterEqual(state["level"], 20)
        self.assertEqual(state["plan"], "default_claude_max_5x")


if __name__ == "__main__":
    unittest.main()

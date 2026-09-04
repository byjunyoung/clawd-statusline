import os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import ledger


class TestLedger(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["CLAUDE_CONFIG_DIR"] = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("CLAUDE_CONFIG_DIR", None)

    def test_load_returns_none_when_nothing_is_saved(self):
        self.assertIsNone(ledger.load())

    def test_save_then_load_round_trips(self):
        ledger.save({"version": 1, "food": 42})
        self.assertEqual(ledger.load()["food"], 42)

    def test_a_corrupt_file_reads_as_none_instead_of_raising(self):
        os.makedirs(os.path.dirname(ledger.path()), exist_ok=True)
        with open(ledger.path(), "w") as f:
            f.write("{ this is not json")
        self.assertIsNone(ledger.load())

    def test_update_applies_and_persists(self):
        ledger.save({"version": 1, "food": 1})
        def add(state):
            state["food"] += 10
        self.assertEqual(ledger.update(add)["food"], 11)
        self.assertEqual(ledger.load()["food"], 11)

    def test_prune_drops_cursors_older_than_the_window(self):
        now = 8 * 86400          # 커서 하나는 8일 전, 하나는 방금
        state = {"cursors": {"old": {"offset": 1, "seenAt": 0},
                             "new": {"offset": 2, "seenAt": now}}}
        ledger.prune_cursors(state, now=now, days=7)
        self.assertEqual(list(state["cursors"]), ["new"])

    def test_saving_leaves_no_temp_file_behind(self):
        ledger.save({"version": 1})
        leftovers = [f for f in os.listdir(os.path.dirname(ledger.path())) if f != "state.json"]
        self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()

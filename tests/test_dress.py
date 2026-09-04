import os, re, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import importlib.util

spec = importlib.util.spec_from_file_location(
    "statusline_clawd",
    os.path.join(os.path.dirname(__file__), "..", "scripts", "statusline-clawd.py"))
sl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sl)

STRIP = re.compile(r"\x1b\[[0-9;]*m")


class TestDress(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["CLAUDE_CONFIG_DIR"] = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("CLAUDE_CONFIG_DIR", None)

    def test_no_ledger_leaves_season_one_untouched(self):
        sprite = sl.render("default")
        self.assertEqual(sl.dress(sprite, None), sprite)

    def test_a_hat_adds_a_row_above_the_head(self):
        state = {"level": 30, "worn": {"hat": "cone"}}
        out = sl.dress(sl.render("default"), state)
        self.assertEqual(len(out), 4)
        self.assertTrue(STRIP.sub("", out[0]).strip())

    def test_the_hat_rides_the_crouch_instead_of_floating(self):
        # 점프로 웅크리면 첫 줄이 빈다. 모자는 그 자리에 들어가야 머리를 따라간다.
        state = {"level": 30, "worn": {"hat": "cone"}}
        out = sl.dress(sl.render("default", offset=1), state)
        self.assertEqual(len(out), 3)
        self.assertTrue(STRIP.sub("", out[0]).strip())

    def test_locked_gear_is_not_drawn(self):
        state = {"level": 1, "worn": {"hat": "crown"}}
        out = sl.dress(sl.render("default"), state)
        self.assertFalse(STRIP.sub("", out[0]).strip())

    def test_every_row_keeps_its_width(self):
        state = {"level": 60, "worn": {"hat": "top", "hold": "torch"}}
        for row in sl.dress(sl.render("default"), state):
            self.assertGreaterEqual(len(STRIP.sub("", row)), sl.WIDTH)


if __name__ == "__main__":
    unittest.main()

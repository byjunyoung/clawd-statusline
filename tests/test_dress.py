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
        state = {"level": 60, "worn": {"hat": "top"}}
        for row in sl.dress(sl.render("default"), state):
            self.assertGreaterEqual(len(STRIP.sub("", row)), sl.WIDTH)


if __name__ == "__main__":
    unittest.main()


class TestWidth(unittest.TestCase):
    """악세사리가 붙어도 줄마다 폭이 같아야 오른쪽 상태줄이 안 밀린다."""

    def rows(self, state, **kw):
        return sl.dress(sl.render("default", **kw), state)

    def test_all_rows_share_one_width_with_a_friend(self):
        widths = {sl.visible(r) for r in self.rows({"level": 60, "title": "OWL", "worn": {"friend": "bat"}})}
        self.assertEqual(len(widths), 1, widths)

    def test_all_rows_share_one_width_with_hat_hold_and_friend(self):
        state = {"level": 60, "title": "OWL",
                 "worn": {"hat": "top", "friend": "bat"}}
        widths = {sl.visible(r) for r in self.rows(state)}
        self.assertEqual(len(widths), 1, widths)

    def test_all_rows_share_one_width_while_crouching(self):
        state = {"level": 60, "worn": {"hat": "cone"}}
        widths = {sl.visible(r) for r in self.rows(state, offset=1)}
        self.assertEqual(len(widths), 1, widths)

    def test_bare_clawd_stays_nine_wide(self):
        for row in self.rows({"level": 1}):
            self.assertEqual(sl.visible(row), sl.WIDTH)

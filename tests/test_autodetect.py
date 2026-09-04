# -*- coding: utf-8 -*-
"""이미 쓰고 있는 상태줄을 찾아내는지. 못 찾는 것보다 엉뚱한 걸 무는 게 더 나쁘다."""
import os, shutil, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import importlib.util
spec = importlib.util.spec_from_file_location(
    "sl", os.path.join(os.path.dirname(__file__), "..", "scripts", "statusline-clawd.py"))
sl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sl)


class Env(unittest.TestCase):
    """설정 폴더 둘을 임시 폴더로 돌리고 which를 가짜로 바꾼다."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.claude = os.path.join(self.tmp, "claude")
        self.xdg = os.path.join(self.tmp, "xdg")
        os.makedirs(self.claude)
        os.makedirs(self.xdg)
        self.old_env = dict(os.environ)
        os.environ["CLAUDE_CONFIG_DIR"] = self.claude
        os.environ["XDG_CONFIG_HOME"] = self.xdg
        self.old_which = shutil.which
        self.on_path = set()
        shutil.which = lambda name, *a, **k: ("/bin/" + name) if name in self.on_path else None

    def tearDown(self):
        shutil.which = self.old_which
        os.environ.clear()
        os.environ.update(self.old_env)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def touch(self, *parts):
        path = os.path.join(*parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").close()
        return path


class TestNothingInstalled(Env):
    def test_finds_nothing_and_says_so(self):
        self.assertIsNone(sl.autodetect_wrap())


class TestCcstatusline(Env):
    def test_pinned_binary_wins_over_npx(self):
        self.on_path = {"ccstatusline", "npx"}
        self.touch(self.xdg, "ccstatusline", "settings.json")
        self.assertEqual(sl.autodetect_wrap(), ["/bin/ccstatusline"])

    def test_falls_back_to_npx_when_configured(self):
        self.on_path = {"npx"}
        self.touch(self.xdg, "ccstatusline", "settings.json")
        self.assertEqual(sl.autodetect_wrap(), ["/bin/npx", "-y", "ccstatusline@latest"])

    def test_npx_alone_is_not_enough(self):
        # npx가 있다고 안 쓰는 패키지를 매 턴 끌어오면 안 된다.
        self.on_path = {"npx"}
        self.assertIsNone(sl.autodetect_wrap())


class TestPowerline(Env):
    def test_claude_dir_config_is_the_signal(self):
        self.on_path = {"npx"}
        self.touch(self.claude, "claude-powerline.json")
        self.assertEqual(sl.autodetect_wrap(),
                         ["/bin/npx", "-y", "@owloops/claude-powerline@latest"])

    def test_xdg_config_counts_too(self):
        self.on_path = {"npx"}
        self.touch(self.xdg, "claude-powerline", "config.json")
        self.assertEqual(sl.autodetect_wrap(),
                         ["/bin/npx", "-y", "@owloops/claude-powerline@latest"])

    def test_without_npx_it_is_skipped(self):
        self.touch(self.claude, "claude-powerline.json")
        self.assertIsNone(sl.autodetect_wrap())


class TestCcusage(Env):
    def test_binary_gets_the_statusline_subcommand(self):
        self.on_path = {"ccusage"}
        self.assertEqual(sl.autodetect_wrap(), ["/bin/ccusage", "statusline"])

    def test_it_loses_to_ccstatusline(self):
        # ccusage는 다른 이유로 깔려 있기도 해서 신호가 제일 약하다. 맨 뒤다.
        self.on_path = {"ccusage", "ccstatusline"}
        self.assertEqual(sl.autodetect_wrap(), ["/bin/ccstatusline"])


class TestHud(Env):
    def _install(self):
        self.touch(self.claude, "plugins", "cache", "claude-hud",
                   "claude-hud", "0.1.0", "dist", "index.js")

    def test_still_found_the_way_it_always_was(self):
        self.on_path = {"node"}
        self._install()
        found = sl.autodetect_wrap()
        self.assertEqual(found[0], "/bin/node")
        self.assertTrue(found[1].endswith(os.path.join("dist", "index.js")))

    def test_it_goes_first(self):
        # 0.2.0부터 hud를 물고 있던 사람의 화면이 판올림으로 바뀌면 안 된다.
        self.on_path = {"node", "ccstatusline", "ccusage", "npx"}
        self._install()
        self.assertEqual(sl.autodetect_wrap()[0], "/bin/node")


if __name__ == "__main__":
    unittest.main()

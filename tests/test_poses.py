import importlib.util, os, unittest

spec = importlib.util.spec_from_file_location(
    "statusline_clawd",
    os.path.join(os.path.dirname(__file__), "..", "scripts", "statusline-clawd.py"))
sl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sl)

ORIGINAL = {"default", "look-left", "look-right", "arms-up"}


class TestPoses(unittest.TestCase):
    """앤트로픽 원본에 있는 넷 말고는 그리지 않는다. 표정을 더 그리면 짝퉁이 된다."""

    def test_only_the_four_original_poses_exist(self):
        self.assertEqual(set(sl.POSES), ORIGINAL)
        self.assertEqual(set(sl.FALLBACK), ORIGINAL)
        self.assertEqual(set(sl.AIRBORNE), ORIGINAL)
        self.assertTrue(set(sl.AIRBORNE.values()) <= ORIGINAL)

    def test_no_pose_draws_a_mouth(self):
        # 몸통 줄은 원본에서 늘 꽉 차 있다. 사분면을 비우면 그게 입이 된다.
        for name, (_arms, _face, body) in sl.POSES.items():
            self.assertEqual(set(body), {"█"}, name)

    def test_every_band_only_ever_picks_an_original_pose(self):
        for _label, weights in sl.BANDS:
            for name, _w in weights:
                self.assertIn(name, ORIGINAL, name)

    def test_headroom_bands_pick_poses_that_exist(self):
        cfg = {"thresholds": {"wary": 50, "alarmed": 25, "panic": 10}, "jump": False}
        for pct in (95, 60, 40, 20, 5, 0):
            payload = {"context_window": {"remaining_percentage": pct}}
            for tick in range(12):
                pose, offset, _poof = sl.pick_pose(payload, cfg, tick)
                self.assertIn(pose, ORIGINAL, (pct, tick))
                self.assertIn(offset, (0, 1))

    def test_the_lowest_band_alternates_the_arms(self):
        cfg = {"thresholds": {"wary": 50, "alarmed": 25, "panic": 10}, "jump": False}
        payload = {"context_window": {"remaining_percentage": 3}}
        seen = {sl.pick_pose(payload, cfg, t)[0] for t in range(6)}
        self.assertEqual(seen, {"arms-up", "default"})

    def test_a_calm_session_mostly_stands_still(self):
        cfg = {"thresholds": {"wary": 50, "alarmed": 25, "panic": 10}, "jump": False}
        payload = {"context_window": {"remaining_percentage": 90}}
        poses = [sl.pick_pose(payload, cfg, t)[0] for t in range(200)]
        self.assertGreater(poses.count("default"), 90)


if __name__ == "__main__":
    unittest.main()

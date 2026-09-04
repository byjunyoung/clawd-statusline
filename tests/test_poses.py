import importlib.util, os, unittest

spec = importlib.util.spec_from_file_location(
    "statusline_clawd",
    os.path.join(os.path.dirname(__file__), "..", "scripts", "statusline-clawd.py"))
sl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sl)

ORIGINAL = {"default", "look-left", "look-right", "arms-up"}

# 클로드 코드 2.1.260 chunk-j9b3a0wh.js에서 그대로 옮긴 것. 원본 애니메이션 다섯(jump·look·
# idle·spin·celebrate·skip)을 통틀어 실제로 나오는 (포즈, 세로오프셋) 짝은 이 다섯뿐이다.
# offset 1은 default에만 붙는다 - arms-up을 내린 프레임 같은 건 원본에 없다.
OFFICIAL_FRAMES = {("default", 0), ("look-left", 0), ("look-right", 0),
                   ("arms-up", 0), ("default", 1)}


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


class TestOfficialFrames(unittest.TestCase):
    """원본에 없는 (포즈, 오프셋) 짝은 내지 않는다.

    포즈 넷을 지키는 것만으로는 모자란다. 넷 중 하나를 원본이 안 쓰는 자세로 놓으면
    그것도 새로 그린 것이다. 실제로 한 번 그랬다 - 놀랄 때 arms-up을 한 줄 내렸었다.
    """

    def frames(self, payload, cfg):
        return {sl.pick_pose(payload, cfg, t)[:2] for t in range(60)}

    def test_every_headroom_band_stays_official(self):
        cfg = dict(sl.DEFAULTS)
        for pct in (95, 60, 40, 20, 5, 0):
            got = self.frames({"context_window": {"remaining_percentage": pct}}, cfg)
            self.assertTrue(got <= OFFICIAL_FRAMES, (pct, got - OFFICIAL_FRAMES))

    def test_the_idle_cycle_is_the_one_the_original_plays(self):
        self.assertEqual(sl.IDLE_CYCLE,
                         ["default"] * 12 + ["look-right"] * 5 + ["look-left"] * 5)
        self.assertTrue(set(sl.IDLE_CYCLE) <= ORIGINAL)

    def test_dust_only_ever_falls_while_crouching(self):
        # 원본은 offset이 0보다 클 때만 먼지를 그린다. 웅크릴 때 잘려나간 몸통 양 끝
        # 한 칸을 그 두 글자가 메우기 때문이다.
        cfg = dict(sl.DEFAULTS)
        for pct in (95, 40, 5):
            for tick in range(60):
                pose, offset, poof = sl.pick_pose(
                    {"context_window": {"remaining_percentage": pct}}, cfg, tick)
                if poof is not None:
                    self.assertEqual(offset, 1, (pose, tick))
                    self.assertIn(poof, sl.POOF)


if __name__ == "__main__":
    unittest.main()

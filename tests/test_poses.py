import importlib.util, os, unittest

spec = importlib.util.spec_from_file_location(
    "statusline_clawd",
    os.path.join(os.path.dirname(__file__), "..", "scripts", "statusline-clawd.py"))
sl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sl)

ORIGINAL = {"default", "look-left", "look-right", "arms-up"}

# 클로드 코드 2.1.311에서 그대로 옮긴 것. 원본은 눈·팔·발을 따로 두고 조합한다.
# 아래는 원본의 동작 열다섯(jump·look·celebrate·skip·spin·peekaboo·drop·waddle·peek·wink·
# boop·tap·sneeze·turn·coin-hop) 가운데 여기서 쓰는 것들이 실제로 내는 조합이다.
OFFICIAL_COMBOS = {
    ("open", "down", "both"), ("left", "down", "both"), ("right", "down", "both"),
    ("open", "up", "both"),                                  # 이름 붙은 넷
    ("closed", "down", "both"),                              # 깜빡임, boop, sneeze
    ("wink", "down", "both"),                                # wink
    ("closed", "up", "both"),                                # sneeze
    ("open", "down", "left"), ("open", "down", "right"),     # tap
}
# 원본이 실제로 내는 (포즈, 세로오프셋) 짝. offset 1은 팔을 내린 채 눈을 뜨거나 감은
# 자세에만 붙는다 - arms-up을 내린 프레임 같은 건 원본에 없다.
OFFICIAL_FRAMES = ({(name, 0) for name in ORIGINAL | {"closed", "wink", "closed-arms-up",
                                                      "step-left", "step-right"}}
                   | {("default", 1), ("closed", 1)})

# 원본 동작을 60ms 장면 그대로 편 것. 여기 틱 판은 이 순서를 건너뛸 수는 있어도 바꿀 수는 없다.
OFFICIAL_SEQUENCES = {
    "WINK": ["wink"] * 5 + ["default"],
    "TAP": (["step-left"] * 2 + ["step-right"] * 2) * 2 + ["step-left", "step-right"]
           + ["arms-up"] * 3 + ["default"],
    "SNEEZE": ["closed-arms-up"] * 4 + ["closed"] * 4 + ["default"] * 2 + ["closed", "default"],
}


def in_order(short, full):
    """short가 full의 순서를 지키며 골라낸 것인가."""
    rest = iter(full)
    return all(any(item == other for other in rest) for item in short)


class TestPoses(unittest.TestCase):
    """앤트로픽 원본에 있는 부품과 조합 말고는 그리지 않는다. 표정을 더 그리면 짝퉁이 된다."""

    def test_the_four_named_poses_are_still_there(self):
        self.assertTrue(ORIGINAL <= set(sl.POSES))
        self.assertEqual(set(sl.AIRBORNE), ORIGINAL)
        self.assertTrue(set(sl.AIRBORNE.values()) <= ORIGINAL)

    def test_every_pose_is_a_combination_the_original_uses(self):
        self.assertEqual(set(sl.POSES.values()), OFFICIAL_COMBOS)
        for eyes, arms, feet in sl.POSES.values():
            self.assertIn(eyes, sl.EYES)
            self.assertIn(eyes, sl.FALLBACK_EYES)
            self.assertIn(arms, sl.ARMS)
            self.assertIn(feet, sl.FEET)

    def test_no_pose_draws_a_mouth(self):
        # 몸통 줄은 원본에서 늘 꽉 차 있다. 사분면을 비우면 그게 입이 된다.
        self.assertEqual(set(sl.BODY), {"█"})

    def test_every_frame_is_three_rows_of_the_same_width(self):
        import re
        for term in ("iTerm.app", "Apple_Terminal"):
            os.environ["TERM_PROGRAM"] = term
            try:
                for pose in sl.POSES:
                    for offset, poof in ((0, None), (1, "~")):
                        rows = [re.sub(r"\x1b\[[0-9;]*m", "", r) for r in sl.render(pose, offset, poof)]
                        self.assertEqual([len(r) for r in rows], [sl.WIDTH] * 3, (term, pose, offset))
            finally:
                del os.environ["TERM_PROGRAM"]

    def test_every_band_only_ever_picks_an_original_pose(self):
        for _label, weights in sl.BANDS:
            for name, _w in weights:
                self.assertIn(name, ORIGINAL, name)

    def test_the_tick_sequences_follow_the_original_order(self):
        for name, official in OFFICIAL_SEQUENCES.items():
            ours = getattr(sl, name)
            self.assertTrue(in_order([pose for pose, _o, _p in ours], official), name)
            for pose, offset, poof in ours:
                self.assertIn((pose, offset), OFFICIAL_FRAMES, (name, pose))
                if poof is not None:
                    self.assertEqual(offset, 1, name)

    def test_headroom_bands_pick_poses_that_exist(self):
        cfg = {"thresholds": {"wary": 50, "alarmed": 25, "panic": 10}, "jump": False}
        for pct in (95, 60, 40, 20, 5, 0):
            payload = {"context_window": {"remaining_percentage": pct}}
            for tick in range(12):
                pose, offset, _poof = sl.pick_pose(payload, cfg, tick)
                self.assertIn(pose, ORIGINAL | {"closed"}, (pct, tick))
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

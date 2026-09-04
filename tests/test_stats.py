import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import stats, scan


class TestInterp(unittest.TestCase):
    def test_interpolates_between_anchors(self):
        a = [(0, 0), (10, 50), (20, 100)]
        self.assertEqual(stats.interp(a, 0), 0)
        self.assertEqual(stats.interp(a, 5), 25)
        self.assertEqual(stats.interp(a, 20), 100)

    def test_clamps_outside_the_anchor_range(self):
        a = [(0, 0), (10, 50)]
        self.assertEqual(stats.interp(a, -5), 0)
        self.assertEqual(stats.interp(a, 1000), 50)


class TestCompute(unittest.TestCase):
    def test_empty_history_gives_all_zeros(self):
        s = stats.compute(scan.new_raw())
        self.assertEqual(set(s), {"appetite", "reach", "stamina", "pack", "nocturne"})
        self.assertTrue(all(v == 0 for v in s.values()))

    def test_all_stats_stay_inside_zero_to_hundred(self):
        raw = scan.new_raw()
        raw.update(food=10 ** 12, calls=10 ** 6, compacts=10 ** 5, sidechain=10 ** 6,
                   outer_tools=10 ** 6, total_tools=10 ** 6, night_calls=10 ** 6, day_calls=0)
        raw["days"] = {"2026-09-%02d" % d: 10 ** 9 for d in range(1, 10)}
        raw["turns_by_session"] = {"s%d" % i: 5000 for i in range(10)}
        for k, v in stats.compute(raw).items():
            self.assertGreaterEqual(v, 0, k)
            self.assertLessEqual(v, 100, k)

    def test_reach_reflects_the_outer_tool_share(self):
        raw = scan.new_raw()
        raw.update(outer_tools=60, total_tools=100)
        self.assertGreater(stats.compute(raw)["reach"], 70)


class TestTitle(unittest.TestCase):
    def test_no_title_below_ninety(self):
        self.assertIsNone(stats.title({"appetite": 89, "reach": 10, "stamina": 10,
                                       "pack": 10, "nocturne": 10}))

    def test_highest_stat_over_ninety_wins(self):
        self.assertEqual(stats.title({"appetite": 95, "reach": 92, "stamina": 10,
                                      "pack": 10, "nocturne": 10}), "GLUTTON")


if __name__ == "__main__":
    unittest.main()

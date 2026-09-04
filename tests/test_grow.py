import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import grow


class TestLevel(unittest.TestCase):
    def test_curve_is_the_cube_of_the_level(self):
        self.assertEqual(grow.food_for_level(1, 1.0), 5000)
        self.assertEqual(grow.food_for_level(20, 1.0), 40_000_000)
        self.assertEqual(grow.food_for_level(45, 1.0), 455_625_000)

    def test_level_for_is_the_inverse(self):
        for n in (1, 5, 20, 45, 60, 99):
            self.assertEqual(grow.level_for(grow.food_for_level(n, 1.0), 1.0), n)

    def test_level_never_leaves_one_to_ninetynine(self):
        self.assertEqual(grow.level_for(0, 1.0), 1)
        self.assertEqual(grow.level_for(10 ** 15, 1.0), 99)

    def test_pro_reaches_a_level_on_less_food(self):
        food = grow.food_for_level(30, grow.plan_factor("claude_pro"))
        self.assertLess(food, grow.food_for_level(30, grow.plan_factor("default_claude_max_5x")))

    def test_unknown_plan_falls_back_to_one(self):
        self.assertEqual(grow.plan_factor(None), 1.0)
        self.assertEqual(grow.plan_factor("something_else"), 1.0)




if __name__ == "__main__":
    unittest.main()

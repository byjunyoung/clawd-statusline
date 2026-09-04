import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import closet


class TestFold(unittest.TestCase):
    def test_folds_two_pixel_rows_into_one_cell_row(self):
        self.assertEqual(closet.fold("##\n##", 1), "█")
        self.assertEqual(closet.fold("#.\n..", 1), "▘")

    def test_every_row_is_exactly_the_sprite_width(self):
        for name in closet.HATS:
            self.assertEqual(len(closet.hat_row(name)), closet.WIDTH, name)


class TestUnlocks(unittest.TestCase):
    def test_a_new_ledger_can_only_wear_nothing(self):
        open_now = closet.unlocked({"level": 1})
        self.assertEqual(open_now["hat"], ["none"])
        self.assertEqual(open_now["friend"], ["none"])

    def test_levels_open_things_up(self):
        self.assertIn("cap", closet.unlocked({"level": 5})["hat"])
        self.assertNotIn("crown", closet.unlocked({"level": 5})["hat"])
        self.assertIn("crown", closet.unlocked({"level": 50})["hat"])

    def test_friends_never_come_from_levels(self):
        # 아무리 레벨이 높아도 칭호가 없으면 친구는 안 붙는다.
        self.assertEqual(closet.unlocked({"level": 99})["friend"], ["none"])
        self.assertIn("bat", closet.unlocked({"level": 1, "title": "OWL"})["friend"])

    def test_wearing_something_not_yet_unlocked_falls_back_to_none(self):
        state = {"level": 1, "worn": {"hat": "crown"}}
        self.assertEqual(closet.worn(state, "hat"), "none")

    def test_next_unlock_points_at_the_nearest_level(self):
        slot, name, need = closet.next_unlock({"level": 1})
        self.assertEqual(need, 5)
        self.assertEqual((slot, name), ("hat", "cap"))

    def test_nothing_is_left_to_unlock_at_the_ceiling(self):
        self.assertIsNone(closet.next_unlock({"level": 99}))


if __name__ == "__main__":
    unittest.main()


class TestColour(unittest.TestCase):
    """악세사리가 몸통색과 같으면 걸친 게 아니라 혹으로 보인다."""

    def test_every_wearable_declares_a_colour(self):
        for table in (closet.HATS, closet.FRIENDS):
            for name, item in table.items():
                if not item[1]:
                    continue
                self.assertIsNotNone(item[2], name)
                self.assertTrue(item[3].startswith("\033["), name)

    def test_no_hat_reuses_the_body_colour(self):
        body = (215, 119, 87)
        for name, item in closet.HATS.items():
            if item[1]:
                self.assertNotEqual(item[2], body, name)

    def test_colour_falls_back_when_the_terminal_is_not_truecolor(self):
        rich = closet.color_of(closet.HATS, "crown", True)
        plain = closet.color_of(closet.HATS, "crown", False)
        self.assertIn("38;2;", rich)
        self.assertNotIn("38;2;", plain)
        self.assertTrue(plain.startswith("\033["))

    def test_wearing_nothing_asks_for_no_colour(self):
        self.assertEqual(closet.color_of(closet.HATS, "none", True), "")

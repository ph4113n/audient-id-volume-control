import unittest

from volume_curve import MUTE_DB, db_to_percent, percent_to_db


class VolumeCurveTests(unittest.TestCase):
    def test_zero_percent_is_muted(self):
        self.assertEqual(percent_to_db(0, -24.0), MUTE_DB)

    def test_full_scale_equals_ceiling(self):
        self.assertEqual(percent_to_db(100, -24.0), -24.0)

    def test_curve_round_trip(self):
        ceiling = -24.31
        for percent in (1, 5, 25, 50, 75, 100):
            self.assertEqual(db_to_percent(percent_to_db(percent, ceiling), ceiling), percent)

    def test_output_never_exceeds_ceiling(self):
        self.assertLessEqual(percent_to_db(150, -30.0), -30.0)


if __name__ == "__main__":
    unittest.main()

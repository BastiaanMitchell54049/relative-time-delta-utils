import calendar
import unittest
from datetime import datetime, timezone

from relative_time_delta_utils import (
    RelativeTimeDelta,
    RelativeTimeError,
    Weekday,
    Month,
)


class TestOrdinalInMonth(unittest.TestCase):
    def test_first_monday_of_january(self):
        rtd = RelativeTimeDelta("first Monday of January")
        base = datetime(2024, 6, 15, 10, 30)
        self.assertEqual(rtd.apply(base), datetime(2024, 1, 1, 10, 30))

    def test_third_wednesday_of_march(self):
        rtd = RelativeTimeDelta("third Wednesday of March")
        base = datetime(2024, 6, 15, 8, 0)
        self.assertEqual(rtd.apply(base), datetime(2024, 3, 20, 8, 0))

    def test_last_day_of_february_non_leap(self):
        rtd = RelativeTimeDelta("last day of February")
        base = datetime(2023, 6, 15, 0, 0)
        self.assertEqual(rtd.apply(base), datetime(2023, 2, 28, 0, 0))

    def test_last_day_of_february_leap(self):
        rtd = RelativeTimeDelta("last day of February")
        base = datetime(2024, 6, 15, 0, 0)
        self.assertEqual(rtd.apply(base), datetime(2024, 2, 29, 0, 0))

    def test_fifth_monday_of_march_invalid(self):
        rtd = RelativeTimeDelta("fifth Monday of March")
        base = datetime(2024, 6, 15, 0, 0)
        with self.assertRaises(RelativeTimeError):
            rtd.apply(base)


class TestOrdinalInYear(unittest.TestCase):
    def test_third_wednesday_of_year(self):
        rtd = RelativeTimeDelta("third Wednesday")
        base = datetime(2024, 6, 15, 12, 0)
        # 2024-01-17 is the 3rd Wednesday
        self.assertEqual(rtd.apply(base), datetime(2024, 1, 17, 12, 0))


class TestProximityWeekday(unittest.TestCase):
    def test_next_friday(self):
        rtd = RelativeTimeDelta("next Friday")
        base = datetime(2024, 6, 15, 14, 0)  # Saturday
        self.assertEqual(rtd.apply(base), datetime(2024, 6, 21, 14, 0))

    def test_last_monday_on_monday(self):
        rtd = RelativeTimeDelta("last Monday")
        base = datetime(2024, 6, 17, 9, 0)  # Monday
        self.assertEqual(rtd.apply(base), datetime(2024, 6, 10, 9, 0))

    def test_next_monday_on_monday(self):
        rtd = RelativeTimeDelta("next Monday")
        base = datetime(2024, 6, 17, 9, 0)  # Monday
        self.assertEqual(rtd.apply(base), datetime(2024, 6, 24, 9, 0))

    def test_previous_tuesday(self):
        rtd = RelativeTimeDelta("previous Tuesday")
        base = datetime(2024, 6, 19, 0, 0)  # Wednesday
        self.assertEqual(rtd.apply(base), datetime(2024, 6, 13, 0, 0))


class TestEdgeCases(unittest.TestCase):
    def test_empty_phrase(self):
        with self.assertRaises(RelativeTimeError):
            RelativeTimeDelta("")

    def test_garbage_phrase(self):
        with self.assertRaises(RelativeTimeError):
            RelativeTimeDelta("some random nonsense")

    def test_unknown_month(self):
        with self.assertRaises(RelativeTimeError):
            RelativeTimeDelta("first Monday of Smarch")

    def test_unknown_weekday(self):
        with self.assertRaises(RelativeTimeError):
            RelativeTimeDelta("first Frobnitz of January")

    def test_numeric_ordinal(self):
        rtd = RelativeTimeDelta("2nd Monday of January")
        base = datetime(2024, 6, 15, 0, 0)
        self.assertEqual(rtd.apply(base), datetime(2024, 1, 8, 0, 0))

    def test_preserves_timezone(self):
        rtd = RelativeTimeDelta("next Friday")
        tz = timezone.utc
        base = datetime(2024, 6, 15, 14, 0, tzinfo=tz)  # Saturday
        result = rtd.apply(base)
        self.assertEqual(result, datetime(2024, 6, 21, 14, 0, tzinfo=tz))
        self.assertIs(result.tzinfo, tz)

    def test_preserves_time(self):
        rtd = RelativeTimeDelta("next Friday")
        base = datetime(2024, 6, 15, 14, 37, 42)
        result = rtd.apply(base)
        self.assertEqual(result.time(), base.time())


class TestExports(unittest.TestCase):
    def test_weekday_and_month_exported(self):
        self.assertTrue(hasattr(Weekday(0, "Monday"), "name"))
        self.assertTrue(hasattr(Month(1, "January"), "name"))


if __name__ == "__main__":
    unittest.main()

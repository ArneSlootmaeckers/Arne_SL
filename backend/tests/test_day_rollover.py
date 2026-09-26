from datetime import date, datetime, timezone

import pytest

from app.domain.calendar import local_today
from app.domain.status import Status, effective_status


class TestEffectiveStatus:
    def test_no_stored_status_is_not_yet_jumped(self):
        assert effective_status(None, None, date(2026, 6, 1)) is Status.NOG_NIET_GESPRONGEN

    def test_stored_status_from_today_is_kept(self):
        today = date(2026, 6, 1)
        for status in Status:
            assert effective_status(status, today, today) is status

    @pytest.mark.parametrize(
        "stored_status",
        [Status.HERKANSING, Status.GESLAAGD, Status.NIET_GESLAAGD],
    )
    def test_stored_status_from_yesterday_resets_to_not_yet_jumped(self, stored_status):
        yesterday = date(2026, 6, 1)
        today = date(2026, 6, 2)
        assert effective_status(stored_status, yesterday, today) is Status.NOG_NIET_GESPRONGEN

    def test_stored_status_from_a_previous_day_long_ago_also_resets(self):
        assert (
            effective_status(Status.GESLAAGD, date(2025, 1, 1), date(2026, 6, 2))
            is Status.NOG_NIET_GESPRONGEN
        )


class TestBrusselsDayBoundaryAcrossDST:
    """A fixed UTC offset would misplace visitors near local midnight in summer (CEST,
    UTC+2) vs winter (CET, UTC+1). These pin down both cases against the real
    Europe/Brussels rules using zoneinfo, and the actual 2026 DST transition dates
    (spring forward 2026-03-29, fall back 2026-10-25).
    """

    def test_winter_local_midnight_boundary_cet_utc_plus_1(self):
        before_midnight = datetime(2026, 1, 14, 22, 30, tzinfo=timezone.utc)
        assert local_today(before_midnight) == date(2026, 1, 14)

        after_midnight = datetime(2026, 1, 14, 23, 30, tzinfo=timezone.utc)
        assert local_today(after_midnight) == date(2026, 1, 15)

    def test_summer_local_midnight_boundary_cest_utc_plus_2(self):
        before_midnight = datetime(2026, 7, 14, 21, 30, tzinfo=timezone.utc)
        assert local_today(before_midnight) == date(2026, 7, 14)

        # An hour earlier in UTC than the winter case, because CEST is UTC+2.
        after_midnight = datetime(2026, 7, 14, 22, 30, tzinfo=timezone.utc)
        assert local_today(after_midnight) == date(2026, 7, 15)

    def test_naive_fixed_offset_would_misdate_the_summer_case(self):
        # The same UTC instant that is already "tomorrow" in Brussels (CEST) is still
        # "today" under plain UTC-date truncation, proving a hardcoded offset breaks here.
        instant = datetime(2026, 7, 14, 22, 30, tzinfo=timezone.utc)
        assert instant.date() == date(2026, 7, 14)
        assert local_today(instant) == date(2026, 7, 15)

    def test_spring_forward_transition_2026_03_29(self):
        # Clocks jump from 02:00 CET to 03:00 CEST at 01:00 UTC, well after local
        # midnight, so the calendar date must stay March 29 on both sides.
        just_before = datetime(2026, 3, 29, 0, 59, tzinfo=timezone.utc)
        just_after = datetime(2026, 3, 29, 1, 1, tzinfo=timezone.utc)
        assert local_today(just_before) == date(2026, 3, 29)
        assert local_today(just_after) == date(2026, 3, 29)

    def test_fall_back_transition_2026_10_25(self):
        # Clocks fall from 03:00 CEST to 02:00 CET at 01:00 UTC (local 02:00-03:00
        # occurs twice). The calendar date must stay October 25 throughout.
        just_before = datetime(2026, 10, 25, 0, 59, tzinfo=timezone.utc)
        just_after = datetime(2026, 10, 25, 1, 1, tzinfo=timezone.utc)
        assert local_today(just_before) == date(2026, 10, 25)
        assert local_today(just_after) == date(2026, 10, 25)

    def test_local_today_requires_timezone_aware_input(self):
        with pytest.raises(ValueError):
            local_today(datetime(2026, 1, 1, 12, 0))

import pytest

from app.domain.status import (
    Status,
    Verdict,
    VerdictNotAllowedError,
    apply_verdict,
    can_access_ski_jump,
    can_attempt_test_jump,
    is_valid_manual_status,
)


class TestTransitionTable:
    """Every transition from section 2 of the assignment, verified exactly."""

    def test_not_yet_jumped_green_becomes_geslaagd(self):
        result = apply_verdict(Status.NOG_NIET_GESPRONGEN, Verdict.GROEN)
        assert result.new_status is Status.GESLAAGD
        assert result.status_changed is True
        assert result.is_practice_jump is False

    def test_not_yet_jumped_red_becomes_herkansing(self):
        result = apply_verdict(Status.NOG_NIET_GESPRONGEN, Verdict.ROOD)
        assert result.new_status is Status.HERKANSING
        assert result.status_changed is True
        assert result.is_practice_jump is False

    def test_herkansing_green_becomes_geslaagd(self):
        result = apply_verdict(Status.HERKANSING, Verdict.GROEN)
        assert result.new_status is Status.GESLAAGD
        assert result.status_changed is True
        assert result.is_practice_jump is False

    def test_herkansing_red_becomes_niet_geslaagd(self):
        result = apply_verdict(Status.HERKANSING, Verdict.ROOD)
        assert result.new_status is Status.NIET_GESLAAGD
        assert result.status_changed is True
        assert result.is_practice_jump is False

    @pytest.mark.parametrize("verdict", [Verdict.GROEN, Verdict.ROOD])
    def test_geslaagd_stays_geslaagd_as_practice_jump(self, verdict):
        result = apply_verdict(Status.GESLAAGD, verdict)
        assert result.new_status is Status.GESLAAGD
        assert result.status_changed is False
        assert result.is_practice_jump is True

    @pytest.mark.parametrize("verdict", [Verdict.GROEN, Verdict.ROOD])
    def test_niet_geslaagd_never_accepts_a_verdict(self, verdict):
        with pytest.raises(VerdictNotAllowedError):
            apply_verdict(Status.NIET_GESLAAGD, verdict)


class TestLocationAccess:
    @pytest.mark.parametrize(
        "status,expected",
        [
            (Status.NOG_NIET_GESPRONGEN, True),
            (Status.HERKANSING, True),
            (Status.GESLAAGD, True),
            (Status.NIET_GESLAAGD, False),
        ],
    )
    def test_test_jump_access(self, status, expected):
        assert can_attempt_test_jump(status) is expected

    @pytest.mark.parametrize(
        "status,expected",
        [
            (Status.NOG_NIET_GESPRONGEN, False),
            (Status.HERKANSING, False),
            (Status.GESLAAGD, True),
            (Status.NIET_GESLAAGD, False),
        ],
    )
    def test_ski_jump_access_requires_geslaagd(self, status, expected):
        assert can_access_ski_jump(status) is expected


class TestManualStatusValidation:
    @pytest.mark.parametrize(
        "status",
        [Status.NOG_NIET_GESPRONGEN, Status.HERKANSING, Status.GESLAAGD, Status.NIET_GESLAAGD],
    )
    def test_all_four_statuses_are_valid(self, status):
        assert is_valid_manual_status(status.value) is True

    @pytest.mark.parametrize("value", ["", "GESLAAGD ", "geslaagd", "ONBEKEND", "NONE"])
    def test_invalid_values_are_rejected(self, value):
        assert is_valid_manual_status(value) is False

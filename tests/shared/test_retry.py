from facebook_extractor.shared.retry import backoff_seconds


def test_exponential_backoff_doubles_each_attempt() -> None:
    assert backoff_seconds(1, None) == 1.0
    assert backoff_seconds(2, None) == 2.0
    assert backoff_seconds(3, None) == 4.0


def test_retry_after_overrides_when_larger() -> None:
    assert backoff_seconds(1, "10") == 10.0


def test_computed_backoff_wins_when_retry_after_is_smaller() -> None:
    assert backoff_seconds(3, "1") == 4.0


def test_invalid_retry_after_falls_back_to_computed_backoff() -> None:
    assert backoff_seconds(2, "not-a-number") == 2.0

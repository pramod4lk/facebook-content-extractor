import pytest

from facebook_extractor.shared.url_parser import InvalidFacebookUrlError, parse_page_url


@pytest.mark.parametrize(
    "raw_url",
    [
        "https://www.facebook.com/examplepage",
        "https://facebook.com/examplepage",
        "https://www.facebook.com/examplepage/",
        "https://m.facebook.com/examplepage",
        "http://www.facebook.com/examplepage",
    ],
)
def test_normalizes_known_valid_shapes(raw_url: str) -> None:
    result = parse_page_url(raw_url)

    assert result.normalized_url == "https://www.facebook.com/examplepage"
    assert result.page_slug == "examplepage"


def test_ignores_tracking_query_parameters() -> None:
    result = parse_page_url("https://www.facebook.com/examplepage?ref=share&utm_source=x")

    assert result.normalized_url == "https://www.facebook.com/examplepage"


def test_supports_profile_php_id_urls() -> None:
    result = parse_page_url("https://www.facebook.com/profile.php?id=123456789")

    assert result.normalized_url == "https://www.facebook.com/profile.php?id=123456789"
    assert result.page_slug == "123456789"


def test_profile_php_without_id_is_invalid() -> None:
    with pytest.raises(InvalidFacebookUrlError):
        parse_page_url("https://www.facebook.com/profile.php")


@pytest.mark.parametrize(
    "raw_url",
    [
        "https://www.instagram.com/examplepage",
        "not-a-url",
        "https://www.facebook.com/",
        "ftp://www.facebook.com/examplepage",
        "",
    ],
)
def test_rejects_invalid_urls(raw_url: str) -> None:
    with pytest.raises(InvalidFacebookUrlError):
        parse_page_url(raw_url)

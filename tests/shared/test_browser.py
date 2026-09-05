import pytest

from facebook_extractor.shared.browser import is_media_response

# Note: is_media_response is the only part of shared/browser.py covered here. The
# Playwright orchestration itself (launching a browser, navigating, intercepting real
# responses) is deliberately not exercised by the automated suite — same policy as never
# making a real request to facebook.com, extended to never launching a real browser
# against it either. That path is validated by the project owner on their own machine.


@pytest.mark.parametrize(
    ("content_type", "url"),
    [
        ("video/mp4", "https://video-abc.fbcdn.net/v/t42/1.mp4"),
        ("image/jpeg", "https://scontent.fplu1-1.fna.fbcdn.net/v/t1/1.jpg"),
        ("video/mp4; charset=binary", "https://scontent.example.fbcdn.net/1.mp4"),
    ],
)
def test_recognizes_media_responses(content_type: str, url: str) -> None:
    assert is_media_response(content_type, url) is True


@pytest.mark.parametrize(
    ("content_type", "url"),
    [
        ("application/javascript", "https://static.xx.fbcdn.net/rsrc.php/x.js"),
        ("text/css", "https://static.xx.fbcdn.net/rsrc.php/x.css"),
        ("video/mp4", "https://not-facebook-cdn.example.com/1.mp4"),
        ("text/html", "https://scontent.example.fbcdn.net/page.html"),
    ],
)
def test_ignores_non_media_or_non_facebook_responses(content_type: str, url: str) -> None:
    assert is_media_response(content_type, url) is False

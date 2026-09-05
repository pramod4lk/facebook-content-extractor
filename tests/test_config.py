import pytest

from facebook_extractor.config import ConfigurationError, load_settings

REQUIRED_ENV = {
    "FACEBOOK_PAGE_URL": "https://www.facebook.com/examplepage",
}


def _set_env(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> None:
    env = {**REQUIRED_ENV, **overrides}
    for key, value in env.items():
        monkeypatch.setenv(key, value)


def test_loads_required_variables(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    _set_env(monkeypatch)

    settings = load_settings()

    assert settings.facebook_page_url == REQUIRED_ENV["FACEBOOK_PAGE_URL"]


def test_applies_defaults_for_optional_variables(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    _set_env(monkeypatch)

    settings = load_settings()

    assert str(settings.output_directory) == "downloads"
    assert settings.log_level == "INFO"


def test_missing_required_variable_raises_configuration_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FACEBOOK_PAGE_URL", raising=False)

    with pytest.raises(ConfigurationError) as exc_info:
        load_settings()

    assert "FACEBOOK_PAGE_URL is missing from .env" in str(exc_info.value)


def test_blank_required_variable_raises_configuration_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.chdir(tmp_path)
    _set_env(monkeypatch, FACEBOOK_PAGE_URL="   ")

    with pytest.raises(ConfigurationError) as exc_info:
        load_settings()

    assert "FACEBOOK_PAGE_URL is invalid" in str(exc_info.value)

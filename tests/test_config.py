import pytest

from facebook_extractor.config import ConfigurationError, load_settings

REQUIRED_ENV = {
    "FACEBOOK_PAGE_URL": "https://www.facebook.com/examplepage",
    "META_ACCESS_TOKEN": "test-token",
    "META_GRAPH_API_VERSION": "v25.0",
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
    assert settings.meta_access_token.get_secret_value() == "test-token"
    assert settings.meta_graph_api_version == "v25.0"


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
    monkeypatch.setenv("META_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("META_GRAPH_API_VERSION", "v25.0")

    with pytest.raises(ConfigurationError) as exc_info:
        load_settings()

    assert "FACEBOOK_PAGE_URL is missing from .env" in str(exc_info.value)


def test_blank_required_variable_raises_configuration_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.chdir(tmp_path)
    _set_env(monkeypatch, META_ACCESS_TOKEN="   ")

    with pytest.raises(ConfigurationError) as exc_info:
        load_settings()

    assert "META_ACCESS_TOKEN is invalid" in str(exc_info.value)


def test_secret_never_appears_in_repr_or_str(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    _set_env(monkeypatch, META_ACCESS_TOKEN="super-secret-value")

    settings = load_settings()

    assert "super-secret-value" not in repr(settings)
    assert "super-secret-value" not in str(settings)

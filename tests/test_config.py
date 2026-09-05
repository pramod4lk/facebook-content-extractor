import pytest

from facebook_extractor.config import ConfigurationError, load_settings


def test_applies_defaults_when_env_is_empty(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)

    settings = load_settings()

    assert str(settings.output_directory) == "downloads"
    assert settings.log_level == "INFO"


def test_reads_overrides_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OUTPUT_DIRECTORY", "/tmp/somewhere")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    settings = load_settings()

    assert str(settings.output_directory) == "/tmp/somewhere"
    assert settings.log_level == "DEBUG"


def test_blank_log_level_raises_configuration_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LOG_LEVEL", "   ")

    with pytest.raises(ConfigurationError):
        load_settings()

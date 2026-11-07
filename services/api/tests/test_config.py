import pytest

from app.core.config import Settings, assert_production_safe


def test_dev_defaults_allowed():
    assert_production_safe(Settings(app_env="development"))


def test_production_rejects_default_secrets():
    with pytest.raises(RuntimeError):
        assert_production_safe(Settings(app_env="production"))


def test_production_accepts_custom_secrets():
    assert_production_safe(
        Settings(app_env="production", jwt_secret="a" * 32, file_url_secret="b" * 32)
    )

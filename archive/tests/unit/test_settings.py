from trading_ai.config import settings


def test_settings_load():
    assert settings.db_host is not None
    assert settings.data_provider in ["yahoo", "polygon"]

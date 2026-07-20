from trading_ai.config import Settings, settings


def main() -> None:
    assert isinstance(settings, Settings)
    assert not isinstance(settings, type)

    database_url = settings.database_url
    assert database_url.startswith("postgresql://")
    assert settings.db_host in database_url
    assert str(settings.db_port) in database_url
    assert settings.db_name in database_url

    assert settings.ui_bind_host in {"127.0.0.1", "localhost", "::1"}
    assert settings.ui_local_admin_user_id

    from trading_ai.database.engine import engine

    assert str(engine.url) == database_url

    print("Configuration export and database URL assertions passed.")
    print(f"Settings type: {type(settings).__name__}")
    print(f"Database host: {settings.db_host}")
    print(f"Database name: {settings.db_name}")
    print(f"Local admin enabled: {settings.ui_local_admin_mode}")


if __name__ == "__main__":
    main()

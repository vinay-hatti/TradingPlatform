from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    polygon_api_key: str = "demo"

    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "trading_ai"
    db_user: str = "vinay.hatti"
    db_password: str = "postgres"

    ui_local_admin_mode: bool = False
    ui_bind_host: str = "127.0.0.1"
    ui_local_admin_user_id: str = "local-workstation-admin"
    ui_local_admin_display_name: str = "Local Workstation Administrator"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        user = quote_plus(self.db_user)
        password = quote_plus(self.db_password)
        return (
            f"postgresql://{user}:{password}@"
            f"{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = Settings()

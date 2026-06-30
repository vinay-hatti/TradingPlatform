from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    polygon_api_key: str = "demo"

    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "trading_ai"
    db_user: str = "vinay.hatti"
    db_password: str = "postgres"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.db_user}:"
            f"{self.db_password}@"
            f"{self.db_host}:"
            f"{self.db_port}/"
            f"{self.db_name}"
        )


settings = Settings()

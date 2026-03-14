from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_HERE = Path(__file__).parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Scraping
    hours_lookback: int = 24
    scraper_headless: bool = True

    # X credentials — used as fallback if no session file is present
    x_username: str | None = None
    x_email: str | None = None  # Used for identity challenge (email or phone)
    x_password: str | None = None

    # Session persistence path (override in production to point to a PVC, e.g. /data/x_session.json)
    session_storage_path: str = str(_HERE.parent / "x_session.json")


settings = Settings()

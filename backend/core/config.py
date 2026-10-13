from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
# BASE_DIR = Path(__file__).parent.parent.parent
SQLITE_DB_PATH = str(BASE_DIR / "db.sqlite3")


class RunSettings(BaseModel):
    host: str = "127.0.0.5"
    port: int = 8005


class DatabaseSettings(BaseModel):
    url: str = f"sqlite+aiosqlite:///{SQLITE_DB_PATH}"
    db_name: str | None = None
    db_user: str | None = None
    db_password: str | None = None
    echo: bool = False

    naming_convention: dict[str, str] = {
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_N_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            BASE_DIR / ".env",
            BASE_DIR / ".env.example"),
        case_sensitive=False,
        env_nested_delimiter="__",
        env_prefix="APP_CONFIG__",
    )

    run: RunSettings = RunSettings()
    db: DatabaseSettings = Field(default_factory=DatabaseSettings)


settings = Settings()

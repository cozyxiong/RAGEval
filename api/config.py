from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    eval_db_path: str = str(ROOT / "data" / "eval.db")
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    judge_model: str = "gpt-4.1-mini"


settings = Settings()

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


class Settings(BaseModel):
    llm_provider: str = "stub"  # "openai" | "stub"
    stt_provider: str = "stub"  # "openai" | "stub"
    openai_api_key: str | None = None
    app_secret: str = "dev-secret-change-me"


def get_settings() -> Settings:
    # Simple env mapping without pulling in pydantic-settings.
    import os

    return Settings(
        llm_provider=os.getenv("LLM_PROVIDER", "stub").strip().lower(),
        stt_provider=os.getenv("STT_PROVIDER", "stub").strip().lower(),
        openai_api_key=(os.getenv("OPENAI_API_KEY") or "").strip() or None,
        app_secret=os.getenv("APP_SECRET", "dev-secret-change-me"),
    )


@dataclass(frozen=True)
class Paths:
    root: Path

    @property
    def data_dir(self) -> Path:
        p = self.root / ".data"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def uploads_dir(self) -> Path:
        p = self.data_dir / "uploads"
        p.mkdir(parents=True, exist_ok=True)
        return p


def get_paths() -> Paths:
    return Paths(root=Path(__file__).resolve().parents[1])


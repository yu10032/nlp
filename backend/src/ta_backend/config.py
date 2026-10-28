import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Settings:
    database_url: str
    storage_dir: Path = PROJECT_ROOT / "data/runtime/uploads"
    generation_provider: str = "disabled"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    max_upload_bytes: int = 20 * 1024 * 1024

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(PROJECT_ROOT / ".env")
        default_db = (PROJECT_ROOT / "data/runtime/assistant.db").as_posix()
        url = os.getenv("TA_DATABASE_URL", f"sqlite:///{default_db}")
        if url.startswith("sqlite:///") and url != "sqlite:///:memory:":
            path = Path(url.removeprefix("sqlite:///"))
            if not path.is_absolute():
                url = f"sqlite:///{(PROJECT_ROOT / path).as_posix()}"
        return cls(
            database_url=url,
            storage_dir=PROJECT_ROOT / os.getenv("TA_STORAGE_DIR", "data/runtime/uploads"),
            generation_provider=os.getenv("TA_GENERATION_PROVIDER", "disabled"),
            llm_base_url=os.getenv("TA_LLM_BASE_URL", ""),
            llm_api_key=os.getenv("TA_LLM_API_KEY", ""),
            llm_model=os.getenv("TA_LLM_MODEL", ""),
        )

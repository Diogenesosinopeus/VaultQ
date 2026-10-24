from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    root: Path
    vault_name: str
    content_dirs: tuple[str, ...] = ("笔记", "wiki", "outputs")
    lm_studio_base_url: str = "http://127.0.0.1:1234/v1"
    lm_studio_chat_model: str = "nvidia/nemotron-3-nano-4b"
    lm_studio_embedding_model: str = "text-embedding-nomic-embed-text-v1.5"
    lm_studio_timeout: float = 90.0
    embedding_batch_size: int = 16

    @property
    def db_path(self) -> Path:
        return self.root / ".vaultq" / "index.db"


def get_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[2]
    root = Path(os.getenv("VAULTQ_ROOT", project_root)).expanduser().resolve()
    vault_name = os.getenv("VAULTQ_VAULT_NAME", root.name)
    return Settings(
        root=root,
        vault_name=vault_name,
        lm_studio_base_url=os.getenv("LM_STUDIO_BASE_URL", "http://127.0.0.1:1234/v1").rstrip("/"),
        lm_studio_chat_model=os.getenv("LM_STUDIO_CHAT_MODEL", "nvidia/nemotron-3-nano-4b"),
        lm_studio_embedding_model=os.getenv("LM_STUDIO_EMBEDDING_MODEL", "text-embedding-nomic-embed-text-v1.5"),
        lm_studio_timeout=float(os.getenv("LM_STUDIO_TIMEOUT", "90")),
    )


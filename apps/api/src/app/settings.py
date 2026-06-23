"""Host settings, read from the environment (.env in dev). Centralised here so the
rest of the app never reaches into os.environ directly.

Kept minimal in B0 — just enough to name the configuration surface. Validated
typing/strictness via pydantic-settings can come when the host actually wires the
DB and auth (B7/B10).
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://invoicing:invoicing@localhost:5432/invoicing"
    )
    jwt_secret: str = os.environ.get("JWT_SECRET", "dev-only-change-me")
    jwt_algorithm: str = os.environ.get("JWT_ALGORITHM", "HS256")
    jwt_expire_minutes: int = int(os.environ.get("JWT_EXPIRE_MINUTES", "60"))


settings = Settings()

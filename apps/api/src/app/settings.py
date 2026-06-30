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
    # >= 32 bytes: HS256 minimum, and PyJWT warns below it. Always override in deploy.
    jwt_secret: str = os.environ.get("JWT_SECRET", "dev-only-change-me-to-a-32-byte-random-string")
    jwt_algorithm: str = os.environ.get("JWT_ALGORITHM", "HS256")
    jwt_expire_minutes: int = int(os.environ.get("JWT_EXPIRE_MINUTES", "60"))

    # v1 single-user login (README §5). Plaintext compare for dev only — real
    # deployments override these and a future item moves to hashed credentials.
    auth_username: str = os.environ.get("AUTH_USERNAME", "admin")
    auth_password: str = os.environ.get("AUTH_PASSWORD", "admin")

    # Browser origins allowed to call the API (the Next.js app). Comma-separated;
    # the SPA calls the API cross-origin, so it must be on this list or CORS blocks it.
    cors_origins: str = os.environ.get("CORS_ORIGINS", "http://localhost:3000")


settings = Settings()

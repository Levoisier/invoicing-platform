"""FastAPI entry point. In B0 it is a bare app with a health check so the host is
runnable and testable end-to-end before any module is mounted. bootstrap.py (B10)
will turn this into discover → toposort → migrate → mount.
"""

from fastapi import FastAPI

app = FastAPI(title="Invoicing Platform API")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe. Also the seam the first integration test exercises so the
    host wiring is proven before modules exist."""
    return {"status": "ok"}

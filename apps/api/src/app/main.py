"""FastAPI entry point. The ASGI server (uvicorn) imports ``app.main:app``.

The app is now fully composed by ``bootstrap.create_app`` — discover plugins →
load+migrate modules → mount routers. Construction touches the database (it runs
migrations), so importing this module requires a reachable DB; that's expected for
a running host. Tests build their own app via ``create_app`` against a test DB
rather than importing this module.
"""

from app.bootstrap import create_app

app = create_app()

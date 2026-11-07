"""The engine service (spec 3 "Architecture", "Service rules" and "Endpoints").

The service is one FastAPI application made by ``lcsim.service.app.create_app`` from a
``ServiceConfig``; each area of the API is a router in its own module (``system``,
``engines``, ``templates``, ``projects``), and later areas add theirs the same way. Every
error a client sees is spec 3's error body with a spec 1 code (``lcsim.service.errors``).
``python -m lcsim.service`` binds ``127.0.0.1`` on a port the operating system chooses,
writes ``service.json`` and serves (``lcsim.service.main``).
"""

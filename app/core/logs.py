"""Logging setup shared by the API and the workers.

Every logger ends up at the root logger, so every handler on root sees every line: the
console handler added here and, when the process runs under `opentelemetry-instrument`
(see README, "Observability"), the OpenTelemetry handler that ships each record to
Elastic tagged with the trace id of the request or message that wrote it.
"""

import logging

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def setup_logging(level: int = logging.INFO) -> None:
    """Send INFO and above from every logger (app, uvicorn, workers) through root."""
    root = logging.getLogger()
    root.setLevel(level)
    # `type(...) is`, not isinstance: subclasses such as pytest's capture handler don't count.
    if not any(type(h) is logging.StreamHandler for h in root.handlers):
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter(LOG_FORMAT))
        root.addHandler(console)

    # uvicorn gives its loggers their own console handlers and turns propagation off, so
    # startup lines, the access log and app.main's warnings would never reach root.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True

    logging.getLogger("aiokafka").setLevel(logging.WARNING)

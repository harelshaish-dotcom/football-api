"""Run a Python command with OpenTelemetry, sending logs, traces and metrics to Elastic.

    python -m scripts.instrumented <service-name> <python args...>

Examples:
    python -m scripts.instrumented football-api -m uvicorn app.main:app --reload
    python -m scripts.instrumented football-stats-worker -m workers.stats
    python -m scripts.instrumented football-notifications-worker -m workers.notifications

It fills in the OTEL_* settings below (any you already set in the environment win) and
starts `opentelemetry-instrument python <args>`, which instruments FastAPI, SQLAlchemy,
MongoDB, Redis and Kafka before the app is imported. The data goes to the APM Server
from docker-compose.yml; look at it in Kibana: http://localhost:5601.
Without this wrapper (tests, CI, plain `uvicorn ...`) nothing is exported.
"""

import os
import subprocess
import sys
from pathlib import Path

DEFAULTS = {
    # 127.0.0.1, not localhost: on Windows "localhost" can add ~2s per connection (IPv6 first).
    "OTEL_EXPORTER_OTLP_ENDPOINT": "http://127.0.0.1:8200",  # apm-server in docker-compose
    "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
    "OTEL_TRACES_EXPORTER": "otlp",
    "OTEL_METRICS_EXPORTER": "otlp",
    "OTEL_LOGS_EXPORTER": "otlp",
    # Attach the OTel handler to the root logger (app.core.logs routes every log there).
    "OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED": "true",
    # Send metrics every 10s instead of 60s, so charts fill in quickly while developing.
    "OTEL_METRIC_EXPORT_INTERVAL": "10000",
    # Elastic recommends delta temporality for metrics sent to APM Server.
    "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE": "delta",
    # The load balancer polls /health constantly; tracing it only adds noise.
    "OTEL_PYTHON_FASTAPI_EXCLUDED_URLS": "health",
    "OTEL_RESOURCE_ATTRIBUTES": "deployment.environment.name=local",
}


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    service_name, python_args = sys.argv[1], sys.argv[2:]

    env = {**DEFAULTS, **os.environ, "OTEL_SERVICE_NAME": service_name}
    # Use the opentelemetry-instrument next to this interpreter (the venv's), not one on PATH.
    exe_suffix = ".exe" if os.name == "nt" else ""
    instrument = Path(sys.executable).parent / f"opentelemetry-instrument{exe_suffix}"
    cmd = [str(instrument), sys.executable, *python_args]
    try:
        return subprocess.call(cmd, env=env)
    except KeyboardInterrupt:  # Ctrl+C also reaches the child, which shuts down on its own
        return 130


if __name__ == "__main__":
    sys.exit(main())

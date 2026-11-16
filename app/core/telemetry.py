"""Custom metrics and the app's own tracer, exported to Elastic next to the automatic ones.

Uses only the OpenTelemetry API. When the process isn't started with
`opentelemetry-instrument` (tests, CI, a plain `uvicorn` run) there is no SDK
behind it and every `.add()` is a no-op, so call sites need no checks.
"""

from opentelemetry import metrics, trace

meter = metrics.get_meter("football-api")
tracer = trace.get_tracer("football-api")

match_events_created = meter.create_counter(
    "football.match_events.created",
    unit="{event}",
    description="Match events recorded through the API, by type and whether Kafka acked them",
)

worker_messages = meter.create_counter(
    "football.worker.messages",
    unit="{message}",
    description="Kafka messages a worker finished with, by consumer group and outcome",
)

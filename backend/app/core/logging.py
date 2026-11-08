"""Structured JSON logging (stdout) with optional OpenTelemetry tracing."""
from __future__ import annotations

import json
import logging
import os
import sys

from app.core.config import settings

_STD = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"), "level": record.levelname, "logger": record.name,
                   "msg": record.getMessage()}
        payload.update({k: v for k, v in record.__dict__.items() if k not in _STD})
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging() -> None:
    root = logging.getLogger()
    if any(isinstance(h.formatter, JsonFormatter) for h in root.handlers):
        return
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter())
    root.handlers = [h]
    root.setLevel(settings.log_level)
    logging.getLogger("uvicorn.access").setLevel("WARNING")
    if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        try:  # optional: distributed tracing when the OpenTelemetry SDK is installed
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            tp = TracerProvider(resource=Resource.create({"service.name": os.getenv("OTEL_SERVICE_NAME", "rip-api")}))
            tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
            trace.set_tracer_provider(tp)
        except ImportError:
            logging.getLogger("rip").warning("OTEL endpoint set but opentelemetry packages not installed")

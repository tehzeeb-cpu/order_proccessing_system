# shared/logging.py
"""
WHY THIS FILE EXISTS:
Implements structured JSON logging across the Coordinator and all Microservices.

Why Structured JSON Logging?
Plain text logs ("Order failed for ORD001") are difficult to parse in log aggregators (Elasticsearch, CloudWatch).
Structured JSON logs (`{"timestamp": "...", "order_id": "ORD001", "level": "ERROR", "service": "payment-service"}`)
enable instant filtering, correlation tracing, and automated alerting.

Interview Explanation:
"Structured logging attaches contextual metadata (order_id, service_name, latency) to every log line, 
making distributed transaction debugging straightforward across multi-container topologies."
"""

import logging
import json
import sys
from datetime import datetime


class JSONFormatter(logging.Formatter):
    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "service": self.service_name,
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        
        # Attach extra contextual fields if passed to logger
        if hasattr(record, "order_id"):
            log_data["order_id"] = getattr(record, "order_id")
        if hasattr(record, "step_name"):
            log_data["step_name"] = getattr(record, "step_name")
        if hasattr(record, "event_type"):
            log_data["event_type"] = getattr(record, "event_type")
        if hasattr(record, "execution_time_ms"):
            log_data["execution_time_ms"] = getattr(record, "execution_time_ms")
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_logger(service_name: str) -> logging.Logger:
    """Configures root logger with JSON formatting directed to stdout."""
    logger = logging.getLogger(service_name)
    logger.setLevel(logging.INFO)
    
    # Avoid duplicate handlers if re-initialized
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter(service_name))
        logger.addHandler(handler)
        
    return logger

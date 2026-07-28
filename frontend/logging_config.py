# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import os
import sys

from pythonjsonlogger import json


def setup_logging(service_name: str | None = None, level: str | None = None):
    """Sets up standardized JSON logging for the entire application."""
    if level is None:
        level = os.getenv("LOG_LEVEL", "INFO").upper()

    numeric_level = getattr(logging, level, logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Console Handler
    handler = logging.StreamHandler(sys.stdout)

    # Standard format for JSON logs
    format_str = (
        "%(asctime)s %(name)s %(levelname)s %(message)s %(filename)s %(lineno)d"
    )

    formatter = json.JsonFormatter(format_str, json_ensure_ascii=False)
    handler.setFormatter(formatter)

    # Clear existing handlers to avoid duplicates
    root_logger.handlers = []
    root_logger.addHandler(handler)

    # Silence noisy defaults unless in DEBUG
    if level != "DEBUG":
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)

    service = service_name or os.getenv("SERVICE_NAME", "unknown-service")
    logging.info(
        f"Logging initialized for {service}",
        extra={"service": service, "log_level": level},
    )


def get_uvicorn_log_config(level: str = "info"):
    """Returns a dictionary configuration for uvicorn to use the JSON formatter."""
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": "pythonjsonlogger.json.JsonFormatter",
                "format": "%(asctime)s %(name)s %(levelname)s %(message)s %(filename)s %(lineno)d",
            },
        },
        "handlers": {
            "default": {
                "formatter": "json",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": level.upper()},
            "uvicorn.error": {"level": level.upper()},
            "uvicorn.access": {
                "handlers": ["default"],
                "level": level.upper(),
                "propagate": False,
            },
        },
    }


if __name__ == "__main__":
    # Test logging
    setup_logging("test-service")
    logging.info("This is a test log message")
    logging.error("This is an error message", extra={"error_code": 500})

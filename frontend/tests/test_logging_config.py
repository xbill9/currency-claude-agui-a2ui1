import logging

from logging_config import get_uvicorn_log_config, setup_logging


def test_setup_logging_configures_root_logger():
    setup_logging(service_name="test-service", level="DEBUG")

    root_logger = logging.getLogger()
    assert root_logger.level == logging.DEBUG
    assert len(root_logger.handlers) == 1

    # Check if formatter is JsonFormatter
    handler = root_logger.handlers[0]
    from pythonjsonlogger import json

    assert isinstance(handler.formatter, json.JsonFormatter)


def test_get_uvicorn_log_config():
    config = get_uvicorn_log_config(level="warning")
    assert config["version"] == 1
    assert config["loggers"]["uvicorn"]["level"] == "WARNING"
    assert "json" in config["formatters"]

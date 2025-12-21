"""
Logging utility for DepotButler application.
Provides consistent logging configuration across all modules.

Log level priority:
1. Function parameter (level=)
2. Environment variable (LOG_LEVEL)
3. MongoDB config (app_config.log_level) - checked asynchronously if available
4. Default: INFO
"""

import logging
import os
import sys


def get_logger(name: str, level: str | None = None) -> logging.Logger:
    """
    Get a configured logger instance.

    Args:
        name: Logger name (usually __name__)
        level: Log level override (DEBUG, INFO, WARNING, ERROR)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Only configure if not already configured
    if not logger.handlers:
        # Set log level with priority: parameter > env var > default
        log_level = level or os.getenv("LOG_LEVEL", "INFO")
        logger.setLevel(getattr(logging, log_level.upper()))

        # Create console handler
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logger.level)

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)

        # Add handler to logger
        logger.addHandler(handler)

        # Prevent duplicate logs
        logger.propagate = False

    return logger

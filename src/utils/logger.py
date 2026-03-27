import logging
import os
from typing import Optional


def get_logger(name: Optional[str] = None) -> logging.Logger:
    logger_name = name or "etf_quant_advisor"
    logger = logging.getLogger(logger_name)
    if logger.handlers:
        return logger

    log_level = os.getenv("ADVISOR_LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(log_level)
    logger.propagate = False
    return logger

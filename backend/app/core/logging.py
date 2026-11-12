import logging
import sys
from app.core.config import settings


def setup_logging() -> logging.Logger:
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt=f"[%(asctime)s] [{settings.INSTANCE_ID}] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = [handler]

    # Suppress excessive noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    return root_logger


logger = logging.getLogger("seatsurge")

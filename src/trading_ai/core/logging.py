from loguru import logger
import sys


def configure_logging(level: str = "INFO"):
    logger.remove()

    logger.add(
        sys.stdout,
        level=level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name} | {message}",
    )

    logger.add(
        "logs/trading.log",
        rotation="10 MB",
        retention="10 days",
        level=level,
    )

    return logger

from loguru import logger

logger.add(
    "logs/trading.log", rotation="100 MB", retention="30 days", compression="zip"
)

log = logger

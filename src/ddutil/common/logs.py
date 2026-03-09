#########################################################################################
### Library Imports
#########################################################################################
import os
import sys
from loguru import logger  # type: ignore


#########################################################################################
### Configure Loguru
#########################################################################################
# Remove default handler
logger.remove()

# Get log level from environment variable, default to INFO
log_level = os.getenv("LOG_LEVEL", "INFO").upper()

# Add custom handler with nice formatting
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=log_level,
    colorize=True,
)


#########################################################################################
### Export
#########################################################################################
__all__ = ["logger"]

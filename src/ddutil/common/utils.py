#########################################################################################
### Imports
#########################################################################################
import os
from .logs import logger


#########################################################################################
### Functions
#########################################################################################
def set_env_variables(env_vars: dict):
    for key, value in env_vars.items():
        if isinstance(value, str):
            logger.debug(f"Setting environment variable: {key}")
            os.environ[key] = value

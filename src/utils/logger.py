import logging
import sys
from typing import Any, Dict
import json
from ..config.settings import settings

class StructuredLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(settings.LOG_LEVEL)
        
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
        self.logger.addHandler(handler)
    
    def _log(self, level: int, message: str, **kwargs: Dict[str, Any]) -> None:
        if kwargs:
            message = f"{message} {json.dumps(kwargs)}"
        self.logger.log(level, message)
    
    def info(self, message: str, **kwargs: Dict[str, Any]) -> None:
        self._log(logging.INFO, message, **kwargs)
    
    def error(self, message: str, **kwargs: Dict[str, Any]) -> None:
        self._log(logging.ERROR, message, **kwargs)
    
    def debug(self, message: str, **kwargs: Dict[str, Any]) -> None:
        self._log(logging.DEBUG, message, **kwargs)
    
    def warning(self, message: str, **kwargs: Dict[str, Any]) -> None:
        self._log(logging.WARNING, message, **kwargs) 
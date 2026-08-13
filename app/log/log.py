import os
import sys

from loguru import logger as loguru_logger

from app.settings import settings


class Loggin:
    def __init__(self) -> None:
        debug = settings.DEBUG
        if debug:
            self.level = "DEBUG"
        else:
            self.level = "INFO"

    def setup_logger(self):
        loguru_logger.remove()
        loguru_logger.add(sink=sys.stdout, level=self.level)
        os.makedirs(settings.LOGS_ROOT, exist_ok=True)
        loguru_logger.add(
            sink=os.path.join(settings.LOGS_ROOT, "finwork.log"),
            level=self.level,
            rotation="50 MB",
            retention="14 days",
            encoding="utf-8",
            enqueue=True,
            backtrace=True,
            diagnose=bool(settings.DEBUG),
        )
        return loguru_logger


loggin = Loggin()
logger = loggin.setup_logger()

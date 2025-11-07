import logging
import os
from logging.handlers import TimedRotatingFileHandler

_logger_list = {}
ROOT_DIR = os.path.abspath(os.path.dirname(__file__))  # path to .utils
BOT_ROOT = os.path.abspath(os.path.join(ROOT_DIR, ".."))
DIR_LOGS = os.path.join(BOT_ROOT, ".logs")

def setup_logger(name, log_file='bot_logs.log'):
    if name in _logger_list:
        return _logger_list[name]

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # File handler with daily rotation
    os.makedirs(DIR_LOGS, exist_ok=True)
    file_path = os.path.join(DIR_LOGS, log_file)
    file_handler = TimedRotatingFileHandler(
        file_path,
        when='midnight',
        interval=1,
        backupCount=7
    )
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    _logger_list[name] = logger
    return logger

def setup_temp_logger(name):
    if name in _logger_list:
        return _logger_list[name]

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    _logger_list[name] = logger

    return logger

class FakeLogger:
    def __getattr__(self, _):
        return lambda *args, **kwargs: None

def setup_fake():
    return FakeLogger()


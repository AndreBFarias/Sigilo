import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging() -> None:
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    if logger.hasHandlers():
        logger.handlers.clear()
    log_format = '[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] - %(message)s'
    date_format = '%H:%M:%S'
    formatter = logging.Formatter(log_format, datefmt=date_format)
    log_file = Path(__file__).resolve().parent.parent / 'app.log'
    file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=2, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # Terceiros barulhentos ficam em WARNING: o fontTools despeja ~94 linhas
    # INFO por selagem e o watchdog inunda o DEBUG — o sinal do app sumia.
    for ruidoso in ('fontTools', 'watchdog', 'PIL', 'urllib3'):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logging.critical('Uncaught exception', exc_info=(exc_type, exc_value, exc_traceback))
    sys.excepthook = handle_exception
    logging.info('Sistema de logging inicializado.')

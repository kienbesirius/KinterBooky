import os
import sys
from pathlib import Path
import logging
from typing import List, Tuple

_fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_datefmt = "%Y-%m-%d %H:%M:%S"
_path = Path(__file__).resolve()
for x in range(3):
    _path = _path.parent
    if _path.name == "src":
        sys.path.insert(0, _path)

SRC_DIR = Path(sys.path[0])
ASSETS_DIR = SRC_DIR / "assets"

def get_config_path() -> Path:
        """
        Trả về đường dẫn config.ini nằm cùng thư mục với .py hoặc .exe.
        """
        base_dir = Path(sys.argv[0]).resolve().parent
        return base_dir / "config.ini"

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # When running in a PyInstaller bundle
        base_path = sys._MEIPASS
    except Exception:
        # When running normally
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


class ListLogHandler(logging.Handler):
    def __init__(self, buffer: List[str]):
        super().__init__()
        self._buffer = buffer

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            self._buffer.append(msg)
        except Exception as e:
            self.handleError(record)

def build_log_buffer(name: str = "KinterBooky", level = logging.DEBUG) -> Tuple[logging.Logger, List[str]]:
    logger = logging.getLogger(name=name)
    logger.setLevel(level)
    log_buffer: List[str] = []

    log_formatter = logging.Formatter(fmt=_fmt, datefmt=_datefmt)
    listLogHandler = ListLogHandler(log_buffer)
    listLogHandler.setFormatter(log_formatter)
    listLogHandler.setLevel(level)

    stdoutLogHandler = logging.StreamHandler(sys.stdout)
    stdoutLogHandler.setFormatter(log_formatter)
    stdoutLogHandler.setLevel(level)

    logger.addHandler(listLogHandler)
    logger.addHandler(stdoutLogHandler)

    return logger, log_buffer

__all__ = [
    "SRC_DIR",
    "ASSETS_DIR",
    "get_config_path",
    "resource_path",
    "build_log_buffer",
]
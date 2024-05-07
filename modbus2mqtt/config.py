import logging
from pathlib import Path

from yaml import safe_load


def parse_config(filename: Path) -> dict:
    try:
        with filename.open() as f:
            return safe_load(f)
    except Exception as e:
        logging.error(f"Can't load yaml file {filename}: {e:r}")
        raise

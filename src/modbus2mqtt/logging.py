import logging


class PrefixAdapter(logging.LoggerAdapter):
    def __init__(self, logger: logging.Logger, prefix: str):
        super().__init__(logger, {})
        self._prefix = prefix

    def process(self, msg, kwargs):
        return f"{self._prefix}{msg}", kwargs

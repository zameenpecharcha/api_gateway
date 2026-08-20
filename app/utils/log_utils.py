import logging
import re
import sys

from app.utils.request_context import get_correlation_id, get_user_id

_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*")
_BEARER_RE = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-+=/]+")


def redact_secrets(message: str) -> str:
    text = str(message)
    text = _JWT_RE.sub("[REDACTED_TOKEN]", text)
    text = _BEARER_RE.sub(r"\1[REDACTED_TOKEN]", text)
    return text


class CustomAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        """
        Process the log message to include user_id and correlation_id.
        """
        return f'UserID: {self.extra.get("user_id", "N/A")} | CorrelationID: {self.extra.get("correlation_id", "N/A")} | {msg}', kwargs


_LOGGER_NAME = "zpc.gateway"
_configured = False


def _get_logger() -> logging.Logger:
    global _configured
    logger = logging.getLogger(_LOGGER_NAME)
    if not _configured:
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(levelname)s - %(message)s",
                    datefmt="%m/%d/%Y %I:%M:%S %p",
                )
            )
            logger.addHandler(handler)
        # Avoid dropping logs when uvicorn has already configured logging.
        logger.propagate = True
        _configured = True
    return logger


def log_msg(level: str, message: str, user_id: str = None, correlation_id: str = None):
    """
    Logs messages with user_id and correlation_id.

    Args:
        level (str): Log level (debug, info, warning, error, critical)
        message (str): Log message
        user_id (str, optional): ID of the user. Defaults to request context or 'N/A'.
        correlation_id (str, optional): Request correlation ID. Defaults to request context or 'N/A'.
    """
    extra = {
        "user_id": user_id or get_user_id() or "N/A",
        "correlation_id": correlation_id or get_correlation_id() or "N/A",
    }
    adapter = CustomAdapter(_get_logger(), extra)
    message = redact_secrets(message)

    level = (level or "info").lower()
    if level == "warn":
        level = "warning"
    log_methods = {
        "debug": adapter.debug,
        "info": adapter.info,
        "warning": adapter.warning,
        "error": adapter.error,
        "critical": adapter.critical,
    }
    log_methods.get(level, adapter.info)(message)
    # Also write to uvicorn's logger so container platforms surface the line.
    logging.getLogger("uvicorn.error").log(
        getattr(logging, level.upper(), logging.INFO),
        f'UserID: {extra["user_id"]} | CorrelationID: {extra["correlation_id"]} | {message}',
    )

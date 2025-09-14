import logging

class CustomAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        """
        Process the log message to include user_id and correlation_id.
        """
        return f'UserID: {self.extra.get("user_id", "N/A")} | CorrelationID: {self.extra.get("correlation_id", "N/A")} | {msg}', kwargs


def log_msg(level: str, message: str, user_id: str = None, correlation_id: str = None):
    """
    Logs messages with user_id and correlation_id.

    Args:
        level (str): Log level (debug, info, warning, error, critical)
        message (str): Log message
        user_id (str, optional): ID of the user. Defaults to 'N/A'.
        correlation_id (str, optional): Request correlation ID. Defaults to 'N/A'.
    """
    # Configure Logging
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%m/%d/%Y %I:%M:%S %p",
        level=logging.INFO  # Default to INFO
    )

    # Create Logger
    logger = logging.getLogger("custom_logger")

    # Create Adapter for User & Correlation ID
    extra = {
        "user_id": user_id if user_id else "N/A",
        "correlation_id": correlation_id if correlation_id else "N/A"
    }
    adapter = CustomAdapter(logger, extra)

    # Correct Logging Level Handling
    level = level.lower()
    log_methods = {
        "debug": adapter.debug,
        "info": adapter.info,
        "warning": adapter.warning,
        "error": adapter.error,
        "critical": adapter.critical
    }

    if level in log_methods:
        log_methods[level](message)
    else:
        log_methods['info'](message)

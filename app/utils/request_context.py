from contextvars import ContextVar
from typing import Optional

_user_id: ContextVar[Optional[str]] = ContextVar("zpc_user_id", default=None)
_correlation_id: ContextVar[Optional[str]] = ContextVar("zpc_correlation_id", default=None)


def get_user_id() -> Optional[str]:
    return _user_id.get()


def get_correlation_id() -> Optional[str]:
    return _correlation_id.get()


def set_user_id(value: Optional[str]) -> None:
    _user_id.set(value or None)


def set_correlation_id(value: Optional[str]) -> None:
    _correlation_id.set(value or None)


def reset_context() -> None:
    _user_id.set(None)
    _correlation_id.set(None)

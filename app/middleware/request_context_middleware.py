import uuid

from starlette.types import ASGIApp, Receive, Scope, Send

from app.utils.jwt_utils import peek_user_id_from_authorization
from app.utils.request_context import reset_context, set_correlation_id, set_user_id


def _header_map(scope: Scope) -> dict:
    return {
        k.decode("latin-1").lower(): v.decode("latin-1")
        for k, v in scope.get("headers") or []
    }


class RequestContextMiddleware:
    """Bind UserID / CorrelationID for the lifetime of each HTTP/WebSocket request."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        headers = _header_map(scope)
        correlation_id = (
            (headers.get("x-correlation-id") or headers.get("x-request-id") or "").strip()
            or str(uuid.uuid4())
        )
        set_correlation_id(correlation_id)

        user_id = peek_user_id_from_authorization(headers.get("authorization"))
        if user_id:
            set_user_id(user_id)

        async def send_with_correlation(message):
            if message["type"] == "http.response.start":
                out_headers = list(message.get("headers") or [])
                out_headers.append((b"x-correlation-id", correlation_id.encode("latin-1")))
                message = {**message, "headers": out_headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_correlation)
        finally:
            reset_context()

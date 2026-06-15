import json
import os
import re
import grpc

from starlette.types import ASGIApp, Receive, Scope, Send
from fastapi import Request
from starlette.responses import JSONResponse, Response
from app.clients.auth.auth_client import auth_service_client
from app.utils.log_utils import log_msg

PUBLIC_GRAPHQL_OPS = {
    "login", "register", "sendotp", "verifyotp", "forgotpassword", "logout",
    "createuser",
    # chat operations — authenticated via WebSocket session
    "createdmroom", "creategrouproom", "requestchatupload", "chatdownloadurl",
}

# CORS origins — same source as run_gateway.py
_origins_env = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
_ALLOWED_ORIGINS = {o.strip() for o in _origins_env.split() if o.strip()}

CORS_HEADERS = {
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Authorization, Content-Type, Accept",
    "Access-Control-Allow-Credentials": "true",
    "Access-Control-Max-Age": "86400",
}


class AuthMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] not in ("http",):
            await self.app(scope, receive, send)
            return

        # Handle CORS preflight (OPTIONS) here before reading the body,
        # so the browser never sees a 401 on preflight.
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            method = scope.get("method", "")
            origin = headers.get(b"origin", b"").decode("utf-8", errors="ignore")

            if method == "OPTIONS":
                cors_headers = dict(CORS_HEADERS)
                if origin in _ALLOWED_ORIGINS or not _ALLOWED_ORIGINS:
                    cors_headers["Access-Control-Allow-Origin"] = origin or "*"
                else:
                    cors_headers["Access-Control-Allow-Origin"] = next(iter(_ALLOWED_ORIGINS), "*")
                res = Response(status_code=204, headers=cors_headers)
                await res(scope, receive, send)
                return

        # Read full body to inspect GraphQL operation
        # (origin already extracted above for preflight handling)
        body = b""
        more_body = True
        while more_body:
            message = await receive()
            body += message.get("body", b"")
            more_body = message.get("more_body", False)
            if message.get("type") == "http.disconnect":
                break

        async def receive_with_body():
            return {"type": "http.request", "body": body, "more_body": False}

        request = Request(scope, receive=receive_with_body)

        if self._should_skip_auth(request, body):
            await self.app(scope, receive_with_body, send)
            return

        try:
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                raise ValueError("Missing or invalid Authorization header")

            token = auth_header.split(" ")[1]
            response = auth_service_client.validate_token(token)

            if not response.valid:
                raise ValueError(response.message or "Invalid or expired token")

            # Propagate user to downstream handlers
            request.state.user = {
                "id": response.user_info.id,
                "email": response.user_info.email,
                "role": response.user_info.role,
                "first_name": response.user_info.first_name,
                "last_name": response.user_info.last_name,
            }
            scope["state"] = request.state._state

            await self.app(scope, receive_with_body, send)

        except ValueError as e:
            log_msg("warn", f"Authentication failed: {str(e)}")
            res = JSONResponse(status_code=401, content={"detail": str(e)},
                               headers={"Access-Control-Allow-Origin": origin or "*",
                                        "Access-Control-Allow-Credentials": "true"})
            await res(scope, receive_with_body, send)

        except grpc.RpcError as e:
            log_msg("error", f"gRPC error: {str(e)}")
            status = 401 if e.code() == grpc.StatusCode.UNAUTHENTICATED else 403
            detail = e.details() or "Authorization failed"
            res = JSONResponse(status_code=status, content={"detail": detail},
                               headers={"Access-Control-Allow-Origin": origin or "*",
                                        "Access-Control-Allow-Credentials": "true"})
            await res(scope, receive_with_body, send)

        except Exception as e:
            log_msg("error", f"AuthMiddleware error: {str(e)}")
            res = JSONResponse(status_code=500, content={"detail": str(e)},
                               headers={"Access-Control-Allow-Origin": origin or "*",
                                        "Access-Control-Allow-Credentials": "true"})
            await res(scope, receive_with_body, send)

    def _should_skip_auth(self, request: Request, body: bytes) -> bool:
        path = request.url.path

        # Always pass CORS preflight through
        if request.method == "OPTIONS":
            return True

        # Public paths — no token needed
        if path in ("/", "/health") or any(path.startswith(p) for p in [
            "/docs", "/redoc", "/openapi.json",
            "/chat", "/static", "/api/v1/ws/chat",
        ]):
            return True

        # GraphQL endpoint — individual resolvers handle their own auth
        if path.startswith("/api/v1/graphql"):
            try:
                parsed = json.loads(body.decode("utf-8"))
                query = parsed.get("query", "")
                match = re.search(r"(mutation|query)\s+(\w+)", query, re.IGNORECASE)
                if match:
                    op_name = match.group(2).lower()
                    if op_name in PUBLIC_GRAPHQL_OPS:
                        return True
                # If no named operation matched, still pass through
                # (resolvers enforce auth via Info context)
                return True
            except Exception as e:
                log_msg("warn", f"Failed to parse GraphQL operation: {e}")
                return True  # pass through on parse error — resolver handles auth

        return False

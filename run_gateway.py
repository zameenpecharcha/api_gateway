import asyncio
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from pathlib import Path

from dotenv import load_dotenv

# Must be called before service-module imports that read os.getenv at module level
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

import truststore

truststore.inject_into_ssl()

import strawberry
from fastapi import FastAPI, Request, Response
from starlette.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.schema.auth_schema import Query as AuthQuery, Mutation as AuthMutation
from app.schema.user_schema import Query as UserQuery, Mutation as UserMutation
from app.schema.posts_schema import Query as PostsQuery, Mutation as PostsMutation
from app.schema.property_schema import Query as PropertyQuery, Mutation as PropertyMutation
from app.schema.chat_schema import Query as ChatQuery, Mutation as ChatMutation
from app.schema.global_search_schema import Query as GlobalSearchQuery
from app.schema.analytics_schema import Query as AnalyticsQuery
from app.middleware.auth_middleware import AuthMiddleware
from app.middleware.request_context_middleware import RequestContextMiddleware
from app.api.chat_api import chat_router
from strawberry.fastapi import GraphQLRouter
from app.api.uploads_api import router as uploads_router
from app.utils.graphql_log_context import BindLogContextExtension
from app.utils.request_context import get_correlation_id, get_user_id, set_correlation_id, set_user_id

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class _ContextCopyingExecutor(ThreadPoolExecutor):
    def submit(self, fn, *args, **kwargs):
        ctx = copy_context()

        def runner():
            return ctx.run(fn, *args, **kwargs)

        return super().submit(runner)


async def graphql_context(request: Request, response: Response = None):
    correlation_id = (
        get_correlation_id()
        or request.headers.get("x-correlation-id")
        or request.headers.get("x-request-id")
    )
    user_id = get_user_id()
    if correlation_id:
        set_correlation_id(correlation_id)
    if user_id:
        set_user_id(user_id)
    return {
        "request": request,
        "response": response,
        "correlation_id": correlation_id,
        "user_id": user_id,
    }


# Define GraphQL schema
@strawberry.type
class Query(AuthQuery, UserQuery, PostsQuery, PropertyQuery, ChatQuery, GlobalSearchQuery, AnalyticsQuery): pass

@strawberry.type
class Mutation(AuthMutation, UserMutation, PostsMutation, PropertyMutation, ChatMutation): pass

schema = strawberry.Schema(query=Query, mutation=Mutation, extensions=[BindLogContextExtension])

# Initialize app
app = FastAPI(title="ZPC API Gateway", version="1.0.0")

# CORS origins — load_dotenv() already called above so env vars are available
_origins_env = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
allowed_origins = [o.strip() for o in re.split(r"[\s,]+", _origins_env) if o.strip()]

# Mount GraphQL route
graphql_app = GraphQLRouter(
    schema=schema,
    graphql_ide="graphiql",
    path="/graphql",
    context_getter=graphql_context,
)
app.include_router(graphql_app, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(uploads_router, prefix="/api/v1")

# Serve static test UI at /chat (optional — folder may be absent in Docker)
_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")

    @app.get("/chat")
    def chat_ui():
        return FileResponse(os.path.join(_static_dir, "chat.html"))

# Health check
@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "api_gateway"}

@app.get("/")
def root():
    return {
        "service": "ZPC API Gateway",
        "graphql": "/api/v1/graphql",
        "websocket_chat": "/api/v1/ws/chat/{room_id}/{user_id}",
        "health": "/health",
    }

@app.on_event("startup")
async def _copy_contextvars_into_threads():
    loop = asyncio.get_running_loop()
    loop.set_default_executor(_ContextCopyingExecutor(max_workers=32))


app = AuthMiddleware(app)
app = RequestContextMiddleware(app)

# CORSMiddleware must be the OUTERMOST layer so it:
#   1. handles OPTIONS preflight before AuthMiddleware runs
#   2. injects Access-Control-* headers on ALL responses (including 401/500 from AuthMiddleware)
app = CORSMiddleware(
    app,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["x-correlation-id"],
)

# Run app
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("run_gateway:app", host="0.0.0.0", port=port, reload=False)

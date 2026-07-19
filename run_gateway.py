import os
import re
from dotenv import load_dotenv

# Must be called before service-module imports that read os.getenv at module level
load_dotenv()

import strawberry
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.schema.auth_schema import Query as AuthQuery, Mutation as AuthMutation
from app.schema.user_schema import Query as UserQuery, Mutation as UserMutation
from app.schema.posts_schema import Query as PostsQuery, Mutation as PostsMutation
from app.schema.property_schema import Query as PropertyQuery, Mutation as PropertyMutation
from app.schema.chat_schema import Query as ChatQuery, Mutation as ChatMutation
from app.middleware.auth_middleware import AuthMiddleware
from app.api.chat_api import chat_router
from strawberry.fastapi import GraphQLRouter
from app.api.uploads_api import router as uploads_router

import logging
import os

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define GraphQL schema
@strawberry.type
class Query(AuthQuery, UserQuery, PostsQuery, PropertyQuery, ChatQuery): pass

@strawberry.type
class Mutation(AuthMutation, UserMutation, PostsMutation, PropertyMutation, ChatMutation): pass

schema = strawberry.Schema(query=Query, mutation=Mutation)

# Initialize app
app = FastAPI(title="ZPC API Gateway", version="1.0.0")

# CORS origins — load_dotenv() already called above so env vars are available
_origins_env = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
allowed_origins = [o.strip() for o in re.split(r"[\s,]+", _origins_env) if o.strip()]

# Mount GraphQL route
graphql_app = GraphQLRouter(
    schema=schema,
    graphql_ide="graphiql",
    path="/graphql"
)
app.include_router(graphql_app, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(uploads_router, prefix="/api/v1")

# Serve static test UI at /chat
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/chat")
def chat_ui():
    return FileResponse("static/chat.html")

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

app = AuthMiddleware(app)

# CORSMiddleware must be the OUTERMOST layer so it:
#   1. handles OPTIONS preflight before AuthMiddleware runs
#   2. injects Access-Control-* headers on ALL responses (including 401/500 from AuthMiddleware)
app = CORSMiddleware(
    app,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Run app
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("run_gateway:app", host="0.0.0.0", port=port, reload=False)

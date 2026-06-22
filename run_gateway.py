import os
import strawberry
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from app.schema.auth_schema import Query as AuthQuery, Mutation as AuthMutation
from app.schema.user_schema import Query as UserQuery, Mutation as UserMutation
from app.schema.posts_schema import Query as PostsQuery, Mutation as PostsMutation
from app.schema.chat_schema import Query as ChatQuery, Mutation as ChatMutation
from app.middleware.auth_middleware import AuthMiddleware
from app.api.chat_api import chat_router
from strawberry.fastapi import GraphQLRouter

import logging

load_dotenv()

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define GraphQL schema
@strawberry.type
class Query(AuthQuery, UserQuery, PostsQuery, ChatQuery): pass

@strawberry.type
class Mutation(AuthMutation, UserMutation, PostsMutation, ChatMutation): pass

schema = strawberry.Schema(query=Query, mutation=Mutation)

# Initialize app
app = FastAPI(title="ZPC API Gateway", version="1.0.0")

# CORS — read from env, fallback to localhost dev
_origins_env = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
allowed_origins = [o.strip() for o in _origins_env.split() if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount GraphQL route
graphql_app = GraphQLRouter(
    schema=schema,
    graphql_ide="graphiql",
    path="/graphql"
)
app.include_router(graphql_app, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")

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

# Run app
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("run_gateway:app", host="0.0.0.0", port=port, reload=False)

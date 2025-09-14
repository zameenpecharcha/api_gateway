import strawberry
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.schema.auth_schema import Query as AuthQuery, Mutation as AuthMutation
from app.schema.user_schema import Query as UserQuery, Mutation as UserMutation
from app.schema.posts_schema import Query as PostsQuery, Mutation as PostsMutation
from app.middleware.auth_middleware import AuthMiddleware
from app.api.chat_api import chat_router
from strawberry.fastapi import GraphQLRouter

import logging

# Logging setup
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Define GraphQL schema
@strawberry.type
class Query(AuthQuery, UserQuery, PostsQuery): pass

@strawberry.type
class Mutation(AuthMutation, UserMutation, PostsMutation): pass

schema = strawberry.Schema(query=Query, mutation=Mutation)

# Initialize app
app = FastAPI()

# Mount GraphQL route
graphql_app = GraphQLRouter(
    schema=schema,
    graphql_ide="graphiql",
    path="/graphql"
)
app.include_router(graphql_app, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")

# Health check
@app.get("/health")
def health_check():
    return {"status": "healthy"}

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app = AuthMiddleware(app)

# Run app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("run_gateway:app", host="0.0.0.0", port=8000, reload=True)

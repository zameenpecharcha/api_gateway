from fastapi import APIRouter
from app.schema.posts_schema import Query, Mutation
import strawberry
from strawberry.asgi import GraphQL

posts_router = APIRouter()

schema = strawberry.Schema(Query, Mutation)
graphql_app = GraphQL(schema)

posts_router.add_route("/graphql", graphql_app) 
from fastapi import APIRouter
from app.schema.property_schema import Query, Mutation
import strawberry
from strawberry.asgi import GraphQL

property_router = APIRouter()

schema = strawberry.Schema(Query, Mutation)
graphql_app = GraphQL(schema)

property_router.add_route("/graphql", graphql_app) 
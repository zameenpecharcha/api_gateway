from fastapi import APIRouter
from gateway.app.schema.notification_schema import Mutation, Query
import strawberry
from strawberry.asgi import GraphQL

router = APIRouter()

schema = strawberry.Schema(Query, Mutation)
graphql_app = GraphQL(schema)

router.add_route("/graphql", graphql_app) 
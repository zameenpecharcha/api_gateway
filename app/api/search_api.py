from fastapi import APIRouter, HTTPException
from ..utils.grpc_client import search_client
from ..schema.search_schema import Mutation, Query
import strawberry
from strawberry.asgi import GraphQL

router = APIRouter()

schema = strawberry.Schema(Query, Mutation)
graphql_app = GraphQL(schema)

router.add_route("/graphql", graphql_app)

@router.get("/posts")
async def search_posts(
    query: str,
    page: int = 1,
    page_size: int = 10,
    latitude: float = None,
    longitude: float = None,
    radius_km: float = None
):
    try:
        response = search_client.search_posts(
            query=query,
            page=page,
            page_size=page_size,
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/users")
async def search_users(
    query: str,
    page: int = 1,
    page_size: int = 10
):
    try:
        response = search_client.search_users(
            query=query,
            page=page,
            page_size=page_size
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/properties")
async def search_properties(
    query: str,
    page: int = 1,
    page_size: int = 10,
    min_price: float = None,
    max_price: float = None,
    property_type: str = None,
    latitude: float = None,
    longitude: float = None,
    radius_km: float = None
):
    try:
        response = search_client.search_properties(
            query=query,
            page=page,
            page_size=page_size,
            min_price=min_price,
            max_price=max_price,
            property_type=property_type,
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 
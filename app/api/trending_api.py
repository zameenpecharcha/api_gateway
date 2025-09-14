from fastapi import APIRouter, HTTPException
from ..utils.grpc_client import trending_client
from ..schema.trending_schema import Mutation, Query
import strawberry
from strawberry.asgi import GraphQL

router = APIRouter()

schema = strawberry.Schema(Query, Mutation)
graphql_app = GraphQL(schema)

router.add_route("/graphql", graphql_app)

@router.get("/posts")
async def get_trending_posts(
    limit: int = 10,
    latitude: float = None,
    longitude: float = None,
    radius_km: float = None
):
    try:
        response = trending_client.get_trending_posts(
            limit=limit,
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/properties")
async def get_trending_properties(
    limit: int = 10,
    property_type: str = None,
    min_price: float = None,
    max_price: float = None,
    latitude: float = None,
    longitude: float = None,
    radius_km: float = None
):
    try:
        response = trending_client.get_trending_properties(
            limit=limit,
            property_type=property_type,
            min_price=min_price,
            max_price=max_price,
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/locations")
async def get_trending_locations(
    limit: int = 10,
    latitude: float = None,
    longitude: float = None,
    radius_km: float = None
):
    try:
        response = trending_client.get_trending_locations(
            limit=limit,
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 
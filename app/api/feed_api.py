from fastapi import APIRouter, HTTPException
from ..utils.grpc_client import feed_client
from ..schema.feed_schema import Mutation, Query
import strawberry
from strawberry.asgi import GraphQL

router = APIRouter()

schema = strawberry.Schema(Query, Mutation)
graphql_app = GraphQL(schema)

router.add_route("/graphql", graphql_app)

@router.post("/posts")
async def create_post(user_id: int, content: str, latitude: float, longitude: float, location_name: str):
    try:
        response = feed_client.create_post(user_id, content, latitude, longitude, location_name)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/posts/{post_id}")
async def get_post(post_id: int):
    try:
        response = feed_client.get_post(post_id)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/users/{user_id}/posts")
async def get_user_posts(user_id: int):
    try:
        response = feed_client.get_user_posts(user_id)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/posts/nearby")
async def get_nearby_posts(latitude: float, longitude: float, radius_km: float = 10.0):
    try:
        response = feed_client.get_nearby_posts(latitude, longitude, radius_km)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/posts/{post_id}")
async def update_post(post_id: int, content: str, latitude: float = None, longitude: float = None, location_name: str = None):
    try:
        response = feed_client.update_post(post_id, content, latitude, longitude, location_name)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/posts/{post_id}")
async def delete_post(post_id: int):
    try:
        response = feed_client.delete_post(post_id)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/posts/{post_id}/like")
async def like_post(post_id: int, user_id: int):
    try:
        response = feed_client.like_post(post_id, user_id)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/posts/{post_id}/unlike")
async def unlike_post(post_id: int, user_id: int):
    try:
        response = feed_client.unlike_post(post_id, user_id)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 
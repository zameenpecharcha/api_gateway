import typing
from datetime import datetime
import strawberry
from gateway.app.exception.UserException import REException
from gateway.app.utils.log_utils import log_msg
from gateway.app.utils.grpc_client import NotificationServiceClient
from typing import Optional, List

client = NotificationServiceClient()

@strawberry.type
class Notification:
    id: int
    user_id: int
    title: str
    message: str
    type: str
    read: bool
    created_at: datetime
    metadata: Optional[str] = None

@strawberry.type
class NotificationPage:
    notifications: List[Notification]
    total_count: int
    has_next: bool

@strawberry.type
class LocationSubscription:
    user_id: int
    latitude: float
    longitude: float
    radius_km: float
    active: bool

@strawberry.type
class Query:
    @strawberry.field
    def get_user_notifications(
        self, 
        user_id: int, 
        page: int = 1, 
        page_size: int = 10,
        unread_only: bool = False
    ) -> NotificationPage:
        try:
            response = client.get_user_notifications(
                user_id=user_id,
                page=page,
                page_size=page_size,
                unread_only=unread_only
            )
            return NotificationPage(
                notifications=[
                    Notification(
                        id=n.id,
                        user_id=n.user_id,
                        title=n.title,
                        message=n.message,
                        type=n.type,
                        read=n.read,
                        created_at=n.created_at,
                        metadata=getattr(n, 'metadata', None)
                    ) for n in response.notifications
                ],
                total_count=response.total_count,
                has_next=response.has_next
            )
        except Exception as e:
            log_msg("error", f"Error fetching notifications for user {user_id}: {str(e)}")
            raise REException("NOTIFICATION_FETCH_FAILED", "Failed to fetch notifications", str(e)).to_graphql_error()

@strawberry.type
class Mutation:
    @strawberry.mutation
    async def mark_notification_read(self, notification_id: int) -> bool:
        try:
            response = client.mark_notification_read(notification_id)
            return response.success
        except Exception as e:
            log_msg("error", f"Failed to mark notification {notification_id} as read: {str(e)}")
            raise REException("NOTIFICATION_UPDATE_FAILED", "Failed to update notification", str(e)).to_graphql_error()

    @strawberry.mutation
    async def mark_all_notifications_read(self, user_id: int) -> bool:
        try:
            response = client.mark_all_notifications_read(user_id)
            return response.success
        except Exception as e:
            log_msg("error", f"Failed to mark all notifications as read for user {user_id}: {str(e)}")
            raise REException("NOTIFICATION_UPDATE_FAILED", "Failed to update notifications", str(e)).to_graphql_error()

    @strawberry.mutation
    async def subscribe_to_location(
        self,
        user_id: int,
        latitude: float,
        longitude: float,
        radius_km: float
    ) -> LocationSubscription:
        try:
            response = client.subscribe_to_location(
                user_id=user_id,
                latitude=latitude,
                longitude=longitude,
                radius_km=radius_km
            )
            return LocationSubscription(
                user_id=response.user_id,
                latitude=response.latitude,
                longitude=response.longitude,
                radius_km=response.radius_km,
                active=response.active
            )
        except Exception as e:
            log_msg("error", f"Failed to subscribe to location for user {user_id}: {str(e)}")
            raise REException("LOCATION_SUBSCRIPTION_FAILED", "Failed to subscribe to location", str(e)).to_graphql_error()

    @strawberry.mutation
    async def unsubscribe_from_location(self, user_id: int) -> bool:
        try:
            response = client.unsubscribe_from_location(user_id)
            return response.success
        except Exception as e:
            log_msg("error", f"Failed to unsubscribe from location for user {user_id}: {str(e)}")
            raise REException("LOCATION_UNSUBSCRIBE_FAILED", "Failed to unsubscribe from location", str(e)).to_graphql_error() 
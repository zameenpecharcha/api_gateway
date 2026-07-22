import os
from dotenv import load_dotenv
from app.clients.grpc_base_client import GRPCBaseClient
from app.proto_files.user import user_pb2, user_pb2_grpc

load_dotenv()


class UserServiceClient(GRPCBaseClient):
    def __init__(self):
        target = os.getenv("USER_SERVICE_URL", "localhost:50053")
        super().__init__(user_pb2_grpc.UserServiceStub, target=target)

    def get_user(self, user_id: str,token=None):
        request = user_pb2.UserRequest(id=user_id)
        return self._call("GetUser", request,token=token)

    def create_user(self, first_name, last_name, email, phone, password, role=None,
                   address=None, latitude=None, longitude=None, bio=None,token=None):
        request = user_pb2.CreateUserRequest(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            password=password,
            role=role,
            address=address,
            latitude=latitude,
            longitude=longitude,
            bio=bio
        )
        return self._call(self.stub.CreateUser, request,token=token)

    def create_user_rating(self, rated_user_id, rated_by_user_id, rating_value, title=None, review=None, rating_type=None, is_anonymous=False, token=None):
        # title/is_anonymous are accepted for GraphQL compat but not persisted by user_service
        request = user_pb2.CreateUserRatingRequest(
            rated_user_id=rated_user_id,
            rated_by_user_id=rated_by_user_id,
            rating_value=rating_value,
            review=review or "",
            rating_type=rating_type or "",
        )
        return self._call(self.stub.CreateUserRating, request, token=token)

    def get_user_ratings(self, user_id,token=None):
        request = user_pb2.UserRequest(id=user_id)
        return self._call(self.stub.GetUserRatings, request,token=token)

    def follow_user(self, user_id, following_id, followee_type: str = "user", status: str = "pending", token=None):
        request = user_pb2.FollowUserRequest(
            follower_id=user_id,
            following_id=following_id,
            followee_type=followee_type,
            status=status
        )
        return self._call(self.stub.FollowUser, request,token=token)

    def update_follow_status(self, follower_id: int, following_id: int, status: str, token=None):
        request = user_pb2.FollowUserRequest(
            follower_id=follower_id,
            following_id=following_id,
            followee_type="user",
            status=status,
        )
        return self._call(self.stub.UpdateFollowStatus, request, token=token)

    def get_media(self, media_id: int, token=None):
        # Proto reuses UserRequest.id as media_id
        request = user_pb2.UserRequest(id=media_id)
        return self._call(self.stub.GetMedia, request, token=token)

    def update_profile_photo(
        self,
        user_id: int,
        file_path: str,
        file_name: str = None,
        content_type: str = None,
        caption: str = None,
        media_order: int = 1,
        token=None,
    ):
        request = user_pb2.UpdateUserPhotoRequest(
            user_id=user_id,
            media=user_pb2.MediaRequest(
                context_id=user_id,
                context_type="user_profile",
                media_type="image",
                file_path=file_path,
                file_name=file_name or "",
                content_type=content_type or "",
                media_order=media_order,
                caption=caption or "",
            ),
        )
        return self._call(self.stub.UpdateProfilePhoto, request, token=token)

    def update_cover_photo(
        self,
        user_id: int,
        file_path: str,
        file_name: str = None,
        content_type: str = None,
        caption: str = None,
        media_order: int = 1,
        token=None,
    ):
        request = user_pb2.UpdateUserPhotoRequest(
            user_id=user_id,
            media=user_pb2.MediaRequest(
                context_id=user_id,
                context_type="user_cover",
                media_type="image",
                file_path=file_path,
                file_name=file_name or "",
                content_type=content_type or "",
                media_order=media_order,
                caption=caption or "",
            ),
        )
        return self._call(self.stub.UpdateCoverPhoto, request, token=token)

    def get_user_followers(self, user_id,token=None):
        request = user_pb2.UserRequest(id=user_id)
        return self._call(self.stub.GetUserFollowers, request,token=token)

    def get_user_following(self, user_id,token=None):
        request = user_pb2.UserRequest(id=user_id)
        return self._call(self.stub.GetUserFollowing, request,token=token)

    def check_following_status(self, user_id, following_id,token=None):
        request = user_pb2.CheckFollowingRequest(
            user_id=user_id,
            following_id=following_id
        )
        return self._call(self.stub.CheckFollowingStatus, request,token=token)

    def get_pending_follow_requests(self, user_id, token=None):
        request = user_pb2.UserRequest(id=user_id)
        return self._call(self.stub.GetPendingFollowRequests, request, token=token)

    def update_user_location(self, user_id: int, latitude: float, longitude: float, token=None):
        request = user_pb2.UpdateUserLocationRequest(
            user_id=user_id,
            latitude=latitude,
            longitude=longitude,
        )
        return self._call(self.stub.UpdateUserLocation, request, token=token)

    def list_users(self, search: str = "", page: int = 1, limit: int = 50, token=None):
        request = user_pb2.ListUsersRequest(search=search, page=page, limit=limit)
        return self._call("ListUsers", request, token=token)

    def get_suggested_users(self, user_id: int, limit: int = 10, token=None):
        request = user_pb2.SuggestedUsersRequest(user_id=user_id, limit=limit)
        return self._call("SuggestedUsers", request, token=token)

    def create_notification(
        self,
        user_id: int,
        title: str,
        message: str,
        type: str = "",
        metadata: str = "",
        token=None,
    ):
        request = user_pb2.CreateNotificationRequest(
            user_id=user_id,
            title=title,
            message=message,
            type=type,
            metadata=metadata,
        )
        return self._call("CreateNotification", request, token=token)

    def list_notifications(self, user_id: int, page: int = 1, limit: int = 20, token=None):
        request = user_pb2.ListNotificationsRequest(user_id=user_id, page=page, limit=limit)
        return self._call("ListNotifications", request, token=token)

    def mark_notification_read(self, notification_id: int, user_id: int, token=None):
        request = user_pb2.MarkNotificationReadRequest(
            notification_id=notification_id,
            user_id=user_id,
        )
        return self._call("MarkNotificationRead", request, token=token)


user_service_client = UserServiceClient()
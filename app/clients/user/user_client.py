import os
from typing import List, Optional

from dotenv import load_dotenv

from app.clients.grpc_base_client import GRPCBaseClient
from app.proto_files.user import user_pb2, user_pb2_grpc

load_dotenv()


def _str_id(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


class UserServiceClient(GRPCBaseClient):
    def __init__(self):
        target = os.getenv("USER_SERVICE_URL", "localhost:50053")
        super().__init__(user_pb2_grpc.UserServiceStub, target=target)

    def _photo_upload(self, user_id: str, file_path: str, file_name: str = "", content_type: str = "", cover: bool = False, token=None):
        photo = user_pb2.PhotoUpload(
            file_path=file_path or "",
            file_name=file_name or "",
            content_type=content_type or "",
        )
        request = user_pb2.UploadPhotoRequest(user_id=_str_id(user_id), photo=photo)
        method = "UploadCoverPhoto" if cover else "UploadProfilePhoto"
        return self._call(method, request, token=token)

    # ------------------------------------------------------------------ users
    def get_user(self, user_id: str, token=None):
        return self._call(
            "GetUser",
            user_pb2.GetUserRequest(user_id=_str_id(user_id)),
            token=token,
        )

    def get_user_by_email(self, email: str, token=None):
        return self._call(
            "GetUserByEmail",
            user_pb2.GetUserByEmailRequest(email=(email or "").strip().lower()),
            token=token,
            require_token=False,
        )

    def get_user_by_phone(self, phone: str, token=None):
        return self._call(
            "GetUserByPhone",
            user_pb2.GetUserByPhoneRequest(phone=phone or ""),
            token=token,
            require_token=False,
        )

    def update_verification_flags(
        self,
        user_id: str,
        email_verified: bool = None,
        phone_verified: bool = None,
        token=None,
    ):
        request = user_pb2.UpdateVerificationFlagsRequest(user_id=_str_id(user_id))
        if email_verified is not None:
            request.email_verified = bool(email_verified)
        if phone_verified is not None:
            request.phone_verified = bool(phone_verified)
        return self._call("UpdateVerificationFlags", request, token=token, require_token=False)

    def get_my_profile(self, user_id: str, token=None):
        return self._call(
            "GetMyProfile",
            user_pb2.GetMyProfileRequest(user_id=_str_id(user_id)),
            token=token,
        )

    def create_user(
        self,
        first_name,
        last_name,
        email,
        phone="",
        password=None,
        role=None,
        address=None,
        latitude=None,
        longitude=None,
        bio=None,
        user_id: str = "",
        token=None,
    ):
        request = user_pb2.CreateUserRequest(
            id=_str_id(user_id),
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone or "",
            role=role or "",
            bio=bio or "",
            latitude=float(latitude or 0),
            longitude=float(longitude or 0),
        )
        return self._call("CreateUser", request, token=token)

    def update_user_profile(
        self,
        user_id: str,
        first_name: str = "",
        last_name: str = "",
        phone: str = "",
        bio: str = "",
        role: str = "",
        latitude: float = 0,
        longitude: float = 0,
        token=None,
    ):
        return self._call(
            "UpdateUserProfile",
            user_pb2.UpdateUserProfileRequest(
                user_id=_str_id(user_id),
                first_name=first_name or "",
                last_name=last_name or "",
                phone=phone or "",
                bio=bio or "",
                role=role or "",
                latitude=latitude,
                longitude=longitude,
            ),
            token=token,
        )

    def delete_user(self, user_id: str, token=None):
        return self._call(
            "DeleteUser",
            user_pb2.DeleteUserRequest(user_id=_str_id(user_id)),
            token=token,
        )

    def update_profile_photo(self, user_id: str, file_path: str, file_name: str = None, content_type: str = None, **kwargs):
        token = kwargs.get("token")
        return self._photo_upload(user_id, file_path, file_name or "", content_type or "", cover=False, token=token)

    def update_cover_photo(self, user_id: str, file_path: str, file_name: str = None, content_type: str = None, **kwargs):
        token = kwargs.get("token")
        return self._photo_upload(user_id, file_path, file_name or "", content_type or "", cover=True, token=token)

    def delete_profile_photo(self, user_id: str, token=None):
        return self._call(
            "DeleteProfilePhoto",
            user_pb2.DeletePhotoRequest(user_id=_str_id(user_id)),
            token=token,
        )

    def delete_cover_photo(self, user_id: str, token=None):
        return self._call(
            "DeleteCoverPhoto",
            user_pb2.DeletePhotoRequest(user_id=_str_id(user_id)),
            token=token,
        )

    def search_users(self, search: str = "", role: str = "", page: int = 1, limit: int = 20, token=None):
        return self._call(
            "SearchUsers",
            user_pb2.SearchUsersRequest(search=search, role=role, page=page, limit=limit),
            token=token,
        )

    def list_users(self, search: str = "", page: int = 1, limit: int = 50, token=None):
        return self.search_users(search=search, page=page, limit=limit, token=token)

    def get_user_statistics(self, user_id: str, token=None):
        return self._call(
            "GetUserStatistics",
            user_pb2.GetUserStatisticsRequest(user_id=_str_id(user_id)),
            token=token,
        )

    def update_user_location(self, user_id: str, latitude: float, longitude: float, token=None):
        return self._call(
            "UpdateUserLocation",
            user_pb2.UpdateUserLocationRequest(
                user_id=_str_id(user_id),
                latitude=latitude,
                longitude=longitude,
            ),
            token=token,
        )

    def get_suggested_users(self, user_id: str, limit: int = 10, token=None):
        return self._call(
            "SuggestedUsers",
            user_pb2.SuggestedUsersRequest(user_id=_str_id(user_id), limit=limit),
            token=token,
        )

    def get_media(self, media_id: str, token=None):
        return self._call(
            "GetMedia",
            user_pb2.GetMediaRequest(media_id=_str_id(media_id)),
            token=token,
        )

    # ------------------------------------------------------------------ follow
    def follow_user(self, user_id, following_id, followee_type: str = "USER", status: str = "ACTIVE", token=None):
        return self._call(
            "FollowUser",
            user_pb2.FollowUserRequest(
                follower_id=_str_id(user_id),
                following_id=_str_id(following_id),
                follow_type=(followee_type or "USER").upper(),
            ),
            token=token,
        )

    def unfollow_user(self, follower_id: str, following_id: str, token=None):
        return self._call(
            "UnfollowUser",
            user_pb2.UnfollowUserRequest(
                follower_id=_str_id(follower_id),
                following_id=_str_id(following_id),
            ),
            token=token,
        )

    def update_follow_status(self, follower_id: str, following_id: str, status: str, token=None):
        return self._call(
            "UpdateFollowStatus",
            user_pb2.UpdateFollowStatusRequest(
                follower_id=_str_id(follower_id),
                following_id=_str_id(following_id),
                status=status,
            ),
            token=token,
        )

    def get_user_followers(self, user_id, page: int = 1, limit: int = 20, token=None):
        return self._call(
            "GetUserFollowers",
            user_pb2.GetFollowListRequest(user_id=_str_id(user_id), page=page, limit=limit),
            token=token,
        )

    def get_user_following(self, user_id, page: int = 1, limit: int = 20, token=None):
        return self._call(
            "GetUserFollowing",
            user_pb2.GetFollowListRequest(user_id=_str_id(user_id), page=page, limit=limit),
            token=token,
        )

    def get_pending_follow_requests(self, user_id, page: int = 1, limit: int = 20, token=None):
        return self._call(
            "GetPendingFollowRequests",
            user_pb2.GetFollowListRequest(user_id=_str_id(user_id), page=page, limit=limit),
            token=token,
        )

    def check_following_status(self, user_id, following_id, token=None):
        return self._call(
            "CheckFollowingStatus",
            user_pb2.CheckFollowStatusRequest(
                follower_id=_str_id(user_id),
                following_id=_str_id(following_id),
            ),
            token=token,
        )

    # ------------------------------------------------------------------ ratings
    def create_user_rating(
        self,
        rated_user_id,
        rated_by_user_id,
        rating_value,
        title=None,
        review=None,
        rating_type=None,
        is_anonymous=False,
        token=None,
    ):
        return self._call(
            "AddUserRating",
            user_pb2.AddUserRatingRequest(
                rated_user_id=_str_id(rated_user_id),
                rated_by=_str_id(rated_by_user_id),
                rating_value=float(rating_value),
                title=title or "",
                review=review or "",
                rating_type=rating_type or "",
                is_anonymous=bool(is_anonymous),
            ),
            token=token,
        )

    def update_user_rating(
        self,
        rating_id: str,
        rated_by: str,
        rating_value: float = 0,
        title: str = "",
        review: str = "",
        rating_type: str = "",
        is_anonymous: bool = False,
        token=None,
    ):
        return self._call(
            "UpdateUserRating",
            user_pb2.UpdateUserRatingRequest(
                rating_id=_str_id(rating_id),
                rated_by=_str_id(rated_by),
                rating_value=rating_value,
                title=title,
                review=review,
                rating_type=rating_type,
                is_anonymous=is_anonymous,
            ),
            token=token,
        )

    def delete_user_rating(self, rating_id: str, rated_by: str, token=None):
        return self._call(
            "DeleteUserRating",
            user_pb2.DeleteUserRatingRequest(
                rating_id=_str_id(rating_id),
                rated_by=_str_id(rated_by),
            ),
            token=token,
        )

    def get_user_ratings(self, user_id, page: int = 1, limit: int = 20, token=None):
        return self._call(
            "GetUserRatings",
            user_pb2.GetUserRatingsRequest(user_id=_str_id(user_id), page=page, limit=limit),
            token=token,
        )

    def get_rating_summary(self, user_id: str, token=None):
        return self._call(
            "GetRatingSummary",
            user_pb2.GetRatingSummaryRequest(user_id=_str_id(user_id)),
            token=token,
        )

    def get_my_submitted_ratings(self, rated_by: str, page: int = 1, limit: int = 20, token=None):
        return self._call(
            "GetMySubmittedRatings",
            user_pb2.GetMySubmittedRatingsRequest(rated_by=_str_id(rated_by), page=page, limit=limit),
            token=token,
        )

    # -------------------------------------------------------------- notifications
    def create_notification(self, user_id: str, title: str, message: str, type: str = "", metadata: str = "", token=None):
        return self._call(
            "CreateNotification",
            user_pb2.CreateNotificationRequest(
                user_id=_str_id(user_id),
                title=title,
                message=message,
                type=type,
                metadata=metadata,
            ),
            token=token,
        )

    def list_notifications(self, user_id: str, page: int = 1, limit: int = 20, token=None):
        return self._call(
            "ListNotifications",
            user_pb2.ListNotificationsRequest(user_id=_str_id(user_id), page=page, limit=limit),
            token=token,
        )

    def mark_notification_read(self, notification_id: str, user_id: str, token=None):
        return self._call(
            "MarkNotificationRead",
            user_pb2.MarkNotificationReadRequest(
                notification_id=_str_id(notification_id),
                user_id=_str_id(user_id),
            ),
            token=token,
        )


user_service_client = UserServiceClient()

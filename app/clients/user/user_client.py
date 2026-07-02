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
        return self._call("CreateUser", request,token=token)

    def create_user_rating(self, rated_user_id, rated_by_user_id, rating_value, review=None, rating_type=None,token=None):
        request = user_pb2.CreateUserRatingRequest(
            rated_user_id=rated_user_id,
            rated_by_user_id=rated_by_user_id,
            rating_value=rating_value,
            review=review,
            rating_type=rating_type
        )
        return self._call("CreateUserRating", request,token=token)

    def get_user_ratings(self, user_id,token=None):
        request = user_pb2.UserRequest(id=user_id)
        return self._call("GetUserRatings", request,token=token)

    def follow_user(self, user_id, following_id,token=None):
        request = user_pb2.FollowUserRequest(
            user_id=user_id,
            following_id=following_id
        )
        return self._call("FollowUser", request,token=token)

    def get_user_followers(self, user_id,token=None):
        request = user_pb2.UserRequest(id=user_id)
        return self._call("GetUserFollowers", request,token=token)

    def get_user_following(self, user_id,token=None):
        request = user_pb2.UserRequest(id=user_id)
        return self._call("GetUserFollowing", request,token=token)

    def check_following_status(self, user_id, following_id,token=None):
        request = user_pb2.CheckFollowingRequest(
            user_id=user_id,
            following_id=following_id
        )
        return self._call("CheckFollowingStatus", request,token=token)

    def list_users(self, search: str = "", page: int = 1, limit: int = 50, token=None):
        request = user_pb2.ListUsersRequest(search=search, page=page, limit=limit)
        return self._call("ListUsers", request, token=token)


user_service_client = UserServiceClient()

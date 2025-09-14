from app.clients.grpc_base_client import GRPCBaseClient
from app.proto_files.user import user_pb2, user_pb2_grpc


class UserServiceClient(GRPCBaseClient):
    def __init__(self):
        super().__init__(user_pb2_grpc.UserServiceStub, target='localhost:50051')

    def get_user(self, user_id: str,token=None):
        request = user_pb2.UserRequest(id=user_id)
        return self._call(self.stub.GetUser, request,token=token)

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

    def create_user_rating(self, rated_user_id, rated_by_user_id, rating_value, review=None, rating_type=None,token=None):
        request = user_pb2.CreateUserRatingRequest(
            rated_user_id=rated_user_id,
            rated_by_user_id=rated_by_user_id,
            rating_value=rating_value,
            review=review,
            rating_type=rating_type
        )
        return self._call(self.stub.CreateUserRating, request,token=token)

    def get_user_ratings(self, user_id,token=None):
        request = user_pb2.UserRequest(id=user_id)
        return self._call(self.stub.GetUserRatings, request,token=token)

    def follow_user(self, user_id, following_id,token=None):
        request = user_pb2.FollowUserRequest(
            user_id=user_id,
            following_id=following_id
        )
        return self._call(self.stub.FollowUser, request,token=token)

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


user_service_client = UserServiceClient()
import typing
import strawberry
from app.exception.UserException import REException
from app.utils.log_utils import log_msg
from app.clients.user.user_client import user_service_client
from strawberry.types import Info

from app.utils.jwt_utils import get_token


@strawberry.type
class User:
    id: int
    first_name: str
    last_name: str
    email: str
    phone: str
    profile_photo: typing.Optional[str] = None
    role: typing.Optional[str] = None
    address: typing.Optional[str] = None
    latitude: typing.Optional[float] = None
    longitude: typing.Optional[float] = None
    bio: typing.Optional[str] = None
    isactive: bool
    email_verified: bool
    phone_verified: bool
    created_at: str
    ratings: typing.List['UserRating'] = strawberry.field(default_factory=list)
    followers_count: int = 0
    following_count: int = 0

@strawberry.type
class UserRating:
    id: int
    rated_user_id: int
    rated_by_user_id: int
    rating_value: int
    review: typing.Optional[str] = None
    rating_type: typing.Optional[str] = None
    created_at: str
    updated_at: str

@strawberry.type
class UserFollower:
    id: int
    user_id: int
    following_id: int
    status: str
    followed_at: str

@strawberry.type
class Query:
    @strawberry.field
    def user(self, info: Info, id: int) -> typing.Optional[User]:
        try:
            log_msg("info", f"Fetching user with ID {id}")
            token = get_token(info)
            response = user_service_client.get_user(id, token=token)

            if response is None:
                raise REException("USER_NOT_FOUND", "User does not exist", "Invalid ID provided")

            # Get user ratings
            ratings_response = user_service_client.get_user_ratings(id,token=token)
            ratings = [
                UserRating(
                    id=rating.id,
                    rated_user_id=rating.rated_user_id,
                    rated_by_user_id=rating.rated_by_user_id,
                    rating_value=rating.rating_value,
                    review=rating.review,
                    rating_type=rating.rating_type,
                    created_at=rating.created_at,
                    updated_at=rating.updated_at
                ) for rating in ratings_response.ratings
            ]

            # Get followers/following count
            followers = user_service_client.get_user_followers(id,token=token)
            following = user_service_client.get_user_following(id,token=token)

            return User(
                id=response.id,
                first_name=response.first_name,
                last_name=response.last_name,
                email=response.email,
                phone=response.phone,
                profile_photo=response.profile_photo,
                role=response.role,
                address=response.address,
                latitude=response.latitude,
                longitude=response.longitude,
                bio=response.bio,
                isactive=response.isActive,
                email_verified=response.email_verified,
                phone_verified=response.phone_verified,
                created_at=response.created_at,
                ratings=ratings,
                followers_count=len(followers.followers),
                following_count=len(following.followers)
            )

        except Exception as e:
            log_msg("error", f"Error fetching user: {str(e)}")
            raise REException(
                "USER_NOT_FOUND",
                "Failed to fetch user",
                str(e)
            ).to_graphql_error()

    @strawberry.field
    def user_ratings(self, info: Info, user_id: int) -> typing.List[UserRating]:
        try:
            log_msg("info", f"Fetching ratings for user {user_id}")
            token = get_token(info)
            response = user_service_client.get_user_ratings(user_id,token=token)
            return [
                UserRating(
                    id=rating.id,
                    rated_user_id=rating.rated_user_id,
                    rated_by_user_id=rating.rated_by_user_id,
                    rating_value=rating.rating_value,
                    review=rating.review,
                    rating_type=rating.rating_type,
                    created_at=rating.created_at,
                    updated_at=rating.updated_at
                ) for rating in response.ratings
            ]
        except Exception as e:
            log_msg("error", f"Error fetching user ratings: {str(e)}")
            raise REException(
                "RATINGS_FETCH_FAILED",
                "Failed to fetch user ratings",
                str(e)
            ).to_graphql_error()

    @strawberry.field
    def user_followers(self, info: Info, user_id: int) -> typing.List[UserFollower]:
        try:
            log_msg("info", f"Fetching followers for user {user_id}")
            token = get_token(info)
            response = user_service_client.get_user_followers(user_id,token=token)
            return [
                UserFollower(
                    id=follower.id,
                    user_id=follower.user_id,
                    following_id=follower.following_id,
                    status=follower.status,
                    followed_at=follower.followed_at
                ) for follower in response.followers
            ]
        except Exception as e:
            log_msg("error", f"Error fetching user followers: {str(e)}")
            raise REException(
                "FOLLOWERS_FETCH_FAILED",
                "Failed to fetch user followers",
                str(e)
            ).to_graphql_error()

    @strawberry.field
    def user_following(self,info: Info, user_id: int) -> typing.List[UserFollower]:
        try:
            log_msg("info", f"Fetching following for user {user_id}")
            token = get_token(info)
            response = user_service_client.get_user_following(user_id,token=token)
            return [
                UserFollower(
                    id=follow.id,
                    user_id=follow.user_id,
                    following_id=follow.following_id,
                    status=follow.status,
                    followed_at=follow.followed_at
                ) for follow in response.followers
            ]
        except Exception as e:
            log_msg("error", f"Error fetching user following: {str(e)}")
            raise REException(
                "FOLLOWING_FETCH_FAILED",
                "Failed to fetch user following",
                str(e)
            ).to_graphql_error()

    @strawberry.field
    def check_following_status(self,info: Info, user_id: int, following_id: int) -> typing.Optional[UserFollower]:
        try:
            log_msg("info", f"Checking following status for user {user_id} -> {following_id}")
            token = get_token(info)
            response = user_service_client.check_following_status(user_id, following_id,token=token)
            if not response or not response.id:
                return None
            return UserFollower(
                id=response.id,
                user_id=response.user_id,
                following_id=response.following_id,
                status=response.status,
                followed_at=response.followed_at
            )
        except Exception as e:
            log_msg("error", f"Error checking following status: {str(e)}")
            raise REException(
                "FOLLOWING_STATUS_CHECK_FAILED",
                "Failed to check following status",
                str(e)
            ).to_graphql_error()

@strawberry.type
class Mutation:
    @strawberry.mutation
    async def create_user(
        self,
        info: Info,
        first_name: str,
        last_name: str,
        email: str,
        phone: str,
        password: str,
        role: typing.Optional[str] = None,
        address: typing.Optional[str] = None,
        latitude: typing.Optional[float] = None,
        longitude: typing.Optional[float] = None,
        bio: typing.Optional[str] = None
    ) -> User:
        try:
            log_msg("info", f"Creating user {email}")
            token = get_token(info)
            response = user_service_client.create_user(
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone,
                password=password,
                role=role,
                address=address,
                latitude=latitude,
                longitude=longitude,
                bio=bio,
                token=token
            )
            return User(
                id=response.id,
                first_name=response.first_name,
                last_name=response.last_name,
                email=response.email,
                phone=response.phone,
                profile_photo=response.profile_photo,
                role=response.role,
                address=response.address,
                latitude=response.latitude,
                longitude=response.longitude,
                bio=response.bio,
                isactive=response.isActive,
                email_verified=response.email_verified,
                phone_verified=response.phone_verified,
                created_at=response.created_at
            )
        except Exception as e:
            error_message = str(e)
            if "Email already registered" in error_message:
                raise REException(
                    "EMAIL_EXISTS",
                    "This email address is already registered",
                    "Please use a different email address or try logging in"
                ).to_graphql_error()
            elif "phone_unique" in error_message:
                raise REException(
                    "PHONE_EXISTS",
                    "This phone number is already registered",
                    "Please use a different phone number"
                ).to_graphql_error()
            elif "invalid email format" in error_message.lower():
                raise REException(
                    "INVALID_EMAIL",
                    "Invalid email format",
                    "Please provide a valid email address"
                ).to_graphql_error()
            else:
                raise REException(
                    "USER_CREATION_FAILED",
                    "Failed to create user",
                    "Please try again later"
                ).to_graphql_error()

    @strawberry.mutation
    async def create_user_rating(
        self,
        info: Info,
        rated_user_id: int,
        rated_by_user_id: int,
        rating_value: int,
        review: typing.Optional[str] = None,
        rating_type: typing.Optional[str] = None
    ) -> UserRating:
        try:
            log_msg("info", f"Creating rating for user {rated_user_id}")
            token = get_token(info)
            response = user_service_client.create_user_rating(
                rated_user_id=rated_user_id,
                rated_by_user_id=rated_by_user_id,
                rating_value=rating_value,
                review=review,
                rating_type=rating_type,
                token=token
            )
            return UserRating(
                id=response.id,
                rated_user_id=response.rated_user_id,
                rated_by_user_id=response.rated_by_user_id,
                rating_value=response.rating_value,
                review=response.review,
                rating_type=response.rating_type,
                created_at=response.created_at,
                updated_at=response.updated_at
            )
        except Exception as e:
            log_msg("error", f"Error creating rating: {str(e)}")
            raise REException(
                "RATING_CREATION_FAILED",
                "Failed to create rating",
                str(e)
            ).to_graphql_error()

    @strawberry.mutation
    async def follow_user(
        self,
        info: Info,
        user_id: int,
        following_id: int
    ) -> UserFollower:
        try:
            log_msg("info", f"User {user_id} following user {following_id}")
            token = get_token(info)
            response = user_service_client.follow_user(user_id, following_id,token=token)
            return UserFollower(
                id=response.id,
                user_id=response.user_id,
                following_id=response.following_id,
                status=response.status,
                followed_at=response.followed_at
            )
        except Exception as e:
            log_msg("error", f"Error following user: {str(e)}")
            raise REException(
                "FOLLOW_FAILED",
                "Failed to follow user",
                str(e)
            ).to_graphql_error()



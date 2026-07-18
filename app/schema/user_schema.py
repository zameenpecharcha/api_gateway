import typing
import strawberry
from app.exception.UserException import REException
from app.utils.log_utils import log_msg
from app.clients.user.user_client import user_service_client
from strawberry.types import Info

from app.utils.jwt_utils import get_token
from app.clients.user.user_client import user_service_client
import httpx
import os
import truststore

# Use OS certificate store on Windows (fixes local SSL verify issues)
truststore.inject_into_ssl()
from app.utils.s3_utils import generate_presigned_get_url_from_url


@strawberry.type
class User:
    id: int
    first_name: str
    last_name: str
    email: str
    phone: str
    profile_photo: typing.Optional[str] = None
    cover_photo: typing.Optional[str] = None
    profile_photo_signed_url: typing.Optional[str] = None
    cover_photo_signed_url: typing.Optional[str] = None
    role: typing.Optional[str] = None
    address: typing.Optional[str] = None
    latitude: typing.Optional[float] = None
    longitude: typing.Optional[float] = None
    bio: typing.Optional[str] = None
    isactive: bool
    email_verified: bool
    phone_verified: bool
    created_at: str
    cover_photo_id: typing.Optional[int] = 0
    profile_photo_id: typing.Optional[int] = 0
    ratings: typing.List['UserRating'] = strawberry.field(default_factory=list)
    followers_count: int = 0
    following_count: int = 0

    @strawberry.field
    def profilePhotoSignedUrl(self, info: Info) -> typing.Optional[str]:
        try:
            from app.utils.s3_utils import generate_presigned_get_url_from_url
            token = get_token(info)

            candidate: typing.Optional[str] = getattr(self, "profile_photo", None)
            if (not candidate) and getattr(self, "profile_photo_id", 0):
                media = user_service_client.get_media(media_id=int(self.profile_photo_id), token=token)
                candidate = getattr(media, "media_url", None)

            if not candidate:
                return None

            url = generate_presigned_get_url_from_url(candidate)
            return url or candidate
        except Exception:
            # Fallback to whatever is already present
            return getattr(self, "profile_photo", None)

    @strawberry.field
    def coverPhotoSignedUrl(self, info: Info) -> typing.Optional[str]:
        try:
            from app.utils.s3_utils import generate_presigned_get_url_from_url
            token = get_token(info)

            candidate: typing.Optional[str] = None
            if getattr(self, "cover_photo_id", 0):
                media = user_service_client.get_media(media_id=int(self.cover_photo_id), token=token)
                candidate = getattr(media, "media_url", None)

            if not candidate:
                return None

            url = generate_presigned_get_url_from_url(candidate)
            return url or candidate
        except Exception:
            return None

    @strawberry.field
    def coverPhotoUrl(self, info: Info) -> typing.Optional[str]:
        try:
            token = get_token(info)
            candidate: typing.Optional[str] = None
            if getattr(self, "cover_photo_id", 0):
                media = user_service_client.get_media(media_id=int(self.cover_photo_id), token=token)
                candidate = getattr(media, "media_url", None)
            return candidate
        except Exception:
            return None

    @strawberry.field
    def profilePhotoUrl(self, info: Info) -> typing.Optional[str]:
        try:
            token = get_token(info)
            candidate: typing.Optional[str] = getattr(self, "profile_photo", None)
            if (not candidate) and getattr(self, "profile_photo_id", 0):
                media = user_service_client.get_media(media_id=int(self.profile_photo_id), token=token)
                candidate = getattr(media, "media_url", None)
            return candidate
        except Exception:
            return getattr(self, "profile_photo", None)

@strawberry.type
class Media:
    id: int
    context_id: int
    context_type: str
    media_type: str
    media_url: str
    media_order: int
    media_size: typing.Optional[int]
    caption: typing.Optional[str]
    uploaded_at: str

@strawberry.type
class UserRating:
    id: int
    rated_user_id: int
    rated_by_user_id: int
    rating_value: int
    title: typing.Optional[str] = None
    review: typing.Optional[str] = None
    rating_type: typing.Optional[str] = None
    is_anonymous: typing.Optional[bool] = False
    created_at: str
    updated_at: str

@strawberry.type
class PresignUploadResponse:
    uploadUrl: str
    publicUrl: str
    key: str

@strawberry.type
class UserFollower:
    id: int
    follower_id: int
    following_id: int
    followee_type: typing.Optional[str] = None
    status: str
    followed_at: str

@strawberry.type
class OlaSuggestion:
    reference: typing.Optional[str]
    place_id: typing.Optional[str]
    description: typing.Optional[str]
    lat: typing.Optional[float]
    lng: typing.Optional[float]
    types: typing.List[str]

@strawberry.type
class Query:
    @strawberry.field
    async def ola_autocomplete(
        self,
        info: Info,
        input: str,
        location: typing.Optional[str] = None,
        radius: typing.Optional[int] = None,
        strictbounds: typing.Optional[bool] = None,
    ) -> typing.List[OlaSuggestion]:
        try:
            api_key = os.getenv("OLA_MAPS_API_KEY")
            
            if not api_key:
                raise REException("CONFIG_ERROR", "OLA_MAPS_API_KEY not configured", "Set OLA_MAPS_API_KEY env var").to_graphql_error()
            params = {"input": input, "api_key": api_key}
            if location:
                params["location"] = location
            if radius is not None:
                params["radius"] = radius
            if strictbounds is not None:
                params["strictbounds"] = str(strictbounds).lower()

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get("https://api.olamaps.io/places/v1/autocomplete", params=params)
                resp.raise_for_status()
                data = resp.json() or {}
                predictions = data.get("predictions", [])
                suggestions: typing.List[OlaSuggestion] = []
                for p in predictions:
                    loc = ((p or {}).get("geometry") or {}).get("location") or {}
                    suggestions.append(
                        OlaSuggestion(
                            reference=p.get("reference"),
                            place_id=p.get("place_id"),
                            description=p.get("description"),
                            lat=loc.get("lat"),
                            lng=loc.get("lng"),
                            types=p.get("types") or [],
                        )
                    )
                return suggestions
        except httpx.HTTPStatusError as e:
            raise REException("OLA_API_ERROR", "Failed to fetch suggestions", e.response.text).to_graphql_error()
        except Exception as e:
            raise REException("AUTOCOMPLETE_FAILED", "Autocomplete failed", str(e)).to_graphql_error()
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
                    title=getattr(rating, 'title', None),
                    review=rating.review,
                    rating_type=rating.rating_type,
                    is_anonymous=getattr(rating, 'is_anonymous', False),
                    created_at=rating.created_at,
                    updated_at=rating.updated_at
                ) for rating in ratings_response.ratings
            ]

            # Get followers/following count
            followers = user_service_client.get_user_followers(id,token=token)
            following = user_service_client.get_user_following(id,token=token)

            cover_photo = getattr(response, 'cover_photo', None) or None
            return User(
                id=response.id,
                first_name=response.first_name,
                last_name=response.last_name,
                email=response.email,
                phone=response.phone,
                profile_photo=response.profile_photo,
                cover_photo=cover_photo,
                profile_photo_signed_url=generate_presigned_get_url_from_url(response.profile_photo) if response.profile_photo else None,
                cover_photo_signed_url=generate_presigned_get_url_from_url(cover_photo) if cover_photo else None,
                role=response.role,
                address=response.address,
                latitude=response.latitude,
                longitude=response.longitude,
                bio=response.bio,
                isactive=response.isActive,
                email_verified=response.email_verified,
                phone_verified=response.phone_verified,
                created_at=response.created_at,
                cover_photo_id=getattr(response, 'cover_photo_id', 0),
                profile_photo_id=getattr(response, 'profile_photo_id', 0),
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
                    follower_id=follower.follower_id,
                    following_id=follower.following_id,
                    followee_type=getattr(follower, 'followee_type', None),
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
    def pending_follow_requests(self, info: Info, user_id: int) -> typing.List[UserFollower]:
        try:
            token = get_token(info)
            response = user_service_client.get_pending_follow_requests(user_id, token=token)
            return [
                UserFollower(
                    id=f.id,
                    follower_id=f.follower_id,
                    following_id=f.following_id,
                    followee_type=getattr(f, 'followee_type', None),
                    status=f.status,
                    followed_at=f.followed_at,
                ) for f in response.followers
            ]
        except Exception as e:
            raise REException(
                "PENDING_REQUESTS_FAILED",
                "Failed to fetch pending follow requests",
                str(e),
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
                    follower_id=follow.follower_id,
                    following_id=follow.following_id,
                    followee_type=getattr(follow, 'followee_type', None),
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
                follower_id=response.follower_id,
                following_id=response.following_id,
                followee_type=getattr(response, 'followee_type', None),
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

    @strawberry.field
    def media(self, info: Info, mediaId: int) -> typing.Optional[Media]:
        try:
            token = get_token(info)
            response = user_service_client.get_media(media_id=mediaId, token=token)
            if not response or not response.id:
                return None
            return Media(
                id=response.id,
                context_id=response.context_id,
                context_type=response.context_type,
                media_type=response.media_type,
                media_url=response.media_url,
                media_order=response.media_order,
                media_size=response.media_size,
                caption=response.caption,
                uploaded_at=response.uploaded_at,
            )
        except Exception as e:
            log_msg("error", f"Error fetching media: {str(e)}")
            return None
    def users(self, info: Info, search: typing.Optional[str] = "", page: int = 1, limit: int = 50) -> typing.List[User]:
        try:
            token = get_token(info)
            response = user_service_client.list_users(search=search or "", page=page, limit=limit, token=token)
            result = []
            for u in response.users:
                cover_photo = getattr(u, 'cover_photo', None) or None
                result.append(User(
                    id=u.id,
                    first_name=u.first_name,
                    last_name=u.last_name,
                    email=u.email,
                    phone=u.phone,
                    profile_photo=u.profile_photo or None,
                    cover_photo=cover_photo,
                    profile_photo_signed_url=generate_presigned_get_url_from_url(u.profile_photo) if u.profile_photo else None,
                    cover_photo_signed_url=None,
                    role=u.role or None,
                    address=u.address or None,
                    latitude=getattr(u, 'latitude', None) or None,
                    longitude=getattr(u, 'longitude', None) or None,
                    bio=getattr(u, 'bio', None) or None,
                    isactive=u.isActive,
                    email_verified=u.email_verified,
                    phone_verified=u.phone_verified,
                    created_at=u.created_at,
                ))
            return result
        except Exception as e:
            log_msg("error", f"Error listing users: {str(e)}")
            return []

@strawberry.type
class Mutation:
    @strawberry.mutation
    async def presignUserPhotoUpload(
        self,
        info: Info,
        fileName: str,
        contentType: typing.Optional[str] = None,
    ) -> PresignUploadResponse:
        try:
            # No auth requirement strictly needed for presign, but keep token access if required later
            _ = get_token(info)
            from app.utils.s3_utils import generate_presigned_put_url

            url, key, public_url = generate_presigned_put_url(file_name=fileName, content_type=contentType)
            return PresignUploadResponse(uploadUrl=url, publicUrl=public_url, key=key)
        except Exception as e:
            raise REException(
                "PRESIGN_FAILED",
                "Failed to generate presigned upload URL",
                str(e),
            ).to_graphql_error()
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
            cover_photo = getattr(response, 'cover_photo', None) or None
            return User(
                id=response.id,
                first_name=response.first_name,
                last_name=response.last_name,
                email=response.email,
                phone=response.phone,
                profile_photo=response.profile_photo,
                cover_photo=cover_photo,
                profile_photo_signed_url=generate_presigned_get_url_from_url(response.profile_photo) if response.profile_photo else None,
                cover_photo_signed_url=generate_presigned_get_url_from_url(cover_photo) if cover_photo else None,
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
        title: typing.Optional[str] = None,
        review: typing.Optional[str] = None,
        rating_type: typing.Optional[str] = None,
        is_anonymous: typing.Optional[bool] = False
    ) -> UserRating:
        try:
            log_msg("info", f"Creating rating for user {rated_user_id}")
            token = get_token(info)
            response = user_service_client.create_user_rating(
                rated_user_id=rated_user_id,
                rated_by_user_id=rated_by_user_id,
                rating_value=rating_value,
                title=title,
                review=review,
                rating_type=rating_type,
                is_anonymous=is_anonymous,
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
    async def updateProfilePhoto(
        self,
        info: Info,
        userId: int,
        filePath: str,
        fileName: typing.Optional[str] = None,
        contentType: typing.Optional[str] = None,
        caption: typing.Optional[str] = None,
        mediaOrder: typing.Optional[int] = 1,
    ) -> User:
        token = get_token(info)
        response = user_service_client.update_profile_photo(
            user_id=userId,
            file_path=filePath,
            file_name=fileName,
            content_type=contentType,
            caption=caption,
            media_order=mediaOrder or 1,
            token=token,
        )
        return User(
            id=response.id,
            first_name=response.first_name,
            last_name=response.last_name,
            email=response.email,
            phone=response.phone,
            profile_photo=response.profile_photo or None,
            role=response.role,
            address=response.address,
            latitude=response.latitude,
            longitude=response.longitude,
            bio=response.bio,
            isactive=response.isActive,
            email_verified=response.email_verified,
            phone_verified=response.phone_verified,
            created_at=response.created_at,
            cover_photo_id=getattr(response, 'cover_photo_id', 0),
            profile_photo_id=getattr(response, 'profile_photo_id', 0),
        )

    @strawberry.mutation
    async def updateCoverPhoto(
        self,
        info: Info,
        userId: int,
        filePath: str,
        fileName: typing.Optional[str] = None,
        contentType: typing.Optional[str] = None,
        caption: typing.Optional[str] = None,
        mediaOrder: typing.Optional[int] = 1,
    ) -> User:
        token = get_token(info)
        response = user_service_client.update_cover_photo(
            user_id=userId,
            file_path=filePath,
            file_name=fileName,
            content_type=contentType,
            caption=caption,
            media_order=mediaOrder or 1,
            token=token,
        )
        # Build user payload with IDs. URL and signed URL can be queried immediately after.
        user_payload = User(
            id=response.id,
            first_name=response.first_name,
            last_name=response.last_name,
            email=response.email,
            phone=response.phone,
            profile_photo=response.profile_photo or None,
            role=response.role,
            address=response.address,
            latitude=response.latitude,
            longitude=response.longitude,
            bio=response.bio,
            isactive=response.isActive,
            email_verified=response.email_verified,
            phone_verified=response.phone_verified,
            created_at=response.created_at,
            cover_photo_id=getattr(response, 'cover_photo_id', 0),
            profile_photo_id=getattr(response, 'profile_photo_id', 0),
        )
        return user_payload

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
            # Default new follow as pending
            response = user_service_client.follow_user(user_id, following_id, token=token)
            return UserFollower(
                id=response.id,
                follower_id=response.follower_id,
                following_id=response.following_id,
                followee_type=getattr(response, 'followee_type', None),
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

    @strawberry.mutation
    async def update_follow_status(
        self,
        info: Info,
        follower_id: int,
        following_id: int,
        status: str,  # 'active' to accept, 'rejected' to decline
    ) -> UserFollower:
        try:
            # Authorization: only the target user (following_id) can change status
            request = info.context["request"]
            actor = getattr(request.state, "user", None)
            if not actor or int(actor.get("id")) != int(following_id):
                raise REException("FORBIDDEN", "Only the target user can update follow status", "Not allowed").to_graphql_error()

            token = get_token(info)
            resp = user_service_client.update_follow_status(
                follower_id=follower_id,
                following_id=following_id,
                status=status,
                token=token,
            )
            return UserFollower(
                id=resp.id,
                follower_id=resp.follower_id,
                following_id=resp.following_id,
                followee_type=getattr(resp, 'followee_type', None),
                status=resp.status,
                followed_at=resp.followed_at,
            )
        except Exception as e:
            log_msg("error", f"Error updating follow status: {str(e)}")
            raise REException(
                "UPDATE_FOLLOW_STATUS_FAILED",
                "Failed to update follow status",
                str(e),
            ).to_graphql_error()

    @strawberry.mutation
    async def update_user_location(
        self,
        info: Info,
        user_id: int,
        latitude: float,
        longitude: float,
    ) -> User:
        token = get_token(info)
        response = user_service_client.update_user_location(user_id=user_id, latitude=latitude, longitude=longitude, token=token)
        return User(
            id=response.id,
            first_name=response.first_name,
            last_name=response.last_name,
            email=response.email,
            phone=response.phone,
            profile_photo=None,
            role=response.role,
            address=response.address,
            latitude=response.latitude,
            longitude=response.longitude,
            bio=response.bio,
            isactive=response.isActive,
            email_verified=response.email_verified,
            phone_verified=response.phone_verified,
            created_at=response.created_at,
            cover_photo_id=getattr(response, 'cover_photo_id', 0),
            profile_photo_id=getattr(response, 'profile_photo_id', 0),
        )



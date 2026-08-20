import typing
import re
import strawberry
from app.exception.UserException import REException
from app.utils.log_utils import log_msg
from app.clients.user.user_client import user_service_client
from strawberry.types import Info
from graphql import GraphQLError

from app.utils.jwt_utils import get_token
from app.clients.user.user_client import user_service_client
import httpx
import os
import grpc
from app.utils.http_ssl import http_ssl_verify
from app.utils.s3_utils import generate_presigned_get_url_from_url


def _grpc_error_message(exc: Exception) -> str:
    if isinstance(exc, grpc.RpcError):
        details = (exc.details() or "").strip()
        if details:
            return details
        code = exc.code()
        if code == grpc.StatusCode.ALREADY_EXISTS:
            return "already exists"
        if code == grpc.StatusCode.INVALID_ARGUMENT:
            return "invalid argument"
        if code == grpc.StatusCode.NOT_FOUND:
            return "not found"
        return str(exc)
    return str(exc)


@strawberry.type
class User:
    id: str
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
    cover_photo_id: typing.Optional[str] = None
    profile_photo_id: typing.Optional[str] = None
    ratings: typing.List['UserRating'] = strawberry.field(default_factory=list)
    followers_count: int = 0
    following_count: int = 0

    @strawberry.field
    def profilePhotoSignedUrl(self, info: Info) -> typing.Optional[str]:
        try:
            # Prefer value already set by list/detail builders (avoid N+1 get_media)
            existing = getattr(self, "profile_photo_signed_url", None)
            if existing:
                return existing

            candidate: typing.Optional[str] = getattr(self, "profile_photo", None)
            if candidate:
                url = generate_presigned_get_url_from_url(candidate)
                return url or candidate

            if getattr(self, "profile_photo_id", None):
                token = get_token(info)
                media = user_service_client.get_media(
                    media_id=str(self.profile_photo_id), token=token
                )
                candidate = getattr(media, "file_url", None) or getattr(media, "media_url", None)
                if candidate:
                    url = generate_presigned_get_url_from_url(candidate)
                    return url or candidate
            return None
        except Exception:
            return getattr(self, "profile_photo", None)

    @strawberry.field
    def coverPhotoSignedUrl(self, info: Info) -> typing.Optional[str]:
        try:
            existing = getattr(self, "cover_photo_signed_url", None)
            if existing:
                return existing

            candidate: typing.Optional[str] = getattr(self, "cover_photo", None)
            if candidate:
                url = generate_presigned_get_url_from_url(candidate)
                return url or candidate

            if getattr(self, "cover_photo_id", None):
                token = get_token(info)
                media = user_service_client.get_media(media_id=str(self.cover_photo_id), token=token)
                candidate = getattr(media, "file_url", None) or getattr(media, "media_url", None)
                if candidate:
                    url = generate_presigned_get_url_from_url(candidate)
                    return url or candidate
            return None
        except Exception:
            return getattr(self, "cover_photo", None)

    @strawberry.field
    def coverPhotoUrl(self, info: Info) -> typing.Optional[str]:
        try:
            token = get_token(info)
            candidate: typing.Optional[str] = None
            if getattr(self, "cover_photo_id", None):
                media = user_service_client.get_media(media_id=str(self.cover_photo_id), token=token)
                candidate = getattr(media, "file_url", None) or getattr(media, "media_url", None)
            return candidate
        except Exception:
            return None

    @strawberry.field
    def profilePhotoUrl(self, info: Info) -> typing.Optional[str]:
        try:
            token = get_token(info)
            candidate: typing.Optional[str] = getattr(self, "profile_photo", None)
            if (not candidate) and getattr(self, "profile_photo_id", 0):
                media = user_service_client.get_media(media_id=str(self.profile_photo_id), token=token)
                candidate = getattr(media, "file_url", None) or getattr(media, "media_url", None)
            return candidate
        except Exception:
            return getattr(self, "profile_photo", None)

    @strawberry.field
    def userFollowers(self, info: Info) -> typing.List["UserFollower"]:
        try:
            token = get_token(info)
            response = user_service_client.get_user_followers(self.id, token=token)
            follows = [
                _follow_from_proto(follower)
                for follower in getattr(response, "follows", [])
            ]
            return _enrich_follows_with_profiles(follows, "follower_id", token)
        except Exception as e:
            log_msg("error", f"Error fetching nested user followers: {str(e)}")
            return []

    @strawberry.field
    def userFollowing(self, info: Info) -> typing.List["UserFollower"]:
        try:
            token = get_token(info)
            response = user_service_client.get_user_following(self.id, token=token)
            follows = [
                _follow_from_proto(follow)
                for follow in getattr(response, "follows", [])
            ]
            return _enrich_follows_with_profiles(follows, "following_id", token)
        except Exception as e:
            log_msg("error", f"Error fetching nested user following: {str(e)}")
            return []

@strawberry.type
class Media:
    id: str
    context_id: str
    context_type: str
    media_type: str
    media_url: str
    media_order: int
    media_size: typing.Optional[int]
    caption: typing.Optional[str]
    uploaded_at: str

@strawberry.type
class UserRating:
    id: str
    rated_user_id: str
    rated_by_user_id: str
    rating_value: int
    title: typing.Optional[str] = None
    review: typing.Optional[str] = None
    rating_type: typing.Optional[str] = None
    is_anonymous: typing.Optional[bool] = False
    created_at: str
    updated_at: str
    rater_first_name: typing.Optional[str] = None
    rater_last_name: typing.Optional[str] = None
    rater_profile_photo: typing.Optional[str] = None
    rater_profile_photo_signed_url: typing.Optional[str] = None


def _rating_from_proto(rating) -> UserRating:
    return UserRating(
        id=str(rating.id),
        rated_user_id=str(rating.rated_user_id),
        rated_by_user_id=str(
            getattr(rating, "rated_by", "") or getattr(rating, "rated_by_user_id", "")
        ),
        rating_value=int(rating.rating_value),
        title=getattr(rating, "title", None),
        review=getattr(rating, "review", None) or "",
        rating_type=getattr(rating, "rating_type", None),
        is_anonymous=getattr(rating, "is_anonymous", False),
        created_at=str(rating.created_at),
        updated_at=str(rating.updated_at),
    )


def _resolve_user_profile(user_id: str, token: typing.Optional[str]) -> typing.Dict[str, typing.Optional[str]]:
    empty = {
        "first_name": "",
        "last_name": "",
        "role": None,
        "profile_photo": None,
        "profile_photo_signed_url": None,
    }
    try:
        u = user_service_client.get_user(str(user_id), token=token)
    except Exception as e:
        log_msg("warning", f"user profile lookup failed user_id={user_id}: {e}")
        return empty

    first_name = getattr(u, "first_name", None) or ""
    last_name = getattr(u, "last_name", None) or ""
    photo = getattr(u, "profile_photo_url", None) or getattr(u, "profile_photo", None) or None
    if (not photo) and getattr(u, "profile_photo_id", None):
        try:
            media = user_service_client.get_media(
                media_id=str(u.profile_photo_id), token=token
            )
            photo = getattr(media, "file_url", None) or getattr(media, "media_url", None) or None
        except Exception as e:
            log_msg("warning", f"user media lookup failed user_id={user_id}: {e}")
            photo = None

    signed = None
    if photo:
        try:
            signed = generate_presigned_get_url_from_url(photo)
        except Exception as e:
            log_msg("warning", f"user photo sign failed user_id={user_id}: {e}")
            signed = None

    return {
        "first_name": first_name,
        "last_name": last_name,
        "role": getattr(u, "role", None) or None,
        "profile_photo": photo,
        "profile_photo_signed_url": signed or photo,
    }


def _resolve_rater_profile(user_id: str, token: typing.Optional[str]) -> typing.Dict[str, typing.Optional[str]]:
    p = _resolve_user_profile(user_id, token)
    return {
        "first_name": p["first_name"],
        "last_name": p["last_name"],
        "profile_photo": p["profile_photo"],
        "profile_photo_signed_url": p["profile_photo_signed_url"],
    }


def _enrich_ratings_with_raters(
    ratings: typing.List[UserRating],
    token: typing.Optional[str],
) -> typing.List[UserRating]:
    """Batch-resolve rater names/photos once per unique rated_by user."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    unique_ids = sorted({str(r.rated_by_user_id) for r in ratings if r.rated_by_user_id})
    if not unique_ids:
        return ratings

    profiles: typing.Dict[str, typing.Dict[str, typing.Optional[str]]] = {}
    workers = min(8, len(unique_ids))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_resolve_rater_profile, uid, token): uid for uid in unique_ids}
        for fut in as_completed(futures):
            uid = futures[fut]
            try:
                profiles[uid] = fut.result()
            except Exception as e:
                log_msg("warning", f"rater batch resolve failed user_id={uid}: {e}")
                profiles[uid] = {
                    "first_name": "",
                    "last_name": "",
                    "profile_photo": None,
                    "profile_photo_signed_url": None,
                }

    enriched: typing.List[UserRating] = []
    for r in ratings:
        p = profiles.get(str(r.rated_by_user_id)) or {}
        enriched.append(
            UserRating(
                id=r.id,
                rated_user_id=r.rated_user_id,
                rated_by_user_id=r.rated_by_user_id,
                rating_value=r.rating_value,
                title=r.title,
                review=r.review,
                rating_type=r.rating_type,
                is_anonymous=r.is_anonymous,
                created_at=r.created_at,
                updated_at=r.updated_at,
                rater_first_name=p.get("first_name") or None,
                rater_last_name=p.get("last_name") or None,
                rater_profile_photo=p.get("profile_photo"),
                rater_profile_photo_signed_url=p.get("profile_photo_signed_url"),
            )
        )
    return enriched

@strawberry.type
class PresignUploadResponse:
    uploadUrl: str
    publicUrl: str
    key: str

@strawberry.type
class UserFollower:
    id: str
    follower_id: str
    following_id: str
    followee_type: typing.Optional[str] = None
    status: str
    followed_at: str
    user_first_name: typing.Optional[str] = None
    user_last_name: typing.Optional[str] = None
    user_role: typing.Optional[str] = None
    user_profile_photo: typing.Optional[str] = None
    user_profile_photo_signed_url: typing.Optional[str] = None


def _follow_from_proto(
    follow,
    profile: typing.Optional[typing.Dict[str, typing.Optional[str]]] = None,
) -> UserFollower:
    p = profile or {}
    return UserFollower(
        id=str(follow.id),
        follower_id=str(follow.follower_id),
        following_id=str(follow.following_id),
        followee_type=getattr(follow, "follow_type", None) or None,
        status=follow.status,
        followed_at=str(follow.followed_at),
        user_first_name=p.get("first_name") or None,
        user_last_name=p.get("last_name") or None,
        user_role=p.get("role"),
        user_profile_photo=p.get("profile_photo"),
        user_profile_photo_signed_url=p.get("profile_photo_signed_url"),
    )


def _enrich_follows_with_profiles(
    follows: typing.List[UserFollower],
    profile_user_id_attr: str,
    token: typing.Optional[str],
) -> typing.List[UserFollower]:
    """Batch-resolve display names/photos for follower or following user IDs."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    unique_ids = sorted({
        str(getattr(f, profile_user_id_attr))
        for f in follows
        if getattr(f, profile_user_id_attr, None)
    })
    if not unique_ids:
        return follows

    profiles: typing.Dict[str, typing.Dict[str, typing.Optional[str]]] = {}
    workers = min(8, len(unique_ids))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_resolve_user_profile, uid, token): uid for uid in unique_ids
        }
        for fut in as_completed(futures):
            uid = futures[fut]
            try:
                profiles[uid] = fut.result()
            except Exception as e:
                log_msg("warning", f"follow profile batch resolve failed user_id={uid}: {e}")
                profiles[uid] = {
                    "first_name": "",
                    "last_name": "",
                    "role": None,
                    "profile_photo": None,
                    "profile_photo_signed_url": None,
                }

    enriched: typing.List[UserFollower] = []
    for f in follows:
        uid = str(getattr(f, profile_user_id_attr) or "")
        p = profiles.get(uid) or {}
        enriched.append(
            UserFollower(
                id=f.id,
                follower_id=f.follower_id,
                following_id=f.following_id,
                followee_type=f.followee_type,
                status=f.status,
                followed_at=f.followed_at,
                user_first_name=p.get("first_name") or None,
                user_last_name=p.get("last_name") or None,
                user_role=p.get("role"),
                user_profile_photo=p.get("profile_photo"),
                user_profile_photo_signed_url=p.get("profile_photo_signed_url"),
            )
        )
    return enriched


def _follow_from_status_response(
    response,
    follower_id: str,
    following_id: str,
) -> typing.Optional[UserFollower]:
    """Map FollowStatusResponse (no follow row id) to UserFollower for GraphQL."""
    if not response:
        return None
    status = (getattr(response, "status", None) or "").strip()
    is_following = bool(getattr(response, "is_following", False))
    if not status and not is_following:
        return None
    return UserFollower(
        id=str(getattr(response, "id", "") or ""),
        follower_id=str(getattr(response, "follower_id", "") or follower_id),
        following_id=str(getattr(response, "following_id", "") or following_id),
        followee_type=getattr(response, "follow_type", None) or None,
        status=status or ("ACTIVE" if is_following else ""),
        followed_at=str(getattr(response, "followed_at", "") or ""),
    )


@strawberry.type
class OlaSuggestion:
    reference: typing.Optional[str]
    place_id: typing.Optional[str]
    description: typing.Optional[str]
    lat: typing.Optional[float]
    lng: typing.Optional[float]
    types: typing.List[str]


_PIN_RE = re.compile(r"\b(\d{6})\b")
_POI_TYPES = {
    "restaurant", "food", "cafe", "bar", "lodging", "store", "shopping_mall",
    "supermarket", "railway_station", "subway_station", "train_station",
    "bus_station", "transit_station", "airport", "hospital", "school",
    "university", "gym", "bank", "atm", "gas_station", "parking",
    "point_of_interest", "establishment", "premise", "street_address",
    "route", "intersection",
}
_GEO_TYPES = {
    "locality", "sublocality", "sublocality_level_1", "sublocality_level_2",
    "sublocality_level_3", "neighborhood", "political",
    "administrative_area_level_1", "administrative_area_level_2",
    "administrative_area_level_3", "postal_code", "geocode", "colloquial_area",
}


def _format_locality_label(description: str) -> str:
    """Compress verbose India addresses to 'Madhapur, Hyderabad, Telangana-500081'."""
    if not description or not str(description).strip():
        return ""
    parts = [p.strip() for p in str(description).split(",") if p.strip()]
    if parts and parts[-1].lower() in {"india", "भारत"}:
        parts = parts[:-1]

    pincode = None
    cleaned = []
    for part in parts:
        if part.isdigit() and len(part) == 6:
            pincode = part
            continue
        m = re.match(r"^(.*?)\s*[-\s]\s*(\d{6})$", part)
        if m and m.group(1).strip():
            pincode = pincode or m.group(2)
            cleaned.append(m.group(1).strip())
            continue
        only = _PIN_RE.search(part)
        if only and not part.replace(only.group(1), "").replace("-", "").replace(" ", ""):
            pincode = only.group(1)
            continue
        cleaned.append(part)

    geo = cleaned[-3:] if len(cleaned) > 3 else cleaned
    if not geo:
        return pincode or str(description).strip()
    if pincode:
        state = geo[-1]
        head = geo[:-1]
        return ", ".join([*head, f"{state}-{pincode}"])
    return ", ".join(geo)


def _is_poi_heavy(types: typing.List[str]) -> bool:
    lower = [str(t or "").lower() for t in (types or [])]
    has_geo = any(t in _GEO_TYPES for t in lower)
    has_poi = any(t in _POI_TYPES for t in lower)
    return has_poi and not has_geo


@strawberry.type
class Notification:
    id: str
    user_id: str
    title: str
    message: str
    type: str
    read: bool
    created_at: str
    metadata: typing.Optional[str] = None

@strawberry.type
class NotificationsPage:
    notifications: typing.List[Notification]
    total: int


@strawberry.type
class ClearNotificationsResult:
    success: bool
    message: str

def _user_from_proto(u) -> User:
    stats = getattr(u, "statistics", None)
    profile_url = getattr(u, "profile_photo_url", None) or getattr(u, "profile_photo", None) or None
    cover_url = getattr(u, "cover_photo_url", None) or getattr(u, "cover_photo", None) or None
    created = getattr(u, "created_at", None)
    return User(
        id=str(u.id),
        first_name=u.first_name,
        last_name=u.last_name,
        email=u.email,
        phone=u.phone,
        profile_photo=profile_url,
        cover_photo=cover_url,
        profile_photo_signed_url=generate_presigned_get_url_from_url(profile_url) if profile_url else None,
        cover_photo_signed_url=generate_presigned_get_url_from_url(cover_url) if cover_url else None,
        role=u.role or None,
        address=None,
        latitude=getattr(u, "latitude", None) or None,
        longitude=getattr(u, "longitude", None) or None,
        bio=getattr(u, "bio", None) or None,
        isactive=getattr(u, "is_active", getattr(u, "isActive", True)),
        email_verified=u.email_verified,
        phone_verified=u.phone_verified,
        created_at=str(created) if created else "",
        cover_photo_id=str(getattr(u, "cover_photo_id", "") or "") or None,
        profile_photo_id=str(getattr(u, "profile_photo_id", "") or "") or None,
        followers_count=int(getattr(stats, "follower_count", 0) or 0) if stats else 0,
        following_count=int(getattr(stats, "following_count", 0) or 0) if stats else 0,
    )

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

            async with httpx.AsyncClient(timeout=10, verify=http_ssl_verify()) as client:
                resp = await client.get("https://api.olamaps.io/places/v1/autocomplete", params=params)
                resp.raise_for_status()
                data = resp.json() or {}
                predictions = data.get("predictions", [])
                raw: typing.List[OlaSuggestion] = []
                for p in predictions:
                    loc = ((p or {}).get("geometry") or {}).get("location") or {}
                    types = p.get("types") or []
                    desc = p.get("description") or ""
                    raw.append(
                        OlaSuggestion(
                            reference=p.get("reference"),
                            place_id=p.get("place_id"),
                            description=_format_locality_label(desc) or desc,
                            lat=loc.get("lat"),
                            lng=loc.get("lng"),
                            types=types,
                        )
                    )

                geographic = [s for s in raw if not _is_poi_heavy(s.types or [])]
                pool = geographic if geographic else raw

                suggestions: typing.List[OlaSuggestion] = []
                seen = set()
                for s in pool:
                    key = (s.description or "").strip().lower()
                    if not key or key in seen:
                        continue
                    seen.add(key)
                    suggestions.append(s)
                return suggestions
        except httpx.HTTPStatusError as e:
            raise REException("OLA_API_ERROR", "Failed to fetch suggestions", e.response.text).to_graphql_error()
        except Exception as e:
            raise REException("AUTOCOMPLETE_FAILED", "Autocomplete failed", str(e)).to_graphql_error()
    @strawberry.field
    def user(self, info: Info, id: str) -> typing.Optional[User]:
        try:
            log_msg("info", f"Fetching user with ID {id}")
            token = get_token(info)
            response = user_service_client.get_user(id, token=token)

            if response is None or not getattr(response, "success", True):
                raise REException("USER_NOT_FOUND", "User does not exist", "Invalid ID provided")

            ratings_response = user_service_client.get_user_ratings(id, token=token)
            ratings = [
                _rating_from_proto(rating)
                for rating in getattr(ratings_response, "ratings", [])
            ]
            ratings = _enrich_ratings_with_raters(ratings, token)

            user_obj = _user_from_proto(response)
            user_obj.ratings = ratings
            return user_obj

        except Exception as e:
            log_msg("error", f"Error fetching user: {str(e)}")
            raise REException(
                "USER_NOT_FOUND",
                "Failed to fetch user",
                str(e)
            ).to_graphql_error()

    @strawberry.field
    def user_ratings(self, info: Info, user_id: str) -> typing.List[UserRating]:
        try:
            log_msg("info", f"Fetching ratings for user {user_id}")
            token = get_token(info)
            response = user_service_client.get_user_ratings(user_id,token=token)
            ratings = [_rating_from_proto(rating) for rating in response.ratings]
            return _enrich_ratings_with_raters(ratings, token)
        except Exception as e:
            log_msg("error", f"Error fetching user ratings: {str(e)}")
            raise REException(
                "RATINGS_FETCH_FAILED",
                "Failed to fetch user ratings",
                str(e)
            ).to_graphql_error()

    @strawberry.field
    def user_followers(self, info: Info, user_id: str) -> typing.List[UserFollower]:
        try:
            log_msg("info", f"Fetching followers for user {user_id}")
            token = get_token(info)
            response = user_service_client.get_user_followers(user_id, token=token)
            follows = [
                _follow_from_proto(follower)
                for follower in getattr(response, "follows", [])
            ]
            return _enrich_follows_with_profiles(follows, "follower_id", token)
        except Exception as e:
            log_msg("error", f"Error fetching user followers: {str(e)}")
            raise REException(
                "FOLLOWERS_FETCH_FAILED",
                "Failed to fetch user followers",
                str(e)
            ).to_graphql_error()

    @strawberry.field
    def pending_follow_requests(self, info: Info, user_id: str) -> typing.List[UserFollower]:
        try:
            token = get_token(info)
            response = user_service_client.get_pending_follow_requests(user_id, token=token)
            follows = [_follow_from_proto(f) for f in getattr(response, "follows", [])]
            return _enrich_follows_with_profiles(follows, "follower_id", token)
        except Exception as e:
            raise REException(
                "PENDING_REQUESTS_FAILED",
                "Failed to fetch pending follow requests",
                str(e),
            ).to_graphql_error()

    @strawberry.field
    def user_following(self, info: Info, user_id: str) -> typing.List[UserFollower]:
        try:
            log_msg("info", f"Fetching following for user {user_id}")
            token = get_token(info)
            response = user_service_client.get_user_following(user_id, token=token)
            follows = [
                _follow_from_proto(follow)
                for follow in getattr(response, "follows", [])
            ]
            return _enrich_follows_with_profiles(follows, "following_id", token)
        except Exception as e:
            log_msg("error", f"Error fetching user following: {str(e)}")
            raise REException(
                "FOLLOWING_FETCH_FAILED",
                "Failed to fetch user following",
                str(e)
            ).to_graphql_error()

    @strawberry.field
    def check_following_status(self, info: Info, user_id: str, following_id: str) -> typing.Optional[UserFollower]:
        try:
            log_msg("info", f"Checking following status for user {user_id} -> {following_id}")
            token = get_token(info)
            response = user_service_client.check_following_status(
                user_id, following_id, token=token
            )
            return _follow_from_status_response(response, user_id, following_id)
        except Exception as e:
            log_msg("error", f"Error checking following status: {str(e)}")
            raise REException(
                "FOLLOWING_STATUS_CHECK_FAILED",
                "Failed to check following status",
                str(e)
            ).to_graphql_error()

    @strawberry.field
    def media(self, info: Info, mediaId: str) -> typing.Optional[Media]:
        try:
            token = get_token(info)
            response = user_service_client.get_media(media_id=mediaId, token=token)
            if not response or not getattr(response, "id", None):
                return None
            file_url = (
                getattr(response, "file_url", None)
                or getattr(response, "media_url", None)
                or ""
            )
            return Media(
                id=str(response.id),
                context_id=str(
                    getattr(response, "entity_id", None)
                    or getattr(response, "context_id", None)
                    or ""
                ),
                context_type=str(
                    getattr(response, "entity_type", None)
                    or getattr(response, "context_type", None)
                    or ""
                ),
                media_type=str(getattr(response, "media_type", None) or ""),
                media_url=str(file_url),
                media_order=int(getattr(response, "media_order", 0) or 0),
                media_size=int(getattr(response, "file_size", 0) or getattr(response, "media_size", 0) or 0) or None,
                caption=getattr(response, "caption", None),
                uploaded_at=str(getattr(response, "created_at", None) or getattr(response, "uploaded_at", None) or ""),
            )
        except Exception as e:
            log_msg("error", f"Error fetching media: {str(e)}")
            return None

    @strawberry.field
    def users(
        self,
        info: Info,
        search: typing.Optional[str] = "",
        role: typing.Optional[str] = None,
        page: int = 1,
        limit: int = 50,
    ) -> typing.List[User]:
        try:
            token = get_token(info)
            response = user_service_client.search_users(
                search=search or "",
                role=role or "",
                page=page,
                limit=limit,
                token=token,
            )
            # Use shared mapper — UserResponse proto has profile_photo_url, not profile_photo/address.
            return [_user_from_proto(u) for u in getattr(response, "users", []) or []]
        except Exception as e:
            log_msg("error", f"Error listing users: {str(e)}")
            return []

    @strawberry.field
    def suggestedUsers(self, info: Info, userId: str, limit: int = 10) -> typing.List[User]:
        try:
            token = get_token(info)
            response = user_service_client.get_suggested_users(user_id=userId, limit=limit, token=token)
            return [_user_from_proto(u) for u in response.users]
        except Exception as e:
            log_msg("error", f"Error fetching suggested users: {str(e)}")
            return []

    @strawberry.field
    def userNotifications(
        self,
        info: Info,
        userId: str,
        page: int = 1,
        limit: int = 20,
    ) -> NotificationsPage:
        try:
            token = get_token(info)
            response = user_service_client.list_notifications(
                user_id=userId, page=page, limit=limit, token=token
            )
            notifications = [
                Notification(
                    id=n.id,
                    user_id=n.user_id,
                    title=n.title,
                    message=getattr(n, "notification_message", None) or getattr(n, "message", "") or "",
                    type=n.type,
                    read=n.read,
                    created_at=n.created_at,
                    metadata=n.metadata or None,
                )
                for n in response.notifications
            ]
            return NotificationsPage(
                notifications=notifications,
                total=getattr(response, "total_count", 0) or 0,
            )
        except Exception as e:
            log_msg("error", f"Error fetching notifications: {str(e)}")
            raise REException(
                "NOTIFICATIONS_FETCH_FAILED",
                "Failed to fetch notifications",
                str(e),
            ).to_graphql_error()

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
            from uuid import uuid4
            from app.clients.auth.auth_client import auth_service_client

            log_msg("info", f"Creating user {email}")
            token = get_token(info)
            new_user_id = str(uuid4())
            response = user_service_client.create_user(
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone,
                role=role,
                address=address,
                latitude=latitude,
                longitude=longitude,
                bio=bio,
                user_id=new_user_id,
                token=token
            )
            if not getattr(response, "success", True) or not getattr(response, "id", ""):
                raise REException(
                    "USER_CREATION_FAILED",
                    getattr(response, "message", None) or "Failed to create user",
                    getattr(response, "message", None) or "Please try again later",
                ).to_graphql_error()
            auth_service_client.register_credentials(new_user_id, password, "LOCAL")
            return _user_from_proto(response)
        except GraphQLError:
            raise
        except Exception as e:
            error_message = _grpc_error_message(e)
            log_msg("error", f"create_user failed: {error_message}")
            lowered = error_message.lower()
            if isinstance(e, grpc.RpcError) and e.code() == grpc.StatusCode.ALREADY_EXISTS:
                raise REException(
                    "USER_EXISTS",
                    "An account with this email or phone already exists",
                    "Please log in or use different registration details"
                ).to_graphql_error()
            if "already exists" in lowered:
                raise REException(
                    "USER_EXISTS",
                    "An account with this email or phone already exists",
                    "Please log in or use different registration details"
                ).to_graphql_error()
            if "email already registered" in lowered or ("email" in lowered and "already" in lowered):
                raise REException(
                    "EMAIL_EXISTS",
                    "This email address is already registered",
                    "Please use a different email address or try logging in"
                ).to_graphql_error()
            elif "phone_unique" in lowered or "phone" in lowered and "already" in lowered:
                raise REException(
                    "PHONE_EXISTS",
                    "This phone number is already registered",
                    "Please use a different phone number"
                ).to_graphql_error()
            elif "user already exists" in lowered or "credentials already exist" in lowered:
                raise REException(
                    "USER_EXISTS",
                    "An account with these details already exists",
                    "Please log in or use different registration details"
                ).to_graphql_error()
            elif "invalid email format" in lowered:
                raise REException(
                    "INVALID_EMAIL",
                    "Invalid email format",
                    "Please provide a valid email address"
                ).to_graphql_error()
            else:
                raise REException(
                    "USER_CREATION_FAILED",
                    "Failed to create user",
                    error_message or "Please try again later"
                ).to_graphql_error()

    @strawberry.mutation
    async def create_user_rating(
        self,
        info: Info,
        rated_user_id: str,
        rated_by_user_id: str,
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
            rating = _rating_from_proto(response)
            return _enrich_ratings_with_raters([rating], token)[0]
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
        userId: str,
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
        return _user_from_proto(response)

    @strawberry.mutation
    async def updateCoverPhoto(
        self,
        info: Info,
        userId: str,
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
        return _user_from_proto(response)

    @strawberry.mutation
    async def follow_user(
        self,
        info: Info,
        user_id: str,
        following_id: str
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
        follower_id: str,
        following_id: str,
        status: str,  # 'active' to accept, 'rejected' to decline
    ) -> UserFollower:
        try:
            # Authorization: only the target user (following_id) can change status
            request = info.context["request"]
            actor = getattr(request.state, "user", None)
            if not actor or str(actor.get("id")) != str(following_id):
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
        user_id: str,
        latitude: float,
        longitude: float,
    ) -> User:
        token = get_token(info)
        response = user_service_client.update_user_location(user_id=user_id, latitude=latitude, longitude=longitude, token=token)
        return _user_from_proto(response)

    @strawberry.mutation
    async def markNotificationRead(
        self,
        info: Info,
        notificationId: str,
        userId: str,
    ) -> Notification:
        try:
            token = get_token(info)
            response = user_service_client.mark_notification_read(
                notification_id=notificationId,
                user_id=userId,
                token=token,
            )
            return Notification(
                id=response.id,
                user_id=response.user_id,
                title=response.title,
                message=response.message,
                type=response.type,
                read=response.read,
                created_at=response.created_at,
                metadata=response.metadata or None,
            )
        except Exception as e:
            log_msg("error", f"Error marking notification read: {str(e)}")
            raise REException(
                "MARK_NOTIFICATION_FAILED",
                "Failed to mark notification read",
                str(e),
            ).to_graphql_error()

    @strawberry.mutation
    async def clearNotifications(
        self,
        info: Info,
        userId: str,
    ) -> ClearNotificationsResult:
        try:
            token = get_token(info)
            response = user_service_client.clear_notifications(user_id=userId, token=token)
            return ClearNotificationsResult(
                success=bool(getattr(response, "success", False)),
                message=getattr(response, "message", "") or "",
            )
        except Exception as e:
            log_msg("error", f"Error clearing notifications: {str(e)}")
            raise REException(
                "CLEAR_NOTIFICATIONS_FAILED",
                "Failed to clear notifications",
                str(e),
            ).to_graphql_error()

    @strawberry.mutation
    def updateUserRole(self, info: Info, userId: str, role: str) -> User:
        """Admin helper — sets a user's platform role (e.g. ADMIN, AGENT, BUILDER, USER)."""
        try:
            token = get_token(info)
            normalized = (role or "").strip().upper().replace("GENERAL_USER", "USER")
            response = user_service_client.update_user_profile(
                user_id=str(userId),
                role=normalized,
                token=token,
            )
            if not getattr(response, "success", True) and not getattr(response, "id", None):
                raise REException(
                    "ROLE_UPDATE_FAILED",
                    getattr(response, "message", None) or "Failed to update role",
                    getattr(response, "message", None) or "Failed to update role",
                ).to_graphql_error()
            return _user_from_proto(response)
        except REException:
            raise
        except Exception as e:
            log_msg("error", f"Error updating user role: {str(e)}")
            raise REException(
                "ROLE_UPDATE_FAILED",
                "Failed to update role",
                str(e),
            ).to_graphql_error()

    @strawberry.mutation
    async def createNotification(
        self,
        info: Info,
        userId: str,
        title: str,
        message: str,
        type: str = "",
        metadata: typing.Optional[str] = None,
    ) -> Notification:
        try:
            token = get_token(info)
            response = user_service_client.create_notification(
                user_id=userId,
                title=title,
                message=message,
                type=type,
                metadata=metadata or "",
                token=token,
            )
            return Notification(
                id=response.id,
                user_id=response.user_id,
                title=response.title,
                message=response.message,
                type=response.type,
                read=response.read,
                created_at=response.created_at,
                metadata=response.metadata or None,
            )
        except Exception as e:
            log_msg("error", f"Error creating notification: {str(e)}")
            raise REException(
                "CREATE_NOTIFICATION_FAILED",
                "Failed to create notification",
                str(e),
            ).to_graphql_error()


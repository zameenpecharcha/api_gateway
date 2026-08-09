import strawberry
import typing
from typing import List, Optional, Dict
from datetime import datetime
import logging
import json as _json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.clients.post.post_client import post_service_client
from app.clients.user.user_client import user_service_client
from app.clients.property.property_client import property_service_client

from app.utils.jwt_utils import get_token, decode_jwt_token
from app.utils.s3_utils import generate_presigned_get_url_from_url
from strawberry.types import Info
from app.exception.UserException import REException

logger = logging.getLogger(__name__)

# User: @[123:Rohit]   Property: @[p:prop-id:Lake Villa]
_MENTION_RE = re.compile(r"@\[(?:(p):)?([^:\]]+):([^\]]+)\]")


def _viewer_user_id_from_token(token: Optional[str]) -> str:
    if not token:
        return ""
    try:
        payload = decode_jwt_token(token)
        return str(payload.get("user_id") or payload.get("sub") or "").strip()
    except Exception:
        return ""


def _extract_mentioned_user_ids(text: Optional[str]) -> List[str]:
    if not text:
        return []
    ids: List[str] = []
    seen = set()
    for match in _MENTION_RE.finditer(text):
        if match.group(1) == "p":
            continue
        uid = (match.group(2) or "").strip()
        if uid and uid not in seen:
            seen.add(uid)
            ids.append(uid)
    return ids


def _extract_mentioned_property_ids(text: Optional[str]) -> List[str]:
    if not text:
        return []
    ids: List[str] = []
    seen = set()
    for match in _MENTION_RE.finditer(text):
        if match.group(1) != "p":
            continue
        pid = (match.group(2) or "").strip()
        if pid and pid not in seen:
            seen.add(pid)
            ids.append(pid)
    return ids


def _notify_mentioned_users(
    *,
    text: Optional[str],
    author_id: str,
    author_name: str,
    token: Optional[str],
    title: str,
    message: str,
    metadata: str,
) -> None:
    """Best-effort mention notifications — never fail the parent mutation."""
    mentioned = [uid for uid in _extract_mentioned_user_ids(text) if uid != author_id]
    for uid in mentioned:
        try:
            user_service_client.create_notification(
                user_id=uid,
                title=title,
                message=message,
                type="mention",
                metadata=metadata,
                token=token,
            )
        except Exception as e:
            logger.warning(
                "mention notify failed author=%s target=%s err=%s",
                author_id,
                uid,
                e,
            )

    for prop_id in _extract_mentioned_property_ids(text):
        try:
            prop_resp = property_service_client.get_property(prop_id, token=token)
            prop = getattr(prop_resp, "property", None) or prop_resp
            owner_raw = getattr(prop, "user_id", None) or getattr(prop, "userId", None)
            if owner_raw is None:
                continue
            owner_id = str(owner_raw).strip()
            if not owner_id or owner_id == author_id:
                continue
            prop_title = getattr(prop, "title", None) or "your property"
            user_service_client.create_notification(
                user_id=owner_id,
                title="Your property was mentioned",
                message=f"{author_name} mentioned {prop_title}",
                type="mention",
                metadata=_json.dumps(
                    {
                        **(_json.loads(metadata) if metadata else {}),
                        "propertyId": prop_id,
                    }
                ),
                token=token,
            )
        except Exception as e:
            logger.warning(
                "property mention notify failed author=%s property=%s err=%s",
                author_id,
                prop_id,
                e,
            )


def _resolve_user_details(user_id: str, token: Optional[str]) -> dict:
    empty = {
        "firstName": "",
        "lastName": "",
        "email": "",
        "phone": "",
        "role": "",
        "profilePhoto": None,
    }
    try:
        user = user_service_client.get_user(str(user_id), token=token)
        profile_photo = getattr(user, "profile_photo_url", None) or getattr(user, "profile_photo", None) or None
        if (not profile_photo) and getattr(user, "profile_photo_id", 0):
            try:
                media = user_service_client.get_media(
                    media_id=str(user.profile_photo_id), token=token
                )
                profile_photo = getattr(media, "media_url", None) or None
            except Exception as e:
                logger.warning("profile media lookup failed user_id=%s: %s", user_id, e)
        return {
            "firstName": getattr(user, "first_name", "") or "",
            "lastName": getattr(user, "last_name", "") or "",
            "email": getattr(user, "email", "") or "",
            "phone": getattr(user, "phone", "") or "",
            "role": getattr(user, "role", "") or "",
            "profilePhoto": profile_photo or None,
        }
    except Exception as e:
        logger.warning("user details lookup failed user_id=%s: %s", user_id, e)
        return empty


def _batch_user_details(user_ids: List[str], token: Optional[str]) -> Dict[str, dict]:
    unique_ids = [uid for uid in {str(u).strip() for u in user_ids if u}]
    out: Dict[str, dict] = {
        uid: {
            "firstName": "",
            "lastName": "",
            "email": "",
            "phone": "",
            "role": "",
            "profilePhoto": None,
        }
        for uid in unique_ids
    }
    if not unique_ids:
        return out

    workers = min(8, len(unique_ids))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_resolve_user_details, uid, token): uid
            for uid in unique_ids
        }
        for fut in as_completed(futures):
            uid = futures[fut]
            try:
                out[uid] = fut.result()
            except Exception:
                pass
    return out


def _resolve_user_profile_photo(user_id: str, token: Optional[str]) -> Optional[str]:
    return _resolve_user_details(user_id, token).get("profilePhoto")


def _builder_user_ids(token: Optional[str], builder_user_id: Optional[str] = None) -> List[str]:
    if builder_user_id:
        return [str(builder_user_id).strip()]
    try:
        result = user_service_client.list_users(search="", page=1, limit=500, token=token)
        users = getattr(result, "users", None) or []
        return [
            str(u.id)
            for u in users
            if str(getattr(u, "role", "")).upper() == "BUILDER"
        ]
    except Exception as e:
        logger.warning("builder user lookup failed: %s", e)
        return []


def _apply_user_details_to_post(post: dict, users: Dict[str, dict]) -> None:
    details = users.get(str(post["userId"]), {})
    post["userFirstName"] = details.get("firstName", "") or post.get("userFirstName", "")
    post["userLastName"] = details.get("lastName", "") or post.get("userLastName", "")
    post["userEmail"] = details.get("email", "") or post.get("userEmail", "")
    post["userPhone"] = details.get("phone", "") or post.get("userPhone", "")
    post["userRole"] = details.get("role", "") or post.get("userRole", "")
    raw = details.get("profilePhoto")
    post["userProfilePhoto"] = raw
    post["userProfilePhotoSignedUrl"] = _safe_presign(raw)


def _apply_user_details_to_comment(comment: dict, users: Dict[str, dict]) -> None:
    details = users.get(str(comment["userId"]), {})
    comment["userFirstName"] = details.get("firstName", "") or comment.get("userFirstName", "")
    comment["userLastName"] = details.get("lastName", "") or comment.get("userLastName", "")
    comment["userRole"] = details.get("role", "") or comment.get("userRole", "")
    raw = details.get("profilePhoto")
    comment["profilePhoto"] = raw
    comment["profilePhotoSignedUrl"] = _safe_presign(raw)
    for reply in comment.get("replies") or []:
        _apply_user_details_to_comment(reply, users)


def _safe_presign(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        return generate_presigned_get_url_from_url(url) or url
    except Exception as e:
        logger.warning("presign failed for url=%s: %s", str(url)[:80], e)
        return url


def _batch_profile_photos(user_ids: List[str], token: Optional[str]) -> Dict[str, Optional[str]]:
    details = _batch_user_details(user_ids, token)
    return {uid: info.get("profilePhoto") for uid, info in details.items()}


def _enrich_posts_with_users(posts_data: List[dict], token: Optional[str]) -> List[dict]:
    users = _batch_user_details([p["userId"] for p in posts_data], token)
    for post in posts_data:
        _apply_user_details_to_post(post, users)
    return posts_data


def _enrich_posts_with_profile_photos(posts_data: List[dict], token: Optional[str]) -> List[dict]:
    return _enrich_posts_with_users(posts_data, token)


def _posts_from_list_result(result: dict, token: Optional[str]) -> List[dict]:
    posts_data = [p for p in (result.get("posts") or []) if p]
    if posts_data:
        _enrich_posts_with_users(posts_data, token)
    return posts_data


def _enrich_comments_with_users(comments_data: List[dict], token: Optional[str]) -> List[dict]:
    user_ids: List[str] = []
    for comment in comments_data:
        user_ids.append(str(comment["userId"]))
        for reply in comment.get("replies") or []:
            user_ids.append(str(reply["userId"]))
    users = _batch_user_details(user_ids, token)
    for comment in comments_data:
        _apply_user_details_to_comment(comment, users)
    return comments_data


def _enrich_comments_with_profile_photos(comments_data: List[dict], token: Optional[str]) -> List[dict]:
    return _enrich_comments_with_users(comments_data, token)


@strawberry.type
class Comment:
    id: str
    postId: str
    userId: str
    userFirstName: str
    userLastName: str
    userRole: str
    comment: str
    parentCommentId: Optional[str]
    status: str
    addedAt: datetime
    commentedAt: datetime
    replies: List['Comment']
    likeCount: int
    profilePhoto: Optional[str] = None
    profilePhotoSignedUrl: Optional[str] = None
    editedAt: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data: dict):
        if not data:
            return None
        return cls(
            id=data['id'],
            postId=data['postId'],
            userId=data['userId'],
            userFirstName=data.get('userFirstName', ''),
            userLastName=data.get('userLastName', ''),
            userRole=data.get('userRole', ''),
            comment=data['comment'],
            parentCommentId=data.get('parentCommentId'),
            status=data['status'],
            addedAt=data['addedAt'],
            commentedAt=data['commentedAt'],
            replies=[cls.from_dict(reply) for reply in data.get('replies', [])],
            likeCount=data['likeCount'],
            profilePhoto=data.get('profilePhoto'),
            profilePhotoSignedUrl=data.get('profilePhotoSignedUrl'),
            editedAt=data.get('editedAt'),
        )


@strawberry.type
class CommentResponse:
    success: bool
    message: str
    comment: Optional[Comment] = None

    @classmethod
    def from_dict(cls, data: dict, token: Optional[str] = None):
        comment = data.get('comment')
        if token and comment:
            _enrich_comments_with_users([comment], token)
        return cls(
            success=data['success'],
            message=data['message'],
            comment=Comment.from_dict(comment)
        )


@strawberry.type
class PostMedia:
    id: str
    mediaType: str
    mediaUrl: str
    mediaOrder: int
    mediaSize: Optional[int]
    caption: Optional[str]
    uploadedAt: datetime
    signedUrl: Optional[str] = None


@strawberry.input
class PostMediaInput:
    mediaType: Optional[str] = None
    mediaOrder: int
    caption: Optional[str] = None
    filePath: Optional[str] = None
    fileName: Optional[str] = None
    contentType: Optional[str] = None


@strawberry.type
class Post:
    id: str
    userId: str
    userFirstName: str
    userLastName: str
    userEmail: str
    userPhone: str
    userRole: str
    title: str
    content: str
    visibility: str
    propertyType: str
    location: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    price: float
    status: str
    createdAt: datetime
    media: List[PostMedia]
    likeCount: int
    commentCount: int
    userProfilePhoto: Optional[str] = None
    isLiked: bool = False
    userProfilePhotoSignedUrl: Optional[str] = None
    isAnonymous: bool = False
    postCode: Optional[str] = None
    propertyId: Optional[str] = None
    currency: Optional[str] = "INR"
    isPinned: bool = False
    pinnedAt: Optional[datetime] = None
    shareCount: int = 0
    viewCount: int = 0

    @classmethod
    def from_dict(cls, data: dict):
        if not data:
            return None
        media_list = [
            PostMedia(
                id=m['id'],
                mediaType=m['mediaType'],
                mediaUrl=m['mediaUrl'],
                mediaOrder=m['mediaOrder'],
                mediaSize=m.get('mediaSize'),
                caption=m.get('caption'),
                uploadedAt=m['uploadedAt'],
                signedUrl=m.get('signedUrl') or (
                    generate_presigned_get_url_from_url(m['mediaUrl']) if m.get('mediaUrl') else None
                ),
            ) for m in data.get('media', [])
        ]
        photo = data.get('userProfilePhoto')
        signed_photo = data.get('userProfilePhotoSignedUrl')
        if photo and not signed_photo:
            signed_photo = generate_presigned_get_url_from_url(photo)
        return cls(
            id=data['id'],
            userId=data['userId'],
            userFirstName=data.get('userFirstName', ''),
            userLastName=data.get('userLastName', ''),
            userEmail=data.get('userEmail', ''),
            userPhone=data.get('userPhone', ''),
            userRole=data.get('userRole', ''),
            title=data['title'],
            content=data['content'],
            visibility=data['visibility'],
            propertyType=data['propertyType'],
            location=data['location'],
            latitude=data.get('latitude'),
            longitude=data.get('longitude'),
            price=data['price'],
            status=data['status'],
            createdAt=data['createdAt'],
            media=media_list,
            likeCount=data['likeCount'],
            commentCount=data['commentCount'],
            userProfilePhoto=photo,
            isLiked=bool(data.get('isLiked', False)),
            userProfilePhotoSignedUrl=signed_photo,
            isAnonymous=bool(data.get('isAnonymous', False)),
            postCode=data.get('postCode'),
            propertyId=data.get('propertyId'),
            currency=data.get('currency', 'INR'),
            isPinned=bool(data.get('isPinned', False)),
            pinnedAt=data.get('pinnedAt'),
            shareCount=int(data.get('shareCount', 0)),
            viewCount=int(data.get('viewCount', 0)),
        )


@strawberry.type
class PostListPage:
    posts: List[Post]
    totalCount: int
    page: int
    totalPages: int

    @classmethod
    def from_result(cls, result: dict, token: Optional[str]):
        posts_data = _posts_from_list_result(result, token)
        return cls(
            posts=[Post.from_dict(p) for p in posts_data],
            totalCount=int(result.get("totalCount", 0)),
            page=int(result.get("page", 1)),
            totalPages=int(result.get("totalPages", 1)),
        )


@strawberry.type
class PostLikeUser:
    userId: str
    firstName: str
    lastName: str
    userRole: str
    reactionType: str
    likedAt: Optional[datetime] = None


@strawberry.type
class PostLikeListPage:
    likes: List[PostLikeUser]
    totalCount: int
    page: int
    totalPages: int


@strawberry.type
class PostShare:
    id: str
    shareCode: str
    postId: str
    sharedBy: str
    shareType: str
    caption: str
    visibility: str
    createdAt: datetime
    post: Optional[Post] = None


@strawberry.type
class PostShareResponse:
    success: bool
    message: str
    share: Optional[PostShare] = None

    @classmethod
    def from_dict(cls, data: dict, token: Optional[str] = None):
        share = data.get("share")
        if token and share:
            _enrich_shares_with_users([share], token)
        return cls(
            success=data["success"],
            message=data["message"],
            share=_post_share_from_dict(share) if share else None,
        )


def _enrich_shares_with_users(shares_data: List[dict], token: Optional[str]) -> List[dict]:
    embedded_posts = [share["post"] for share in shares_data if share.get("post")]
    if embedded_posts:
        _enrich_posts_with_users(embedded_posts, token)
    return shares_data


def _post_share_from_dict(data: dict) -> PostShare:
    return PostShare(
        id=data["id"],
        shareCode=data.get("shareCode", ""),
        postId=data.get("postId", ""),
        sharedBy=data.get("sharedBy", ""),
        shareType=data.get("shareType", ""),
        caption=data.get("caption", ""),
        visibility=data.get("visibility", ""),
        createdAt=data.get("createdAt") or datetime.utcnow(),
        post=Post.from_dict(data["post"]) if data.get("post") else None,
    )


@strawberry.type
class Report:
    id: str
    reportCode: str
    entityType: str
    entityId: str
    reportedBy: str
    reportedUserId: Optional[str]
    reasonCode: str
    description: str
    status: str
    priority: str
    createdAt: datetime


@strawberry.type
class ReportResponse:
    success: bool
    message: str
    report: Optional[Report] = None


@strawberry.type
class CheckLikeStatusResponse:
    success: bool
    message: str
    isLiked: bool
    reactionType: str


@strawberry.type
class PostResponse:
    success: bool
    message: str
    post: Optional[Post] = None

    @classmethod
    def from_dict(cls, data: dict, token: Optional[str] = None):
        post = data.get('post')
        if token and post:
            _enrich_posts_with_users([post], token)
        return cls(
            success=data['success'],
            message=data['message'],
            post=Post.from_dict(post)
        )


@strawberry.type
class Query:
    @strawberry.field
    def post(self, info: Info, postId: str) -> Optional[Post]:
        logger.debug(f"Query.post called with postId: {postId}")
        token = get_token(info)
        post_data = post_service_client.get_post_data(post_id=postId, token=token)
        if not post_data:
            return None
        _enrich_posts_with_users([post_data], token)
        return Post.from_dict(post_data)

    @strawberry.field
    def postsByUser(self, info: Info, userId: str, page: int = 1, limit: int = 10) -> List[Post]:
        logger.debug(f"Query.postsByUser called with userId: {userId}, page: {page}, limit: {limit}")
        token = get_token(info)
        viewer_user_id = _viewer_user_id_from_token(token)
        result = post_service_client.get_posts_by_user(
            user_id=userId, page=page, limit=limit,
            viewer_user_id=viewer_user_id, token=token
        )
        if not result or not result.get("success"):
            return []
        return [Post.from_dict(p) for p in _posts_from_list_result(result, token)]

    @strawberry.field
    def myPosts(self, info: Info, userId: str, page: int = 1, limit: int = 10) -> PostListPage:
        token = get_token(info)
        result = post_service_client.get_my_posts(user_id=userId, page=page, limit=limit, token=token)
        return PostListPage.from_result(result, token)

    @strawberry.field
    def publicPosts(self, info: Info, page: int = 1, limit: int = 20) -> PostListPage:
        token = get_token(info)
        viewer_user_id = _viewer_user_id_from_token(token)
        result = post_service_client.get_public_posts(
            page=page, limit=limit, viewer_user_id=viewer_user_id, token=token
        )
        return PostListPage.from_result(result, token)

    @strawberry.field
    def propertyPosts(self, info: Info, propertyId: str, page: int = 1, limit: int = 10) -> PostListPage:
        token = get_token(info)
        viewer_user_id = _viewer_user_id_from_token(token)
        result = post_service_client.get_property_posts(
            property_id=propertyId, page=page, limit=limit,
            viewer_user_id=viewer_user_id, token=token
        )
        return PostListPage.from_result(result, token)

    @strawberry.field
    def builderPosts(
        self, info: Info,
        builderUserId: Optional[str] = None,
        page: int = 1,
        limit: int = 10,
    ) -> PostListPage:
        token = get_token(info)
        viewer_user_id = _viewer_user_id_from_token(token)
        if builderUserId:
            result = post_service_client.get_builder_posts(
                builder_user_id=builderUserId,
                page=page, limit=limit,
                viewer_user_id=viewer_user_id, token=token,
            )
        else:
            builder_ids = _builder_user_ids(token)
            if not builder_ids:
                return PostListPage(posts=[], totalCount=0, page=page, totalPages=0)
            result = post_service_client.get_builder_posts(
                page=page, limit=limit,
                viewer_user_id=viewer_user_id,
                user_ids=builder_ids,
                token=token,
            )
        return PostListPage.from_result(result, token)

    @strawberry.field
    def searchPosts(
        self, info: Info,
        propertyType: Optional[str] = None,
        location: Optional[str] = None,
        minPrice: Optional[float] = None,
        maxPrice: Optional[float] = None,
        status: Optional[str] = None,
        query: Optional[str] = None,
        hashtag: Optional[str] = None,
        page: int = 1,
        limit: int = 10
    ) -> List[Post]:
        logger.debug(f"Query.searchPosts called with propertyType: {propertyType}, location: {location}")
        token = get_token(info)
        viewer_user_id = _viewer_user_id_from_token(token)
        try:
            result = post_service_client.search_posts(
                property_type=propertyType,
                location=location,
                min_price=minPrice,
                max_price=maxPrice,
                status=status,
                query=query,
                hashtag=hashtag,
                page=page,
                limit=limit,
                viewer_user_id=viewer_user_id,
                token=token
            )
        except Exception as e:
            logger.error(f"searchPosts gRPC failed: {e}")
            raise REException(
                "POSTS_SEARCH_FAILED",
                "Failed to load posts",
                str(e),
            ).to_graphql_error()

        if not result or not result.get("success"):
            msg = result.get("message") if result else "No posts returned"
            logger.error(f"searchPosts unsuccessful: {msg}")
            raise REException(
                "POSTS_SEARCH_FAILED",
                "Failed to load posts",
                msg,
            ).to_graphql_error()

        posts = [Post.from_dict(p) for p in _posts_from_list_result(result, token)]
        logger.debug(f"Returning {len(posts)} posts")
        return posts

    @strawberry.field
    def trendingPosts(self, info: Info, limit: int = 10) -> List[Post]:
        token = get_token(info)
        viewer_user_id = _viewer_user_id_from_token(token)
        try:
            result = post_service_client.trending_posts(
                limit=limit, viewer_user_id=viewer_user_id, token=token
            )
        except Exception as e:
            logger.warning("trendingPosts failed: %s", e)
            return []
        if not result or not result.get("success"):
            return []
        try:
            return [Post.from_dict(p) for p in _posts_from_list_result(result, token)]
        except Exception as e:
            logger.warning("trendingPosts map failed: %s", e)
            return []

    @strawberry.field
    def postLikes(self, info: Info, postId: str, page: int = 1, limit: int = 20) -> PostLikeListPage:
        token = get_token(info)
        result = post_service_client.get_post_likes(post_id=postId, page=page, limit=limit, token=token)
        likes_data = [
            {
                "userId": like["userId"],
                "firstName": like.get("firstName", ""),
                "lastName": like.get("lastName", ""),
                "userRole": like.get("userRole", ""),
                "reactionType": like.get("reactionType", "LIKE"),
                "likedAt": like.get("likedAt"),
            }
            for like in (result.get("likes") or [])
        ]
        users = _batch_user_details([like["userId"] for like in likes_data], token)
        for like in likes_data:
            details = users.get(str(like["userId"]), {})
            like["firstName"] = details.get("firstName", "") or like.get("firstName", "")
            like["lastName"] = details.get("lastName", "") or like.get("lastName", "")
            like["userRole"] = details.get("role", "") or like.get("userRole", "")
        likes = [
            PostLikeUser(
                userId=like["userId"],
                firstName=like.get("firstName", ""),
                lastName=like.get("lastName", ""),
                userRole=like.get("userRole", ""),
                reactionType=like.get("reactionType", "LIKE"),
                likedAt=like.get("likedAt"),
            )
            for like in likes_data
        ]
        return PostLikeListPage(
            likes=likes,
            totalCount=int(result.get("totalCount", 0)),
            page=int(result.get("page", 1)),
            totalPages=int(result.get("totalPages", 1)),
        )

    @strawberry.field
    def checkLikeStatus(self, info: Info, postId: str, userId: str) -> CheckLikeStatusResponse:
        token = get_token(info)
        result = post_service_client.check_like_status(post_id=postId, user_id=userId, token=token)
        return CheckLikeStatusResponse(
            success=bool(result.get("success")),
            message=result.get("message", ""),
            isLiked=bool(result.get("isLiked")),
            reactionType=result.get("reactionType", ""),
        )

    @strawberry.field
    def postComments(
        self, info: Info,
        postId: str,
        page: int = 1,
        limit: int = 10
    ) -> List[Comment]:
        logger.debug(f"Query.postComments called with postId: {postId}")
        token = get_token(info)
        result = post_service_client.get_comments(post_id=postId, page=page, limit=limit, token=token)

        if not result.get("success"):
            return []

        comments_data = result.get("comments") or []
        _enrich_comments_with_users(comments_data, token)
        return [Comment.from_dict(comment) for comment in comments_data if comment]

    @strawberry.field
    def comment(self, info: Info, commentId: str) -> Optional[Comment]:
        token = get_token(info)
        result = post_service_client.get_comment(comment_id=commentId, token=token)
        if not result.get("success") or not result.get("comment"):
            return None
        comments_data = [result["comment"]]
        _enrich_comments_with_users(comments_data, token)
        return Comment.from_dict(comments_data[0])

    @strawberry.field
    def commentReplies(self, info: Info, commentId: str, page: int = 1, limit: int = 10) -> List[Comment]:
        token = get_token(info)
        result = post_service_client.get_replies(comment_id=commentId, page=page, limit=limit, token=token)
        if not result.get("success"):
            return []
        comments_data = result.get("comments") or []
        _enrich_comments_with_users(comments_data, token)
        return [Comment.from_dict(c) for c in comments_data if c]

    @strawberry.field
    def myReports(self, info: Info, reportedBy: str, page: int = 1, limit: int = 20) -> List[Report]:
        token = get_token(info)
        result = post_service_client.get_my_reports(reported_by=reportedBy, page=page, limit=limit, token=token)
        reports = []
        for r in result.get("reports") or []:
            if not r:
                continue
            reports.append(Report(
                id=r["id"],
                reportCode=r.get("reportCode", ""),
                entityType=r.get("entityType", ""),
                entityId=r.get("entityId", ""),
                reportedBy=r.get("reportedBy", ""),
                reportedUserId=r.get("reportedUserId"),
                reasonCode=r.get("reasonCode", ""),
                description=r.get("description", ""),
                status=r.get("status", ""),
                priority=r.get("priority", ""),
                createdAt=r.get("createdAt") or datetime.utcnow(),
            ))
        return reports

    @strawberry.field
    def sharedPosts(self, info: Info, userId: str, page: int = 1, limit: int = 10) -> List[PostShare]:
        token = get_token(info)
        result = post_service_client.get_shared_posts(user_id=userId, page=page, limit=limit, token=token)
        shares_data = [s for s in (result.get("shares") or []) if s]
        _enrich_shares_with_users(shares_data, token)
        return [_post_share_from_dict(s) for s in shares_data]


@strawberry.type
class MediaResponse:
    success: bool
    message: str

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            success=data['success'],
            message=data['message']
        )


@strawberry.type
class Mutation:
    @strawberry.mutation
    def createPost(
        self, info: Info,
        userId: str,
        title: str,
        content: str,
        visibility: str,
        propertyType: str,
        location: str,
        price: float,
        status: str,
        latitude: typing.Optional[float] = None,
        longitude: typing.Optional[float] = None,
        propertyId: typing.Optional[str] = None,
        currency: typing.Optional[str] = "INR",
        isAnonymous: bool = False,
        media: typing.Optional[typing.List[PostMediaInput]] = None
    ) -> PostResponse:
        logger.debug(f"Mutation.createPost called with userId: {userId}, title: {title}")
        token = get_token(info)
        result = post_service_client.create_post(
            user_id=userId,
            title=title,
            content=content,
            visibility=visibility,
            property_type=propertyType,
            location=location,
            latitude=latitude,
            longitude=longitude,
            price=price,
            status=status,
            property_id=propertyId,
            currency=currency,
            is_anonymous=isAnonymous,
            media=media or [],
            token=token
        )
        logger.debug(f"CreatePost result: {result}")
        if result.get("success"):
            post_obj = result.get("post") or {}
            post_id = post_obj.get("id") if isinstance(post_obj, dict) else None
            author_name = "Someone"
            try:
                author = user_service_client.get_user(str(userId), token=token)
                first = getattr(author, "first_name", "") or ""
                last = getattr(author, "last_name", "") or ""
                author_name = f"{first} {last}".strip() or author_name
            except Exception:
                pass
            _notify_mentioned_users(
                text=content,
                author_id=str(userId),
                author_name=author_name,
                token=token,
                title="You were mentioned",
                message=f"{author_name} mentioned you in a post: {title}",
                metadata=_json.dumps({"postId": post_id, "postTitle": title}),
            )
        return PostResponse.from_dict(result, token=token)

    @strawberry.mutation
    def updatePost(
        self, info: Info,
        postId: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        visibility: Optional[str] = None,
        propertyType: Optional[str] = None,
        location: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        price: Optional[float] = None,
        status: Optional[str] = None
    ) -> PostResponse:
        logger.debug(f"Mutation.updatePost called with postId: {postId}")
        token = get_token(info)
        result = post_service_client.update_post(
            post_id=postId,
            title=title,
            content=content,
            visibility=visibility,
            property_type=propertyType,
            location=location,
            latitude=latitude,
            longitude=longitude,
            price=price,
            status=status,
            token=token
        )
        return PostResponse.from_dict(result, token=token)

    @strawberry.mutation
    def deletePost(self, info: Info, postId: str) -> PostResponse:
        logger.debug(f"Mutation.deletePost called with postId: {postId}")
        token = get_token(info)
        result = post_service_client.delete_post(post_id=postId, token=token)
        return PostResponse.from_dict(result, token=token)

    @strawberry.mutation
    def likePost(self, info: Info, postId: str, userId: str, reactionType: Optional[str] = "LIKE") -> PostResponse:
        logger.debug(f"Mutation.likePost called with postId: {postId}, userId: {userId}")
        token = get_token(info)
        result = post_service_client.like_post(
            post_id=postId, user_id=userId, reaction_type=reactionType or "LIKE", token=token
        )
        return PostResponse.from_dict(result, token=token)

    @strawberry.mutation
    def unlikePost(self, info: Info, postId: str, userId: str) -> PostResponse:
        logger.debug(f"Mutation.unlikePost called with postId: {postId}, userId: {userId}")
        token = get_token(info)
        result = post_service_client.unlike_post(post_id=postId, user_id=userId, token=token)
        return PostResponse.from_dict(result, token=token)

    @strawberry.mutation
    def createComment(
        self, info: Info,
        postId: str,
        userId: str,
        comment: str,
        parentCommentId: Optional[str] = None
    ) -> CommentResponse:
        logger.debug(f"Mutation.createComment called with postId: {postId}, userId: {userId}")
        token = get_token(info)
        result = post_service_client.create_comment(
            post_id=postId,
            user_id=userId,
            comment=comment,
            parent_comment_id=parentCommentId,
            token=token
        )
        logger.debug(f"CreateComment result: {result}")
        if result.get("success"):
            author_name = "Someone"
            try:
                author = user_service_client.get_user(str(userId), token=token)
                first = getattr(author, "first_name", "") or ""
                last = getattr(author, "last_name", "") or ""
                author_name = f"{first} {last}".strip() or author_name
            except Exception:
                pass
            comment_obj = result.get("comment") or {}
            comment_id = comment_obj.get("id") if isinstance(comment_obj, dict) else None
            _notify_mentioned_users(
                text=comment,
                author_id=str(userId),
                author_name=author_name,
                token=token,
                title="You were mentioned",
                message=f"{author_name} mentioned you in a comment",
                metadata=_json.dumps({"postId": postId, "commentId": comment_id}),
            )
        return CommentResponse.from_dict(result, token=token)

    @strawberry.mutation
    def updateComment(
        self, info: Info,
        commentId: str,
        comment: Optional[str] = None,
        status: Optional[str] = None
    ) -> CommentResponse:
        logger.debug(f"Mutation.updateComment called with commentId: {commentId}")
        token = get_token(info)
        result = post_service_client.update_comment(
            comment_id=commentId,
            comment=comment,
            status=status,
            token=token
        )
        return CommentResponse.from_dict(result, token=token)

    @strawberry.mutation
    def deleteComment(
        self, info: Info,
        commentId: str
    ) -> CommentResponse:
        logger.debug(f"Mutation.deleteComment called with commentId: {commentId}")
        token = get_token(info)
        result = post_service_client.delete_comment(comment_id=commentId, token=token)
        return CommentResponse.from_dict(result, token=token)

    @strawberry.mutation
    def likeComment(
        self, info: Info,
        commentId: str,
        userId: str,
        reactionType: Optional[str] = "LIKE",
    ) -> CommentResponse:
        logger.debug(f"Mutation.likeComment called with commentId: {commentId}, userId: {userId}")
        token = get_token(info)
        result = post_service_client.like_comment(
            comment_id=commentId,
            user_id=userId,
            reaction_type=reactionType or "LIKE",
            token=token
        )
        return CommentResponse.from_dict(result, token=token)

    @strawberry.mutation
    def unlikeComment(
        self, info: Info,
        commentId: str,
        userId: str
    ) -> CommentResponse:
        logger.debug(f"Mutation.unlikeComment called with commentId: {commentId}, userId: {userId}")
        token = get_token(info)
        result = post_service_client.unlike_comment(
            comment_id=commentId,
            user_id=userId,
            token=token
        )
        return CommentResponse.from_dict(result, token=token)

    @strawberry.mutation
    def addPostMedia(
        self, info: Info,
        postId: str,
        media: List[PostMediaInput],
        uploadedBy: Optional[str] = None,
    ) -> PostResponse:
        logger.debug(f"Mutation.addPostMedia called with postId: {postId}")
        token = get_token(info)
        result = post_service_client.add_post_media(
            post_id=postId,
            media=media,
            uploaded_by=uploadedBy or "",
            token=token
        )
        return PostResponse.from_dict(result, token=token)

    @strawberry.mutation
    def deletePostMedia(
        self, info: Info,
        mediaId: str
    ) -> MediaResponse:
        logger.debug(f"Mutation.deletePostMedia called with mediaId: {mediaId}")
        token = get_token(info)
        result = post_service_client.delete_post_media(media_id=mediaId, token=token)
        return MediaResponse.from_dict(result)

    @strawberry.mutation
    def pinPost(self, info: Info, postId: str, userId: str) -> PostResponse:
        token = get_token(info)
        return PostResponse.from_dict(post_service_client.pin_post(postId, userId, token=token), token=token)

    @strawberry.mutation
    def unpinPost(self, info: Info, postId: str, userId: str) -> PostResponse:
        token = get_token(info)
        return PostResponse.from_dict(post_service_client.unpin_post(postId, userId, token=token), token=token)

    @strawberry.mutation
    def archivePost(self, info: Info, postId: str, userId: str) -> PostResponse:
        token = get_token(info)
        return PostResponse.from_dict(post_service_client.archive_post(postId, userId, token=token), token=token)

    @strawberry.mutation
    def restoreArchivedPost(self, info: Info, postId: str, userId: str) -> PostResponse:
        token = get_token(info)
        return PostResponse.from_dict(post_service_client.restore_archived_post(postId, userId, token=token), token=token)

    @strawberry.mutation
    def replyComment(
        self, info: Info,
        postId: str,
        userId: str,
        comment: str,
        parentCommentId: str,
    ) -> CommentResponse:
        token = get_token(info)
        result = post_service_client.reply_comment(
            post_id=postId, user_id=userId, comment=comment,
            parent_comment_id=parentCommentId, token=token,
        )
        return CommentResponse.from_dict(result, token=token)

    @strawberry.mutation
    def reportComment(
        self, info: Info,
        commentId: str,
        reportedBy: str,
        reportedUserId: Optional[str] = None,
        reasonCode: Optional[str] = None,
        description: Optional[str] = None,
    ) -> ReportResponse:
        token = get_token(info)
        result = post_service_client.report_comment(
            comment_id=commentId, reported_by=reportedBy,
            reported_user_id=reportedUserId or "",
            reason_code=reasonCode or "", description=description or "",
            token=token,
        )
        report = result.get("report")
        return ReportResponse(
            success=bool(result.get("success")),
            message=result.get("message", ""),
            report=Report(
                id=report["id"], reportCode=report.get("reportCode", ""),
                entityType=report.get("entityType", ""), entityId=report.get("entityId", ""),
                reportedBy=report.get("reportedBy", ""), reportedUserId=report.get("reportedUserId"),
                reasonCode=report.get("reasonCode", ""), description=report.get("description", ""),
                status=report.get("status", ""), priority=report.get("priority", ""),
                createdAt=report.get("createdAt") or datetime.utcnow(),
            ) if report else None,
        )

    @strawberry.mutation
    def sharePost(
        self, info: Info,
        postId: str,
        sharedBy: str,
        shareType: Optional[str] = "SHARE",
        caption: Optional[str] = "",
        visibility: Optional[str] = "PUBLIC",
    ) -> PostShareResponse:
        token = get_token(info)
        result = post_service_client.share_post(
            post_id=postId, shared_by=sharedBy, share_type=shareType or "SHARE",
            caption=caption or "", visibility=visibility or "PUBLIC", token=token,
        )
        return PostShareResponse.from_dict(result, token=token)

    @strawberry.mutation
    def deleteSharedPost(self, info: Info, shareId: str, userId: str) -> MediaResponse:
        token = get_token(info)
        result = post_service_client.delete_shared_post(share_id=shareId, user_id=userId, token=token)
        return MediaResponse.from_dict(result)

    @strawberry.mutation
    def reportPost(
        self, info: Info,
        postId: str,
        reportedBy: str,
        reportedUserId: Optional[str] = None,
        reasonCode: Optional[str] = None,
        description: Optional[str] = None,
    ) -> ReportResponse:
        token = get_token(info)
        result = post_service_client.report_post(
            post_id=postId, reported_by=reportedBy,
            reported_user_id=reportedUserId or "",
            reason_code=reasonCode or "", description=description or "",
            token=token,
        )
        report = result.get("report")
        return ReportResponse(
            success=bool(result.get("success")),
            message=result.get("message", ""),
            report=Report(
                id=report["id"], reportCode=report.get("reportCode", ""),
                entityType=report.get("entityType", ""), entityId=report.get("entityId", ""),
                reportedBy=report.get("reportedBy", ""), reportedUserId=report.get("reportedUserId"),
                reasonCode=report.get("reasonCode", ""), description=report.get("description", ""),
                status=report.get("status", ""), priority=report.get("priority", ""),
                createdAt=report.get("createdAt") or datetime.utcnow(),
            ) if report else None,
        )

    @strawberry.mutation
    def reportProperty(
        self, info: Info,
        propertyId: str,
        reportedBy: str,
        reportedUserId: Optional[str] = None,
        reasonCode: Optional[str] = None,
        description: Optional[str] = None,
    ) -> ReportResponse:
        token = get_token(info)
        result = post_service_client.report_property(
            property_id=propertyId, reported_by=reportedBy,
            reported_user_id=reportedUserId or "",
            reason_code=reasonCode or "", description=description or "",
            token=token,
        )
        report = result.get("report")
        return ReportResponse(
            success=bool(result.get("success")),
            message=result.get("message", ""),
            report=Report(
                id=report["id"], reportCode=report.get("reportCode", ""),
                entityType=report.get("entityType", ""), entityId=report.get("entityId", ""),
                reportedBy=report.get("reportedBy", ""), reportedUserId=report.get("reportedUserId"),
                reasonCode=report.get("reasonCode", ""), description=report.get("description", ""),
                status=report.get("status", ""), priority=report.get("priority", ""),
                createdAt=report.get("createdAt") or datetime.utcnow(),
            ) if report else None,
        )

    @strawberry.mutation
    def reportUser(
        self, info: Info,
        userId: str,
        reportedBy: str,
        reasonCode: Optional[str] = None,
        description: Optional[str] = None,
    ) -> ReportResponse:
        token = get_token(info)
        result = post_service_client.report_user(
            user_id=userId, reported_by=reportedBy,
            reason_code=reasonCode or "", description=description or "",
            token=token,
        )
        report = result.get("report")
        return ReportResponse(
            success=bool(result.get("success")),
            message=result.get("message", ""),
            report=Report(
                id=report["id"], reportCode=report.get("reportCode", ""),
                entityType=report.get("entityType", ""), entityId=report.get("entityId", ""),
                reportedBy=report.get("reportedBy", ""), reportedUserId=report.get("reportedUserId"),
                reasonCode=report.get("reasonCode", ""), description=report.get("description", ""),
                status=report.get("status", ""), priority=report.get("priority", ""),
                createdAt=report.get("createdAt") or datetime.utcnow(),
            ) if report else None,
        )

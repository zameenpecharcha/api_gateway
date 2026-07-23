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


def _viewer_user_id_from_token(token: Optional[str]) -> int:
    if not token:
        return 0
    try:
        payload = decode_jwt_token(token)
        return int(payload.get("user_id") or payload.get("sub") or 0)
    except Exception:
        return 0


def _extract_mentioned_user_ids(text: Optional[str]) -> List[int]:
    if not text:
        return []
    ids: List[int] = []
    seen = set()
    for match in _MENTION_RE.finditer(text):
        if match.group(1) == "p":
            continue
        try:
            uid = int(match.group(2))
        except (TypeError, ValueError):
            continue
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
    author_id: int,
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
            owner_id = int(owner_raw)
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


def _resolve_user_profile_photo(user_id: int, token: Optional[str]) -> Optional[str]:
    try:
        user = user_service_client.get_user(int(user_id), token=token)
        candidate = getattr(user, "profile_photo", None) or None
        if (not candidate) and getattr(user, "profile_photo_id", 0):
            try:
                media = user_service_client.get_media(
                    media_id=int(user.profile_photo_id), token=token
                )
                candidate = getattr(media, "media_url", None) or None
            except Exception as e:
                logger.warning("profile media lookup failed user_id=%s: %s", user_id, e)
                candidate = None
        return candidate or None
    except Exception as e:
        logger.warning("profile photo lookup failed user_id=%s: %s", user_id, e)
        return None


def _safe_presign(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        return generate_presigned_get_url_from_url(url) or url
    except Exception as e:
        logger.warning("presign failed for url=%s: %s", str(url)[:80], e)
        return url


def _batch_profile_photos(user_ids: List[int], token: Optional[str]) -> Dict[int, Optional[str]]:
    """One lookup per unique author (parallel), instead of per post."""
    unique_ids = [uid for uid in {int(u) for u in user_ids if u}]
    out: Dict[int, Optional[str]] = {uid: None for uid in unique_ids}
    if not unique_ids:
        return out

    workers = min(8, len(unique_ids))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_resolve_user_profile_photo, uid, token): uid
            for uid in unique_ids
        }
        for fut in as_completed(futures):
            uid = futures[fut]
            try:
                out[uid] = fut.result()
            except Exception:
                out[uid] = None
    return out


def _media_dict_from_grpc(m) -> dict:
    uploaded = getattr(m, "uploaded_at", None)
    media_url = getattr(m, "media_url", None)
    return {
        "id": m.id,
        "mediaType": m.media_type,
        "mediaUrl": media_url,
        "mediaOrder": m.media_order,
        "mediaSize": getattr(m, "media_size", None),
        "caption": getattr(m, "caption", "") or "",
        "uploadedAt": datetime.fromtimestamp(uploaded) if uploaded else datetime.utcnow(),
        "signedUrl": generate_presigned_get_url_from_url(media_url) if media_url else None,
    }


def _post_dict_from_grpc(post) -> dict:
    return {
        "id": post.id,
        "userId": post.user_id,
        "userFirstName": getattr(post, "user_first_name", "") or "",
        "userLastName": getattr(post, "user_last_name", "") or "",
        "userEmail": getattr(post, "user_email", "") or "",
        "userPhone": getattr(post, "user_phone", "") or "",
        "userRole": getattr(post, "user_role", "") or "",
        "title": post.title,
        "content": post.content,
        "visibility": post.visibility,
        "propertyType": getattr(post, "type", "") or "",
        "location": post.location,
        "latitude": getattr(post, "latitude", None),
        "longitude": getattr(post, "longitude", None),
        "price": post.price,
        "status": post.status,
        "createdAt": datetime.fromtimestamp(post.created_at) if post.created_at else datetime.utcnow(),
        "media": [_media_dict_from_grpc(m) for m in post.media],
        "likeCount": post.like_count,
        "commentCount": post.comment_count,
        "isLiked": bool(getattr(post, "is_liked", False)),
    }


def _enrich_posts_with_profile_photos(posts_data: List[dict], token: Optional[str]) -> List[dict]:
    photos = _batch_profile_photos([p["userId"] for p in posts_data], token)
    for p in posts_data:
        raw = photos.get(int(p["userId"]))
        p["userProfilePhoto"] = raw
        p["userProfilePhotoSignedUrl"] = _safe_presign(raw)
    return posts_data


def _apply_photo_to_comment_dict(comment: dict, photos: Dict[int, Optional[str]]) -> None:
    raw = photos.get(int(comment["userId"]))
    comment["profilePhoto"] = raw
    comment["profilePhotoSignedUrl"] = _safe_presign(raw)
    for reply in comment.get("replies") or []:
        reply_raw = photos.get(int(reply["userId"]))
        reply["profilePhoto"] = reply_raw
        reply["profilePhotoSignedUrl"] = _safe_presign(reply_raw)


def _enrich_comments_with_profile_photos(comments_data: List[dict], token: Optional[str]) -> List[dict]:
    user_ids: List[int] = []
    for c in comments_data:
        user_ids.append(int(c["userId"]))
        for r in c.get("replies") or []:
            user_ids.append(int(r["userId"]))
    photos = _batch_profile_photos(user_ids, token)
    for c in comments_data:
        _apply_photo_to_comment_dict(c, photos)
    return comments_data


@strawberry.type
class Comment:
    id: int
    postId: int
    userId: int
    userFirstName: str
    userLastName: str
    userRole: str
    comment: str
    parentCommentId: Optional[int]
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
    def from_dict(cls, data: dict):
        return cls(
            success=data['success'],
            message=data['message'],
            comment=Comment.from_dict(data.get('comment'))
        )


@strawberry.type
class PostMedia:
    id: int
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
    id: int
    userId: int
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
        )


@strawberry.type
class PostResponse:
    success: bool
    message: str
    post: Optional[Post] = None

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            success=data['success'],
            message=data['message'],
            post=Post.from_dict(data.get('post'))
        )


@strawberry.type
class Query:
    @strawberry.field
    def post(self, info: Info, postId: int) -> Optional[Post]:
        logger.debug(f"Query.post called with postId: {postId}")
        token = get_token(info)
        result = post_service_client.get_post(post_id=postId, token=token)
        if result and result.success and result.post:
            post_data = _post_dict_from_grpc(result.post)
            _enrich_posts_with_profile_photos([post_data], token)
            return Post.from_dict(post_data)
        return None

    @strawberry.field
    def postsByUser(self, info: Info, userId: int, page: int = 1, limit: int = 10) -> List[Post]:
        logger.debug(f"Query.postsByUser called with userId: {userId}, page: {page}, limit: {limit}")
        token = get_token(info)
        viewer_user_id = _viewer_user_id_from_token(token)
        result = post_service_client.get_posts_by_user(
            user_id=userId, page=page, limit=limit,
            viewer_user_id=viewer_user_id, token=token
        )

        if not result:
            logger.error("No result returned")
            return []

        posts_data = [_post_dict_from_grpc(post) for post in result]
        _enrich_posts_with_profile_photos(posts_data, token)
        return [Post.from_dict(p) for p in posts_data]

    @strawberry.field
    def searchPosts(
        self, info: Info,
        propertyType: Optional[str] = None,
        location: Optional[str] = None,
        minPrice: Optional[float] = None,
        maxPrice: Optional[float] = None,
        status: Optional[str] = None,
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

        if not result or not result.success:
            msg = getattr(result, "message", None) or "No posts returned"
            logger.error(f"searchPosts unsuccessful: {msg}")
            raise REException(
                "POSTS_SEARCH_FAILED",
                "Failed to load posts",
                msg,
            ).to_graphql_error()

        posts_data = [_post_dict_from_grpc(post) for post in result.posts]
        _enrich_posts_with_profile_photos(posts_data, token)
        posts = [Post.from_dict(post) for post in posts_data]
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
            # Sidebar widget — never hard-fail the home page (often races with searchPosts)
            logger.warning("trendingPosts failed: %s", e)
            return []
        if not result or not result.success:
            return []
        try:
            posts_data = [_post_dict_from_grpc(post) for post in result.posts]
            # Sidebar only needs id/title/counts — skip S3 + user-service fan-out
            return [Post.from_dict(p) for p in posts_data]
        except Exception as e:
            logger.warning("trendingPosts map failed: %s", e)
            return []

    @strawberry.field
    def postComments(
        self, info: Info,
        postId: int,
        page: int = 1,
        limit: int = 10
    ) -> List[Comment]:
        logger.debug(f"Query.postComments called with postId: {postId}")
        token = get_token(info)
        result = post_service_client.get_comments(post_id=postId, page=page, limit=limit, token=token)

        if not result or not result.success:
            return []

        comments_data = []
        for comment in result.comments:
            comment_dict = {
                'id': comment.id,
                'postId': comment.post_id,
                'userId': comment.user_id,
                'userFirstName': comment.user_first_name,
                'userLastName': comment.user_last_name,
                'userRole': comment.user_role,
                'comment': comment.comment,
                'parentCommentId': comment.parent_comment_id if comment.parent_comment_id != 0 else None,
                'status': comment.status,
                'addedAt': datetime.fromtimestamp(comment.added_at),
                'commentedAt': datetime.fromtimestamp(comment.commented_at),
                'editedAt': datetime.fromtimestamp(comment.edited_at) if getattr(comment, 'edited_at', 0) else None,
                'replies': [
                    {
                        'id': r.id,
                        'postId': r.post_id,
                        'userId': r.user_id,
                        'userFirstName': r.user_first_name,
                        'userLastName': r.user_last_name,
                        'userRole': r.user_role,
                        'comment': r.comment,
                        'parentCommentId': r.parent_comment_id,
                        'status': r.status,
                        'addedAt': datetime.fromtimestamp(r.added_at),
                        'commentedAt': datetime.fromtimestamp(r.commented_at),
                        'editedAt': datetime.fromtimestamp(r.edited_at) if getattr(r, 'edited_at', 0) else None,
                        'replies': [],
                        'likeCount': r.like_count
                    } for r in comment.replies
                ],
                'likeCount': comment.like_count
            }
            comments_data.append(comment_dict)

        _enrich_comments_with_profile_photos(comments_data, token)
        return [Comment.from_dict(comment) for comment in comments_data]


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
        userId: int,
        title: str,
        content: str,
        visibility: str,
        propertyType: str,
        location: str,
        price: float,
        status: str,
        latitude: typing.Optional[float] = None,
        longitude: typing.Optional[float] = None,
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
            media=media or [],
            token=token
        )
        logger.debug(f"CreatePost result: {result}")
        if result.get("success"):
            post_obj = result.get("post") or {}
            post_id = post_obj.get("id") if isinstance(post_obj, dict) else None
            author_name = "Someone"
            try:
                author = user_service_client.get_user(int(userId), token=token)
                first = getattr(author, "first_name", "") or ""
                last = getattr(author, "last_name", "") or ""
                author_name = f"{first} {last}".strip() or author_name
            except Exception:
                pass
            _notify_mentioned_users(
                text=content,
                author_id=int(userId),
                author_name=author_name,
                token=token,
                title="You were mentioned",
                message=f"{author_name} mentioned you in a post: {title}",
                metadata=_json.dumps({"postId": post_id, "postTitle": title}),
            )
        return PostResponse.from_dict(result)

    @strawberry.mutation
    def updatePost(
        self, info: Info,
        postId: int,
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
        return PostResponse.from_dict(result)

    @strawberry.mutation
    def deletePost(self, info: Info, postId: int) -> PostResponse:
        logger.debug(f"Mutation.deletePost called with postId: {postId}")
        token = get_token(info)
        result = post_service_client.delete_post(post_id=postId, token=token)
        return PostResponse.from_dict(result)

    @strawberry.mutation
    def likePost(self, info: Info, postId: int, userId: int) -> PostResponse:
        logger.debug(f"Mutation.likePost called with postId: {postId}, userId: {userId}")
        token = get_token(info)
        result = post_service_client.like_post(post_id=postId, user_id=userId, token=token)
        return PostResponse.from_dict(result)

    @strawberry.mutation
    def unlikePost(self, info: Info, postId: int, userId: int) -> PostResponse:
        logger.debug(f"Mutation.unlikePost called with postId: {postId}, userId: {userId}")
        token = get_token(info)
        result = post_service_client.unlike_post(post_id=postId, user_id=userId, token=token)
        return PostResponse.from_dict(result)

    @strawberry.mutation
    def createComment(
        self, info: Info,
        postId: int,
        userId: int,
        comment: str,
        parentCommentId: Optional[int] = None
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
                author = user_service_client.get_user(int(userId), token=token)
                first = getattr(author, "first_name", "") or ""
                last = getattr(author, "last_name", "") or ""
                author_name = f"{first} {last}".strip() or author_name
            except Exception:
                pass
            comment_obj = result.get("comment") or {}
            comment_id = comment_obj.get("id") if isinstance(comment_obj, dict) else None
            _notify_mentioned_users(
                text=comment,
                author_id=int(userId),
                author_name=author_name,
                token=token,
                title="You were mentioned",
                message=f"{author_name} mentioned you in a comment",
                metadata=_json.dumps({"postId": postId, "commentId": comment_id}),
            )
        return CommentResponse.from_dict(result)

    @strawberry.mutation
    def updateComment(
        self, info: Info,
        commentId: int,
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
        return CommentResponse.from_dict(result)

    @strawberry.mutation
    def deleteComment(
        self, info: Info,
        commentId: int
    ) -> CommentResponse:
        logger.debug(f"Mutation.deleteComment called with commentId: {commentId}")
        token = get_token(info)
        result = post_service_client.delete_comment(comment_id=commentId, token=token)
        return CommentResponse.from_dict(result)

    @strawberry.mutation
    def likeComment(
        self, info: Info,
        commentId: int,
        userId: int,
        reactionType: Optional[str] = "like",
    ) -> CommentResponse:
        logger.debug(f"Mutation.likeComment called with commentId: {commentId}, userId: {userId}")
        token = get_token(info)
        result = post_service_client.like_comment(
            comment_id=commentId,
            user_id=userId,
            reaction_type=reactionType or "like",
            token=token
        )
        return CommentResponse.from_dict(result)

    @strawberry.mutation
    def unlikeComment(
        self, info: Info,
        commentId: int,
        userId: int
    ) -> CommentResponse:
        logger.debug(f"Mutation.unlikeComment called with commentId: {commentId}, userId: {userId}")
        token = get_token(info)
        result = post_service_client.unlike_comment(
            comment_id=commentId,
            user_id=userId,
            token=token
        )
        return CommentResponse.from_dict(result)

    @strawberry.mutation
    def addPostMedia(
        self, info: Info,
        postId: int,
        media: List[PostMediaInput]
    ) -> PostResponse:
        logger.debug(f"Mutation.addPostMedia called with postId: {postId}")
        token = get_token(info)
        result = post_service_client.add_post_media(
            post_id=postId,
            media=media,
            token=token
        )
        return PostResponse.from_dict(result)

    @strawberry.mutation
    def deletePostMedia(
        self, info: Info,
        mediaId: int
    ) -> MediaResponse:
        logger.debug(f"Mutation.deletePostMedia called with mediaId: {mediaId}")
        token = get_token(info)
        result = post_service_client.delete_post_media(media_id=mediaId, token=token)
        return MediaResponse.from_dict(result)

import grpc
import os
from datetime import datetime
from typing import List, Optional

from dotenv import load_dotenv

from app.clients.grpc_base_client import GRPCBaseClient
from app.proto_files.posts import post_pb2, post_pb2_grpc

load_dotenv()


def _str_id(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _optional_parent_id(parent_id) -> str:
    s = _str_id(parent_id)
    return "" if not s or s == "0" else s


def _ts(value) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromtimestamp(value)


def _media_dict(m) -> dict:
    uploaded = getattr(m, "uploaded_at", None)
    return {
        "id": _str_id(m.id),
        "mediaType": m.media_type,
        "mediaUrl": m.media_url,
        "mediaOrder": m.media_order,
        "mediaSize": getattr(m, "media_size", None),
        "caption": getattr(m, "caption", "") or "",
        "uploadedAt": _ts(uploaded) or datetime.utcnow(),
    }


def _post_dict(post) -> Optional[dict]:
    if not post or not _str_id(getattr(post, "id", None)):
        return None
    pinned_at = getattr(post, "pinned_at", None)
    return {
        "id": _str_id(post.id),
        "userId": _str_id(post.user_id),
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
        "createdAt": _ts(post.created_at) or datetime.utcnow(),
        "media": [_media_dict(m) for m in post.media],
        "likeCount": post.like_count,
        "commentCount": post.comment_count,
        "isLiked": bool(getattr(post, "is_liked", False)),
        "isAnonymous": bool(getattr(post, "is_anonymous", False)),
        "postCode": getattr(post, "post_code", "") or "",
        "propertyId": _str_id(getattr(post, "property_id", None)) or None,
        "currency": getattr(post, "currency", "") or "INR",
        "isPinned": bool(getattr(post, "is_pinned", False)),
        "pinnedAt": _ts(pinned_at),
        "shareCount": getattr(post, "share_count", 0),
        "viewCount": getattr(post, "view_count", 0),
    }


def _comment_dict(c) -> Optional[dict]:
    if not c or not _str_id(getattr(c, "id", None)):
        return None
    parent = _str_id(getattr(c, "parent_comment_id", None))
    return {
        "id": _str_id(c.id),
        "postId": _str_id(c.post_id),
        "userId": _str_id(c.user_id),
        "userFirstName": getattr(c, "user_first_name", "") or "",
        "userLastName": getattr(c, "user_last_name", "") or "",
        "userRole": getattr(c, "user_role", "") or "",
        "comment": c.comment,
        "parentCommentId": parent or None,
        "status": c.status,
        "addedAt": _ts(c.added_at) or datetime.utcnow(),
        "commentedAt": _ts(c.commented_at) or datetime.utcnow(),
        "editedAt": _ts(getattr(c, "edited_at", None)),
        "replies": [_comment_dict(r) for r in getattr(c, "replies", []) if r],
        "likeCount": c.like_count,
        "isAnonymous": bool(getattr(c, "is_anonymous", False)),
    }


def _report_dict(r) -> Optional[dict]:
    if not r:
        return None
    return {
        "id": _str_id(r.id),
        "reportCode": r.report_code,
        "entityType": r.entity_type,
        "entityId": _str_id(r.entity_id),
        "reportedBy": _str_id(r.reported_by),
        "reportedUserId": _str_id(r.reported_user_id) or None,
        "reasonCode": r.reason_code or "",
        "description": r.description or "",
        "status": r.status,
        "priority": getattr(r, "priority", "") or "",
        "createdAt": _ts(r.created_at) or datetime.utcnow(),
    }


def _share_dict(s) -> Optional[dict]:
    if not s:
        return None
    embedded = getattr(s, "post", None)
    return {
        "id": _str_id(s.id),
        "shareCode": s.share_code,
        "postId": _str_id(s.post_id),
        "sharedBy": _str_id(s.shared_by),
        "shareType": s.share_type,
        "caption": s.caption or "",
        "visibility": s.visibility,
        "createdAt": _ts(s.created_at) or datetime.utcnow(),
        "post": _post_dict(embedded) if embedded and _str_id(getattr(embedded, "id", None)) else None,
    }


def _post_response(response) -> dict:
    return {
        "success": bool(getattr(response, "success", False)),
        "message": getattr(response, "message", "") or "",
        "post": _post_dict(getattr(response, "post", None)),
    }


def _comment_response(response) -> dict:
    return {
        "success": bool(getattr(response, "success", False)),
        "message": getattr(response, "message", "") or "",
        "comment": _comment_dict(getattr(response, "comment", None)),
    }


def _comment_list_response(response) -> dict:
    return {
        "success": bool(getattr(response, "success", False)),
        "message": getattr(response, "message", "") or "",
        "comments": [
            _comment_dict(c) for c in getattr(response, "comments", []) if c
        ],
        "totalCount": getattr(response, "total_count", 0),
        "page": getattr(response, "page", 1),
        "totalPages": getattr(response, "total_pages", 1),
    }


def _share_list_response(response) -> dict:
    return {
        "success": bool(getattr(response, "success", False)),
        "message": getattr(response, "message", "") or "",
        "shares": [_share_dict(s) for s in getattr(response, "shares", []) if s],
        "totalCount": getattr(response, "total_count", 0),
        "page": getattr(response, "page", 1),
        "totalPages": getattr(response, "total_pages", 1),
    }


def _post_list_response(response) -> dict:
    return {
        "success": bool(getattr(response, "success", False)),
        "message": getattr(response, "message", "") or "",
        "posts": [_post_dict(p) for p in getattr(response, "posts", []) if p],
        "totalCount": getattr(response, "total_count", 0),
        "page": getattr(response, "page", 1),
        "totalPages": getattr(response, "total_pages", 1),
    }


class PostsServiceClient(GRPCBaseClient):
    def __init__(self):
        target = os.getenv("POST_SERVICE_URL", "localhost:50055")
        super().__init__(post_pb2_grpc.PostsServiceStub, target=target)

    def _rpc(self, method: str, request, token=None):
        return self._call(method, request, token=token)

    # ------------------------------------------------------------------ posts
    def create_post(
        self,
        user_id: str,
        title: str,
        content: str,
        visibility: str,
        property_type: str,
        location: str,
        price: float,
        status: str,
        latitude: float = None,
        longitude: float = None,
        property_id: str = None,
        currency: str = "INR",
        is_anonymous: bool = False,
        media: list = None,
        token=None,
    ) -> dict:
        try:
            media_list = []
            for m in media or []:
                media_list.append(
                    post_pb2.PostMediaUpload(
                        media_type=getattr(m, "mediaType", None) or "",
                        media_order=getattr(m, "mediaOrder", None) or 1,
                        caption=getattr(m, "caption", None) or "",
                        file_name=getattr(m, "fileName", None) or "",
                        content_type=getattr(m, "contentType", None) or "",
                        file_path=getattr(m, "filePath", None) or "",
                    )
                )
            request = post_pb2.PostCreateRequest(
                user_id=_str_id(user_id),
                title=title,
                content=content,
                visibility=visibility,
                type=property_type,
                location=location,
                latitude=latitude or 0.0,
                longitude=longitude or 0.0,
                price=price,
                status=status,
                is_anonymous=is_anonymous,
                property_id=_str_id(property_id),
                currency=currency or "INR",
                media=media_list,
            )
            return _post_response(self._rpc("CreatePost", request, token=token))
        except grpc.RpcError as e:
            return {"success": False, "message": f"Error creating post: {e}", "post": None}

    def get_post(self, post_id: str, token=None):
        try:
            return self._rpc("GetPost", post_pb2.PostRequest(post_id=_str_id(post_id)), token=token)
        except grpc.RpcError:
            return None

    def get_post_data(self, post_id: str, token=None) -> Optional[dict]:
        try:
            response = self.get_post(post_id=post_id, token=token)
            if not response or not getattr(response, "success", False) or not getattr(response, "post", None):
                return None
            return _post_dict(response.post)
        except grpc.RpcError:
            return None

    def update_post(self, post_id: str, token=None, **kwargs) -> dict:
        try:
            update_data = {k: v for k, v in kwargs.items() if v is not None}
            if "propertyType" in update_data:
                update_data["type"] = update_data.pop("propertyType")
            if "property_type" in update_data:
                update_data["type"] = update_data.pop("property_type")
            if "propertyId" in update_data:
                update_data["property_id"] = _str_id(update_data.pop("propertyId"))
            for key in ("mapLocation", "map_location"):
                update_data.pop(key, None)
            allowed = {
                "title", "content", "visibility", "type", "location",
                "latitude", "longitude", "price", "status", "is_anonymous",
                "property_id", "currency",
            }
            update_data = {k: v for k, v in update_data.items() if k in allowed}
            request = post_pb2.PostUpdateRequest(post_id=_str_id(post_id), **update_data)
            return _post_response(self._rpc("UpdatePost", request, token=token))
        except grpc.RpcError as e:
            return {"success": False, "message": f"Error updating post: {e}", "post": None}

    def delete_post(self, post_id: str, token=None) -> dict:
        try:
            response = self._rpc("DeletePost", post_pb2.PostRequest(post_id=_str_id(post_id)), token=token)
            return {
                "success": bool(response.success),
                "message": response.message or "",
                "post": None,
            }
        except grpc.RpcError as e:
            return {"success": False, "message": f"Error deleting post: {e}", "post": None}

    def get_posts_by_user(
        self, user_id: str, page: int = 1, limit: int = 10,
        viewer_user_id: str = "", token=None,
    ) -> dict:
        try:
            request = post_pb2.GetPostsByUserRequest(
                user_id=_str_id(user_id),
                page=page,
                limit=limit,
                viewer_user_id=_str_id(viewer_user_id),
            )
            return _post_list_response(self._rpc("GetPostsByUser", request, token=token))
        except grpc.RpcError:
            return {"success": False, "message": "Failed to fetch posts", "posts": [], "totalCount": 0, "page": page, "totalPages": 0}

    def get_my_posts(self, user_id: str, page: int = 1, limit: int = 10, token=None) -> dict:
        try:
            request = post_pb2.GetMyPostsRequest(user_id=_str_id(user_id), page=page, limit=limit)
            return _post_list_response(self._rpc("GetMyPosts", request, token=token))
        except grpc.RpcError as e:
            return {"success": False, "message": str(e), "posts": [], "totalCount": 0, "page": page, "totalPages": 0}

    def get_public_posts(self, page: int = 1, limit: int = 20, viewer_user_id: str = "", token=None) -> dict:
        try:
            request = post_pb2.GetPublicPostsRequest(
                page=page, limit=limit, viewer_user_id=_str_id(viewer_user_id),
            )
            return _post_list_response(self._rpc("GetPublicPosts", request, token=token))
        except grpc.RpcError as e:
            return {"success": False, "message": str(e), "posts": [], "totalCount": 0, "page": page, "totalPages": 0}

    def get_property_posts(
        self, property_id: str, page: int = 1, limit: int = 10,
        viewer_user_id: str = "", token=None,
    ) -> dict:
        try:
            request = post_pb2.GetPropertyPostsRequest(
                property_id=_str_id(property_id),
                page=page,
                limit=limit,
                viewer_user_id=_str_id(viewer_user_id),
            )
            return _post_list_response(self._rpc("GetPropertyPosts", request, token=token))
        except grpc.RpcError as e:
            return {"success": False, "message": str(e), "posts": [], "totalCount": 0, "page": page, "totalPages": 0}

    def get_builder_posts(
        self, builder_user_id: str = "", page: int = 1, limit: int = 10,
        viewer_user_id: str = "", user_ids: Optional[List[str]] = None, token=None,
    ) -> dict:
        try:
            request = post_pb2.GetBuilderPostsRequest(
                builder_user_id=_str_id(builder_user_id),
                page=page,
                limit=limit,
                viewer_user_id=_str_id(viewer_user_id),
                user_ids=[_str_id(uid) for uid in (user_ids or []) if _str_id(uid)],
            )
            return _post_list_response(self._rpc("GetBuilderPosts", request, token=token))
        except grpc.RpcError as e:
            return {"success": False, "message": str(e), "posts": [], "totalCount": 0, "page": page, "totalPages": 0}

    def search_posts(
        self, property_type: str = None, location: str = None,
        min_price: float = None, max_price: float = None,
        status: str = None, query: str = None, hashtag: str = None,
        page: int = 1, limit: int = 10,
        viewer_user_id: str = "", token=None,
    ) -> dict:
        request = post_pb2.SearchPostsRequest(
            type=property_type or "",
            location=location or "",
            min_price=min_price or 0.0,
            max_price=max_price or 0.0,
            status=status or "",
            query=query or "",
            hashtag=hashtag or "",
            page=page,
            limit=limit,
            viewer_user_id=_str_id(viewer_user_id),
        )
        return _post_list_response(self._rpc("SearchPosts", request, token=token))

    def trending_posts(self, limit: int = 10, viewer_user_id: str = "", token=None) -> dict:
        request = post_pb2.TrendingPostsRequest(
            limit=limit,
            viewer_user_id=_str_id(viewer_user_id),
        )
        return _post_list_response(self._rpc("TrendingPosts", request, token=token))

    def pin_post(self, post_id: str, user_id: str, token=None) -> dict:
        request = post_pb2.PostOwnerRequest(post_id=_str_id(post_id), user_id=_str_id(user_id))
        return _post_response(self._rpc("PinPost", request, token=token))

    def unpin_post(self, post_id: str, user_id: str, token=None) -> dict:
        request = post_pb2.PostOwnerRequest(post_id=_str_id(post_id), user_id=_str_id(user_id))
        return _post_response(self._rpc("UnpinPost", request, token=token))

    def archive_post(self, post_id: str, user_id: str, token=None) -> dict:
        request = post_pb2.PostOwnerRequest(post_id=_str_id(post_id), user_id=_str_id(user_id))
        return _post_response(self._rpc("ArchivePost", request, token=token))

    def restore_archived_post(self, post_id: str, user_id: str, token=None) -> dict:
        request = post_pb2.PostOwnerRequest(post_id=_str_id(post_id), user_id=_str_id(user_id))
        return _post_response(self._rpc("RestoreArchivedPost", request, token=token))

    # ------------------------------------------------------------------ media
    def add_post_media(self, post_id: str, media: list, uploaded_by: str = "", token=None) -> dict:
        try:
            media_list = [
                post_pb2.PostMediaUpload(
                    media_type=getattr(m, "mediaType", None) or "image",
                    media_order=getattr(m, "mediaOrder", None) or 1,
                    caption=getattr(m, "caption", None) or "",
                    file_name=getattr(m, "fileName", None) or "",
                    content_type=getattr(m, "contentType", None) or "",
                    file_path=getattr(m, "filePath", None) or "",
                )
                for m in media
            ]
            request = post_pb2.PostMediaRequest(
                post_id=_str_id(post_id),
                media=media_list,
                uploaded_by=_str_id(uploaded_by),
            )
            return _post_response(self._rpc("AddPostMedia", request, token=token))
        except grpc.RpcError as e:
            return {"success": False, "message": f"Error adding media: {e}", "post": None}

    def delete_post_media(self, media_id: str, token=None) -> dict:
        try:
            response = self._rpc("DeletePostMedia", post_pb2.MediaIdRequest(media_id=_str_id(media_id)), token=token)
            return {"success": bool(response.success), "message": response.message}
        except grpc.RpcError as e:
            return {"success": False, "message": f"Error deleting media: {e}"}

    # ------------------------------------------------------------------ likes
    def like_post(self, post_id: str, user_id: str, reaction_type: str = "LIKE", token=None) -> dict:
        try:
            request = post_pb2.LikeRequest(
                post_id=_str_id(post_id),
                user_id=_str_id(user_id),
                reaction_type=(reaction_type or "LIKE").upper(),
            )
            return _post_response(self._rpc("LikePost", request, token=token))
        except grpc.RpcError as e:
            return {"success": False, "message": f"Error liking post: {e}", "post": None}

    def unlike_post(self, post_id: str, user_id: str, token=None) -> dict:
        try:
            request = post_pb2.LikeRequest(post_id=_str_id(post_id), user_id=_str_id(user_id))
            return _post_response(self._rpc("UnlikePost", request, token=token))
        except grpc.RpcError as e:
            return {"success": False, "message": f"Error unliking post: {e}", "post": None}

    def get_post_likes(self, post_id: str, page: int = 1, limit: int = 20, token=None) -> dict:
        try:
            response = self._rpc(
                "GetPostLikes",
                post_pb2.GetPostLikesRequest(post_id=_str_id(post_id), page=page, limit=limit),
                token=token,
            )
            return {
                "success": bool(response.success),
                "message": response.message,
                "likes": [
                    {
                        "userId": _str_id(like.user_id),
                        "firstName": like.first_name,
                        "lastName": like.last_name,
                        "userRole": like.user_role,
                        "reactionType": like.reaction_type,
                        "likedAt": _ts(like.liked_at),
                    }
                    for like in response.likes
                ],
                "totalCount": response.total_count,
                "page": response.page,
                "totalPages": response.total_pages,
            }
        except grpc.RpcError as e:
            return {"success": False, "message": str(e), "likes": [], "totalCount": 0, "page": page, "totalPages": 0}

    def check_like_status(self, post_id: str, user_id: str, token=None) -> dict:
        try:
            response = self._rpc(
                "CheckLikeStatus",
                post_pb2.CheckLikeStatusRequest(post_id=_str_id(post_id), user_id=_str_id(user_id)),
                token=token,
            )
            return {
                "success": bool(response.success),
                "message": response.message,
                "isLiked": bool(response.is_liked),
                "reactionType": response.reaction_type or "",
            }
        except grpc.RpcError as e:
            return {"success": False, "message": str(e), "isLiked": False, "reactionType": ""}

    # ---------------------------------------------------------------- comments
    def create_comment(
        self, post_id: str, user_id: str, comment: str,
        parent_comment_id: Optional[str] = None, is_anonymous: bool = False, token=None,
    ) -> dict:
        try:
            request = post_pb2.CommentCreateRequest(
                post_id=_str_id(post_id),
                user_id=_str_id(user_id),
                comment=comment,
                parent_comment_id=_optional_parent_id(parent_comment_id),
                is_anonymous=is_anonymous,
            )
            return _comment_response(self._rpc("CreateComment", request, token=token))
        except grpc.RpcError as e:
            return {"success": False, "message": f"Error creating comment: {e}", "comment": None}

    def reply_comment(
        self, post_id: str, user_id: str, comment: str,
        parent_comment_id: str, is_anonymous: bool = False, token=None,
    ) -> dict:
        try:
            request = post_pb2.CommentCreateRequest(
                post_id=_str_id(post_id),
                user_id=_str_id(user_id),
                comment=comment,
                parent_comment_id=_str_id(parent_comment_id),
                is_anonymous=is_anonymous,
            )
            return _comment_response(self._rpc("ReplyComment", request, token=token))
        except grpc.RpcError as e:
            return {"success": False, "message": f"Error replying to comment: {e}", "comment": None}

    def update_comment(self, comment_id: str, comment: Optional[str] = None,
                       status: Optional[str] = None, token=None) -> dict:
        try:
            request = post_pb2.CommentUpdateRequest(
                comment_id=_str_id(comment_id),
                comment=comment or "",
                status=status or "",
            )
            return _comment_response(self._rpc("UpdateComment", request, token=token))
        except grpc.RpcError as e:
            return {"success": False, "message": f"Error updating comment: {e}", "comment": None}

    def delete_comment(self, comment_id: str, token=None) -> dict:
        try:
            response = self._rpc("DeleteComment", post_pb2.CommentRequest(comment_id=_str_id(comment_id)), token=token)
            return {
                "success": bool(response.success),
                "message": response.message or ("Comment deleted" if response.success else "Failed"),
                "comment": None,
            }
        except grpc.RpcError as e:
            return {"success": False, "message": f"Error deleting comment: {e}", "comment": None}

    def get_comments(self, post_id: str, page: int = 1, limit: int = 10, token=None) -> dict:
        try:
            response = self._rpc(
                "GetComments",
                post_pb2.GetCommentsRequest(post_id=_str_id(post_id), page=page, limit=limit),
                token=token,
            )
            return _comment_list_response(response)
        except grpc.RpcError as e:
            return {"success": False, "message": str(e), "comments": [], "totalCount": 0, "page": page, "totalPages": 0}

    def get_comment(self, comment_id: str, token=None) -> dict:
        try:
            return _comment_response(
                self._rpc("GetComment", post_pb2.CommentRequest(comment_id=_str_id(comment_id)), token=token)
            )
        except grpc.RpcError as e:
            return {"success": False, "message": str(e), "comment": None}

    def get_replies(self, comment_id: str, page: int = 1, limit: int = 10, token=None) -> dict:
        try:
            response = self._rpc(
                "GetReplies",
                post_pb2.GetRepliesRequest(comment_id=_str_id(comment_id), page=page, limit=limit),
                token=token,
            )
            return _comment_list_response(response)
        except grpc.RpcError as e:
            return {"success": False, "message": str(e), "comments": [], "totalCount": 0, "page": page, "totalPages": 0}

    def like_comment(self, comment_id: str, user_id: str, reaction_type: str = "LIKE", token=None) -> dict:
        try:
            request = post_pb2.CommentLikeRequest(
                comment_id=_str_id(comment_id),
                user_id=_str_id(user_id),
                reaction_type=(reaction_type or "LIKE").upper(),
            )
            return _comment_response(self._rpc("LikeComment", request, token=token))
        except grpc.RpcError as e:
            return {"success": False, "message": f"Error liking comment: {e}", "comment": None}

    def unlike_comment(self, comment_id: str, user_id: str, token=None) -> dict:
        try:
            request = post_pb2.CommentLikeRequest(
                comment_id=_str_id(comment_id),
                user_id=_str_id(user_id),
            )
            return _comment_response(self._rpc("UnlikeComment", request, token=token))
        except grpc.RpcError as e:
            return {"success": False, "message": f"Error unliking comment: {e}", "comment": None}

    def report_comment(
        self, comment_id: str, reported_by: str, reported_user_id: str = "",
        reason_code: str = "", description: str = "", token=None,
    ) -> dict:
        try:
            request = post_pb2.ReportCommentRequest(
                comment_id=_str_id(comment_id),
                reported_by=_str_id(reported_by),
                reported_user_id=_str_id(reported_user_id),
                reason_code=reason_code or "",
                description=description or "",
            )
            response = self._rpc("ReportComment", request, token=token)
            return {
                "success": bool(response.success),
                "message": response.message,
                "report": _report_dict(getattr(response, "report", None)),
            }
        except grpc.RpcError as e:
            return {"success": False, "message": str(e), "report": None}

    # ------------------------------------------------------------------ share
    def share_post(
        self, post_id: str, shared_by: str, share_type: str = "SHARE",
        caption: str = "", visibility: str = "PUBLIC", token=None,
    ) -> dict:
        try:
            request = post_pb2.SharePostRequest(
                post_id=_str_id(post_id),
                shared_by=_str_id(shared_by),
                share_type=share_type or "SHARE",
                caption=caption or "",
                visibility=visibility or "PUBLIC",
            )
            response = self._rpc("SharePost", request, token=token)
            return {
                "success": bool(response.success),
                "message": response.message,
                "share": _share_dict(getattr(response, "share", None)),
            }
        except grpc.RpcError as e:
            return {"success": False, "message": str(e), "share": None}

    def get_shared_posts(self, user_id: str, page: int = 1, limit: int = 10, token=None) -> dict:
        try:
            response = self._rpc(
                "GetSharedPosts",
                post_pb2.GetSharedPostsRequest(user_id=_str_id(user_id), page=page, limit=limit),
                token=token,
            )
            return _share_list_response(response)
        except grpc.RpcError as e:
            return {"success": False, "message": str(e), "shares": [], "totalCount": 0, "page": page, "totalPages": 0}

    def delete_shared_post(self, share_id: str, user_id: str, token=None) -> dict:
        try:
            response = self._rpc(
                "DeleteSharedPost",
                post_pb2.DeleteSharedPostRequest(share_id=_str_id(share_id), user_id=_str_id(user_id)),
                token=token,
            )
            return {"success": bool(response.success), "message": response.message}
        except grpc.RpcError as e:
            return {"success": False, "message": str(e)}

    # ----------------------------------------------------------------- reports
    def report_post(
        self, post_id: str, reported_by: str, reported_user_id: str = "",
        reason_code: str = "", description: str = "", token=None,
    ) -> dict:
        return self._report_rpc(
            "ReportPost",
            post_pb2.ReportPostRequest(
                post_id=_str_id(post_id),
                reported_by=_str_id(reported_by),
                reported_user_id=_str_id(reported_user_id),
                reason_code=reason_code or "",
                description=description or "",
            ),
            token=token,
        )

    def report_property(
        self, property_id: str, reported_by: str, reported_user_id: str = "",
        reason_code: str = "", description: str = "", token=None,
    ) -> dict:
        return self._report_rpc(
            "ReportProperty",
            post_pb2.ReportPropertyRequest(
                property_id=_str_id(property_id),
                reported_by=_str_id(reported_by),
                reported_user_id=_str_id(reported_user_id),
                reason_code=reason_code or "",
                description=description or "",
            ),
            token=token,
        )

    def report_user(
        self, user_id: str, reported_by: str,
        reason_code: str = "", description: str = "", token=None,
    ) -> dict:
        return self._report_rpc(
            "ReportUser",
            post_pb2.ReportUserRequest(
                user_id=_str_id(user_id),
                reported_by=_str_id(reported_by),
                reason_code=reason_code or "",
                description=description or "",
            ),
            token=token,
        )

    def get_my_reports(self, reported_by: str, page: int = 1, limit: int = 20, token=None) -> dict:
        try:
            response = self._rpc(
                "GetMyReports",
                post_pb2.GetMyReportsRequest(reported_by=_str_id(reported_by), page=page, limit=limit),
                token=token,
            )
            return {
                "success": bool(response.success),
                "message": response.message,
                "reports": [_report_dict(r) for r in response.reports],
                "totalCount": response.total_count,
                "page": response.page,
                "totalPages": response.total_pages,
            }
        except grpc.RpcError as e:
            return {"success": False, "message": str(e), "reports": [], "totalCount": 0, "page": page, "totalPages": 0}

    def _report_rpc(self, method: str, request, token=None) -> dict:
        try:
            response = self._rpc(method, request, token=token)
            return {
                "success": bool(response.success),
                "message": response.message,
                "report": _report_dict(getattr(response, "report", None)),
            }
        except grpc.RpcError as e:
            return {"success": False, "message": str(e), "report": None}


post_service_client = PostsServiceClient()

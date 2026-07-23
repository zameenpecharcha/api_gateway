import grpc
import base64
import os
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv
from app.proto_files.posts import post_pb2_grpc, post_pb2
from app.utils.jwt_utils import get_token
from app.clients.grpc_base_client import GRPCBaseClient

load_dotenv()


class PostsServiceClient(GRPCBaseClient):
    def __init__(self):
        target = os.getenv("POST_SERVICE_URL", "localhost:50055")
        super().__init__(post_pb2_grpc.PostsServiceStub, target=target)

    def get_comments(self, post_id: int, page: int = 1, limit: int = 10,token=None):
        try:
            request = post_pb2.GetCommentsRequest(
                post_id=post_id,
                page=page,
                limit=limit
            )
            return self._call("GetComments", request,token=token)
        except grpc.RpcError as e:
            print(f"Error in get_comments: {str(e)}")
            return None

    def search_posts(self, property_type: str = None, location: str = None,
                     min_price: float = None, max_price: float = None,
                     status: str = None, page: int = 1, limit: int = 10,
                     viewer_user_id: int = 0, token=None):
        request = post_pb2.SearchPostsRequest(
            type=property_type or "",
            location=location or "",
            min_price=min_price or 0.0,
            max_price=max_price or 0.0,
            status=status or "",
            page=page,
            limit=limit,
            viewer_user_id=viewer_user_id or 0,
        )
        return self._call(self.stub.SearchPosts, request, token=token)

    def trending_posts(self, limit: int = 10, viewer_user_id: int = 0, token=None):
        request = post_pb2.TrendingPostsRequest(
            limit=limit,
            viewer_user_id=viewer_user_id or 0,
        )
        return self._call(self.stub.TrendingPosts, request, token=token)

    def create_post(self, user_id: int, title: str, content: str,
                    visibility: str, property_type: str, location: str,
                    price: float, status: str,
                    latitude: float = None, longitude: float = None,
                    media: list = None, token=None) -> dict:
        try:
            media_list = []
            if media:
                for m in media:
                    media_upload = post_pb2.PostMediaUpload(
                        media_type=getattr(m, 'mediaType', None) or '',
                        media_order=getattr(m, 'mediaOrder', None) or 1,
                        caption=getattr(m, 'caption', None) or '',
                        file_name=getattr(m, 'fileName', None) or '',
                        content_type=getattr(m, 'contentType', None) or '',
                        file_path=getattr(m, 'filePath', None) or ''
                    )
                    media_list.append(media_upload)

            request = post_pb2.PostCreateRequest(
                user_id=user_id,
                title=title,
                content=content,
                visibility=visibility,
                type=property_type,
                location=location,
                latitude=latitude or 0.0,
                longitude=longitude or 0.0,
                price=price,
                status=status,
                media=media_list
            )
            response = self._call(self.stub.CreatePost, request,token=token)

            # Convert the gRPC response to a dictionary
            if response.post:
                media_list = []
                for m in response.post.media:
                    media_list.append({
                        'id': m.id,
                        'mediaType': m.media_type,
                        'mediaUrl': m.media_url,
                        'mediaOrder': m.media_order,
                        'mediaSize': m.media_size,
                        'caption': m.caption,
                        'uploadedAt': datetime.fromtimestamp(m.uploaded_at)
                    })

                post_dict = {
                    'id': response.post.id,
                    'userId': response.post.user_id,
                    'title': response.post.title,
                    'content': response.post.content,
                    'visibility': response.post.visibility,
                    'propertyType': response.post.type,
                    'location': response.post.location,
                     # mapLocation deprecated; keep for backward mapping if present
                    # mapLocation removed
                    'latitude': getattr(response.post, 'latitude', 0.0),
                    'longitude': getattr(response.post, 'longitude', 0.0),
                    'price': response.post.price,
                    'status': response.post.status,
                    'createdAt': datetime.fromtimestamp(response.post.created_at),
                    'media': media_list,
                    'likeCount': response.post.like_count,
                    'commentCount': response.post.comment_count
                }
            else:
                post_dict = None

            return {
                'success': response.success,
                'message': response.message,
                'post': post_dict
            }
        except grpc.RpcError as e:
            return {
                'success': False,
                'message': f'Error creating post: {str(e)}',
                'post': None
            }

    def get_post(self, post_id: int,token=None):
        try:
            request = post_pb2.PostRequest(post_id=post_id)
            return self._call(self.stub.GetPost, request,token=token)
        except grpc.RpcError as e:
            return None

    def update_post(self, post_id: int,token=None, **kwargs) -> dict:
        try:
            # Filter out None values
            update_data = {k: v for k, v in kwargs.items() if v is not None}

            # Convert camelCase / gateway names to gRPC PostUpdateRequest fields
            if 'propertyType' in update_data:
                update_data['type'] = update_data.pop('propertyType')
            if 'property_type' in update_data:
                update_data['type'] = update_data.pop('property_type')
            # mapLocation removed; ignore if present
            if 'mapLocation' in update_data:
                update_data.pop('mapLocation')
            if 'map_location' in update_data:
                update_data.pop('map_location')

            # Only known PostUpdateRequest fields
            allowed = {
                'title', 'content', 'visibility', 'type', 'location',
                'latitude', 'longitude', 'price', 'status', 'is_anonymous',
            }
            update_data = {k: v for k, v in update_data.items() if k in allowed}

            request = post_pb2.PostUpdateRequest(
                post_id=post_id,
                **update_data
            )
            response = self._call(self.stub.UpdatePost, request,token=token)

            # Convert the gRPC response to a dictionary
            if response.post and response.post.id:
                media_list = []
                for m in response.post.media:
                    media_list.append({
                        'id': m.id,
                        'mediaType': m.media_type,
                        'mediaUrl': m.media_url,
                        'mediaOrder': m.media_order,
                        'mediaSize': m.media_size,
                        'caption': m.caption,
                        'uploadedAt': datetime.fromtimestamp(m.uploaded_at)
                    })

                post_dict = {
                    'id': response.post.id,
                    'userId': response.post.user_id,
                    'userFirstName': getattr(response.post, 'user_first_name', '') or '',
                    'userLastName': getattr(response.post, 'user_last_name', '') or '',
                    'userEmail': getattr(response.post, 'user_email', '') or '',
                    'userPhone': getattr(response.post, 'user_phone', '') or '',
                    'userRole': getattr(response.post, 'user_role', '') or '',
                    'title': response.post.title,
                    'content': response.post.content,
                    'visibility': response.post.visibility,
                    'propertyType': response.post.type,
                    'location': response.post.location,
                    'latitude': getattr(response.post, 'latitude', 0.0),
                    'longitude': getattr(response.post, 'longitude', 0.0),
                    'price': response.post.price,
                    'status': response.post.status,
                    'createdAt': datetime.fromtimestamp(response.post.created_at),
                    'media': media_list,
                    'likeCount': response.post.like_count,
                    'commentCount': response.post.comment_count
                }
            else:
                post_dict = None

            return {
                'success': bool(response.success),
                'message': response.message or ('Post updated successfully' if response.success else 'Failed to update post'),
                'post': post_dict
            }
        except grpc.RpcError as e:
            return {
                'success': False,
                'message': f'Error updating post: {str(e)}',
                'post': None
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error updating post: {str(e)}',
                'post': None
            }

    def delete_post(self, post_id: int,token=None):
        try:
            request = post_pb2.PostRequest(post_id=post_id)
            response = self._call(self.stub.DeletePost, request,token=token)
            return {
                'success': bool(getattr(response, 'success', False)),
                'message': getattr(response, 'message', None) or (
                    'Post deleted successfully' if getattr(response, 'success', False) else 'Failed to delete post'
                ),
                'post': None,
            }
        except grpc.RpcError as e:
            return {
                'success': False,
                'message': f'Error deleting post: {str(e)}',
                'post': None,
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error deleting post: {str(e)}',
                'post': None,
            }

    def get_posts_by_user(self, user_id: int, page: int = 1, limit: int = 10,
                          viewer_user_id: int = 0, token=None):
        try:
            request = post_pb2.GetPostsByUserRequest(
                user_id=user_id,
                page=page,
                limit=limit,
                viewer_user_id=viewer_user_id or 0,
            )
            response = self._call(self.stub.GetPostsByUser, request, token=token)
            return response.posts
        except grpc.RpcError as e:
            return []

    def like_post(self, post_id: int, user_id: int,token=None) -> dict:
        try:
            # First check if the post exists
            post_request = post_pb2.PostRequest(post_id=post_id)
            post_response = self._call(self.stub.GetPost, post_request,token=token)
            if not post_response.post:
                return {
                    'success': False,
                    'message': f'Post with ID {post_id} not found',
                    'post': None
                }

            request = post_pb2.LikeRequest(
                post_id=post_id,  # Changed from id to post_id
                user_id=user_id,
                reaction_type='like'
            )
            response = self._call(self.stub.LikePost, request,token=token)

            # Convert the gRPC response to a dictionary
            if response.post:
                media_list = []
                for m in response.post.media:
                    media_list.append({
                        'id': m.id,
                        'mediaType': m.media_type,
                        'mediaUrl': m.media_url,
                        'mediaOrder': m.media_order,
                        'mediaSize': m.media_size,
                        'caption': m.caption,
                        'uploadedAt': datetime.fromtimestamp(m.uploaded_at)
                    })

                post_dict = {
                    'id': response.post.id,
                    'userId': response.post.user_id,
                    'title': response.post.title,
                    'content': response.post.content,
                    'visibility': response.post.visibility,
                    'propertyType': response.post.type,
                    'location': response.post.location,
                    # mapLocation removed
                    'price': response.post.price,
                    'status': response.post.status,
                    'createdAt': datetime.fromtimestamp(response.post.created_at),
                    'media': media_list,
                    'likeCount': response.post.like_count,
                    'commentCount': response.post.comment_count
                }
            else:
                post_dict = None

            return {
                'success': response.success,
                'message': response.message,
                'post': post_dict
            }
        except grpc.RpcError as e:
            return {
                'success': False,
                'message': f'Error liking post: {str(e)}',
                'post': None
            }

    def unlike_post(self, post_id: int, user_id: int,token=None) -> dict:
        try:
            request = post_pb2.LikeRequest(
                post_id=post_id,  # Changed from id to post_id
                user_id=user_id
            )
            response = self._call(self.stub.UnlikePost, request,token=token)

            # Convert the gRPC response to a dictionary
            if response.post:
                media_list = []
                for m in response.post.media:
                    media_list.append({
                        'id': m.id,
                        'mediaType': m.media_type,
                        'mediaUrl': m.media_url,
                        'mediaOrder': m.media_order,
                        'mediaSize': m.media_size,
                        'caption': m.caption,
                        'uploadedAt': datetime.fromtimestamp(m.uploaded_at)
                    })

                post_dict = {
                    'id': response.post.id,
                    'userId': response.post.user_id,
                    'title': response.post.title,
                    'content': response.post.content,
                    'visibility': response.post.visibility,
                    'propertyType': response.post.type,
                    'location': response.post.location,
                    # mapLocation removed
                    'price': response.post.price,
                    'status': response.post.status,
                    'createdAt': datetime.fromtimestamp(response.post.created_at),
                    'media': media_list,
                    'likeCount': response.post.like_count,
                    'commentCount': response.post.comment_count
                }
            else:
                post_dict = None

            return {
                'success': response.success,
                'message': response.message,
                'post': post_dict
            }
        except grpc.RpcError as e:
            return {
                'success': False,
                'message': f'Error unliking post: {str(e)}',
                'post': None
            }

    def delete_post_media(self, media_id: int,token=None) -> dict:
        try:
            request = post_pb2.MediaIdRequest(media_id=media_id)
            response = self._call(self.stub.DeletePostMedia, request,token=token)

            return {
                'success': response.success,
                'message': response.message
            }
        except grpc.RpcError as e:
            return {
                'success': False,
                'message': f'Error deleting media: {str(e)}'
            }

    def add_post_media(self, post_id: int, media: list,token=None) -> dict:
        try:
            media_list = []
            for m in media:
                media_upload = post_pb2.PostMediaUpload(
                    media_type=getattr(m, 'mediaType', None) or 'image',
                    media_order=getattr(m, 'mediaOrder', None) or 1,
                    caption=getattr(m, 'caption', None) or '',
                    file_name=getattr(m, 'fileName', None) or '',
                    content_type=getattr(m, 'contentType', None) or '',
                    file_path=getattr(m, 'filePath', None) or ''
                )
                media_list.append(media_upload)

            request = post_pb2.PostMediaRequest(
                post_id=post_id,
                media=media_list
            )
            response = self._call(self.stub.AddPostMedia, request,token=token)

            # Convert the gRPC response to a dictionary
            if response.post:
                media_list = []
                for m in response.post.media:
                    media_list.append({
                        'id': m.id,
                        'mediaType': m.media_type,
                        'mediaUrl': m.media_url,
                        'mediaOrder': m.media_order,
                        'mediaSize': m.media_size,
                        'caption': m.caption,
                        'uploadedAt': datetime.fromtimestamp(m.uploaded_at)
                    })

                post_dict = {
                    'id': response.post.id,
                    'userId': response.post.user_id,
                    'title': response.post.title,
                    'content': response.post.content,
                    'visibility': response.post.visibility,
                    'propertyType': response.post.type,
                    'location': response.post.location,
                    # mapLocation removed
                    'price': response.post.price,
                    'status': response.post.status,
                    'createdAt': datetime.fromtimestamp(response.post.created_at),
                    'media': media_list,
                    'likeCount': response.post.like_count,
                    'commentCount': response.post.comment_count
                }
            else:
                post_dict = None

            return {
                'success': response.success,
                'message': response.message,
                'post': post_dict
            }
        except grpc.RpcError as e:
            return {
                'success': False,
                'message': f'Error adding media: {str(e)}',
                'post': None
            }

    def create_comment(self, post_id: int, user_id: int, comment: str,
                       parent_comment_id: Optional[int] = None,token=None) -> dict:
        try:
            request = post_pb2.CommentCreateRequest(
                post_id=post_id,
                user_id=user_id,
                comment=comment,
                parent_comment_id=parent_comment_id or 0
            )
            response = self._call(self.stub.CreateComment, request,token=token)

            # Convert the gRPC response to a dictionary
            if response and response.comment:
                comment_dict = {
                    'id': response.comment.id,
                    'postId': response.comment.post_id,
                    'userId': response.comment.user_id,
                    'userFirstName': response.comment.user_first_name,
                    'userLastName': response.comment.user_last_name,
                    'userRole': response.comment.user_role,
                    'comment': response.comment.comment,
                    'parentCommentId': response.comment.parent_comment_id if response.comment.parent_comment_id != 0 else None,
                    'status': response.comment.status,
                    'addedAt': datetime.fromtimestamp(response.comment.added_at),
                    'commentedAt': datetime.fromtimestamp(response.comment.commented_at),
                    'replies': [],  # Replies will be fetched separately if needed
                    'likeCount': response.comment.like_count
                }
            else:
                comment_dict = None

            return {
                'success': response.success if response else False,
                'message': response.message if response else 'Failed to create comment',
                'comment': comment_dict
            }
        except grpc.RpcError as e:
            print(f"Error in create_comment: {str(e)}")
            return {
                'success': False,
                'message': f'Error creating comment: {str(e)}',
                'comment': None
            }

    def update_comment(self, comment_id: int, comment: Optional[str] = None,
                       status: Optional[str] = None,token=None) -> dict:
        try:
            request = post_pb2.CommentUpdateRequest(
                comment_id=comment_id,
                comment=comment,
                status=status
            )
            response = self._call(self.stub.UpdateComment, request,token=token)

            # Convert the gRPC response to a dictionary
            if response and response.comment:
                c = response.comment
                comment_dict = {
                    'id': c.id,
                    'postId': c.post_id,
                    'userId': c.user_id,
                    'comment': c.comment,
                    'parentCommentId': c.parent_comment_id if c.parent_comment_id != 0 else None,
                    'status': c.status,
                    'addedAt': datetime.fromtimestamp(c.added_at),
                    'commentedAt': datetime.fromtimestamp(c.commented_at),
                    'replies': [],
                    'likeCount': c.like_count
                }
            else:
                comment_dict = None

            return {
                'success': response.success if response else False,
                'message': response.message if response else 'Failed to update comment',
                'comment': comment_dict
            }
        except grpc.RpcError as e:
            return {
                'success': False,
                'message': f'Error updating comment: {str(e)}',
                'comment': None
            }

    def delete_comment(self, comment_id: int,token=None) -> dict:
        try:
            request = post_pb2.CommentRequest(comment_id=comment_id)
            response = self._call(self.stub.DeleteComment, request,token=token)
            return {
                'success': True,
                'message': 'Comment deleted successfully',
                'comment': None
            }
        except grpc.RpcError as e:
            return {
                'success': False,
                'message': f'Error deleting comment: {str(e)}',
                'comment': None
            }

    def like_comment(self, comment_id: int, user_id: int,token=None) -> dict:
        try:
            request = post_pb2.CommentLikeRequest(
                comment_id=comment_id,
                user_id=user_id,
                reaction_type='like'
            )
            response = self._call(self.stub.LikeComment, request,token=token)

            # Convert the gRPC response to a dictionary
            if response.comment:
                comment_dict = {
                    'id': response.comment.id,
                    'postId': response.comment.post_id,
                    'userId': response.comment.user_id,
                    'comment': response.comment.comment,
                    'parentCommentId': response.comment.parent_comment_id if response.comment.parent_comment_id != 0 else None,
                    'status': response.comment.status,
                    'addedAt': datetime.fromtimestamp(response.comment.added_at),
                    'commentedAt': datetime.fromtimestamp(response.comment.commented_at),
                    'replies': [],  # Replies will be fetched separately if needed
                    'likeCount': response.comment.like_count
                }
            else:
                comment_dict = None

            return {
                'success': response.success,
                'message': response.message,
                'comment': comment_dict
            }
        except grpc.RpcError as e:
            return {
                'success': False,
                'message': f'Error liking comment: {str(e)}',
                'comment': None
            }

    def unlike_comment(self, comment_id: int, user_id: int,token=None) -> dict:
        try:
            request = post_pb2.CommentLikeRequest(
                comment_id=comment_id,
                user_id=user_id
            )
            response = self._call(self.stub.UnlikeComment, request,token=token)

            # Convert the gRPC response to a dictionary
            if response.comment:
                comment_dict = {
                    'id': response.comment.id,
                    'postId': response.comment.post_id,
                    'userId': response.comment.user_id,
                    'comment': response.comment.comment,
                    'parentCommentId': response.comment.parent_comment_id if response.comment.parent_comment_id != 0 else None,
                    'status': response.comment.status,
                    'addedAt': datetime.fromtimestamp(response.comment.added_at),
                    'commentedAt': datetime.fromtimestamp(response.comment.commented_at),
                    'replies': [],  # Replies will be fetched separately if needed
                    'likeCount': response.comment.like_count
                }
            else:
                comment_dict = None

            return {
                'success': response.success,
                'message': response.message,
                'comment': comment_dict
            }
        except grpc.RpcError as e:
            return {
                'success': False,
                'message': f'Error unliking comment: {str(e)}',
                'comment': None
            }

post_service_client=PostsServiceClient()
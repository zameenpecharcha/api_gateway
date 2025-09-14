import grpc
import base64
from datetime import datetime
from typing import Optional
from app.proto_files.posts import post_pb2_grpc, post_pb2
from app.utils.jwt_utils import get_token
from app.clients.grpc_base_client import GRPCBaseClient


class PostsServiceClient(GRPCBaseClient):
    def __init__(self):
        super().__init__(post_pb2_grpc.PostsServiceStub, target='localhost:50052')

    def get_comments(self, post_id: int, page: int = 1, limit: int = 10,token=None):
        try:
            request = post_pb2.GetCommentsRequest(
                post_id=post_id,
                page=page,
                limit=limit
            )
            return self._call(self.stub.GetComments, request,token=token)
        except grpc.RpcError as e:
            print(f"Error in get_comments: {str(e)}")
            return None

    def search_posts(self, property_type: str = None, location: str = None,
                     min_price: float = None, max_price: float = None,
                     status: str = None, page: int = 1, limit: int = 10,token=None):
        try:
            request = post_pb2.SearchPostsRequest(
                property_type=property_type or "",
                location=location or "",
                min_price=min_price or 0.0,
                max_price=max_price or 0.0,
                status=status or "",
                page=page,
                limit=limit
            )
            return self._call(self.stub.SearchPosts, request,token=token)
        except grpc.RpcError as e:
            print(f"Error in search_posts: {str(e)}")
            return None

    def create_post(self, user_id: int, title: str, content: str,
                    visibility: str, property_type: str, location: str,
                    map_location: str, price: float, status: str,
                    media: list = None,token=None) -> dict:
        try:
            media_list = []
            if media:
                for m in media:
                    try:
                        media_data = base64.b64decode(m.mediaData)
                    except Exception as e:
                        return {
                            'success': False,
                            'message': f'Invalid media data format: {str(e)}'
                        }

                    media_upload = post_pb2.PostMediaUpload(
                        media_type=m.mediaType,
                        media_data=media_data,
                        media_order=m.mediaOrder,
                        caption=m.caption
                    )
                    media_list.append(media_upload)

            request = post_pb2.PostCreateRequest(
                user_id=user_id,
                title=title,
                content=content,
                visibility=visibility,
                property_type=property_type,
                location=location,
                map_location=map_location,
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
                    'propertyType': response.post.property_type,
                    'location': response.post.location,
                    'mapLocation': response.post.map_location,
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

            # Convert camelCase to snake_case for property_type and map_location
            if 'propertyType' in update_data:
                update_data['property_type'] = update_data.pop('propertyType')
            if 'mapLocation' in update_data:
                update_data['map_location'] = update_data.pop('mapLocation')

            request = post_pb2.PostUpdateRequest(
                post_id=post_id,
                **update_data
            )
            response = self._call(self.stub.UpdatePost, request,token=token)

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
                    'propertyType': response.post.property_type,
                    'location': response.post.location,
                    'mapLocation': response.post.map_location,
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
                'message': f'Error updating post: {str(e)}',
                'post': None
            }

    def delete_post(self, post_id: int,token=None):
        try:
            request = post_pb2.PostRequest(post_id=post_id)
            response = self._call(self.stub.DeletePost, request,token=token)
            return {
                'success': True,
                'message': 'Post deleted successfully'
            }
        except grpc.RpcError as e:
            return {
                'success': False,
                'message': f'Error deleting post: {str(e)}'
            }

    def get_posts_by_user(self, user_id: int, page: int = 1, limit: int = 10,token=None):
        try:
            request = post_pb2.GetPostsByUserRequest(
                user_id=user_id,
                page=page,
                limit=limit
            )
            response = self._call(self.stub.GetPostsByUser, request,token=token)
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
                    'propertyType': response.post.property_type,
                    'location': response.post.location,
                    'mapLocation': response.post.map_location,
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
                    'propertyType': response.post.property_type,
                    'location': response.post.location,
                    'mapLocation': response.post.map_location,
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
            request = post_pb2.PostRequest(post_id=media_id)
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
                try:
                    media_data = base64.b64decode(m.mediaData)
                except Exception as e:
                    return {
                        'success': False,
                        'message': f'Invalid media data format: {str(e)}'
                    }

                media_upload = post_pb2.PostMediaUpload(
                    media_type=m.mediaType,
                    media_data=media_data,
                    media_order=m.mediaOrder,
                    caption=m.caption
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
                    'propertyType': response.post.property_type,
                    'location': response.post.location,
                    'mapLocation': response.post.map_location,
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
            if response:
                comment_dict = {
                    'id': response.id,
                    'postId': response.post_id,
                    'userId': response.user_id,
                    'comment': response.comment,
                    'parentCommentId': response.parent_comment_id if response.parent_comment_id != 0 else None,
                    'status': response.status,
                    'addedAt': datetime.fromtimestamp(response.added_at),
                    'commentedAt': datetime.fromtimestamp(response.commented_at),
                    'replies': [],  # Replies will be fetched separately if needed
                    'likeCount': response.like_count
                }
            else:
                comment_dict = None

            return {
                'success': True,
                'message': 'Comment updated successfully',
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
            request = post_pb2.PostRequest(post_id=comment_id)  # Using PostRequest for comment_id
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
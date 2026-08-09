import typing
import grpc
import strawberry
from enum import Enum
from uuid import uuid4

from app.clients.auth.auth_client import auth_service_client
from app.clients.user.user_client import user_service_client
from app.schema.user_schema import User, _user_from_proto
from app.utils.log_utils import log_msg


@strawberry.enum
class OTPType(Enum):
    VERIFICATION = 0
    PASSWORD_RESET = 1
    LOGIN = 2


@strawberry.type
class AuthResponse:
    success: bool
    token: typing.Optional[str] = None
    refresh_token: typing.Optional[str] = None
    message: typing.Optional[str] = None
    user_info: typing.Optional[User] = None
    channels: typing.List[str] = strawberry.field(default_factory=list)


def _get_user_by_email(email: str):
    try:
        response = user_service_client.get_user_by_email(email)
        if response and getattr(response, "id", None):
            return response
    except grpc.RpcError as e:
        if e.code() != grpc.StatusCode.NOT_FOUND:
            raise
    return None


def _get_user_by_phone(phone: str):
    try:
        response = user_service_client.get_user_by_phone(phone)
        if response and getattr(response, "id", None):
            return response
    except grpc.RpcError as e:
        if e.code() != grpc.StatusCode.NOT_FOUND:
            raise
    return None


def _auth_success(auth_response, user_proto, message: str) -> AuthResponse:
    return AuthResponse(
        success=True,
        token=auth_response.token,
        refresh_token=getattr(auth_response, "refresh_token", None) or None,
        message=message,
        user_info=_user_from_proto(user_proto) if user_proto else None,
    )


@strawberry.type
class Query:
    @strawberry.field
    def hello(self) -> str:
        return "Hello from Auth Service!"


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def login(self, email: str, password: str) -> AuthResponse:
        try:
            log_msg("info", f"Login attempt for {email}")
            user_proto = _get_user_by_email(email)
            if not user_proto:
                return AuthResponse(success=False, message="User not found")
            if not getattr(user_proto, "is_active", True):
                return AuthResponse(success=False, message="Account is inactive")

            auth_response = auth_service_client.login(
                user_id=user_proto.id,
                password=password,
                email=user_proto.email,
                role=user_proto.role,
            )
            return _auth_success(auth_response, user_proto, "Login successful")
        except grpc.RpcError as e:
            log_msg("error", f"Login error for {email}: {str(e)}")
            if e.code() == grpc.StatusCode.NOT_FOUND:
                return AuthResponse(success=False, message="User not found")
            if e.code() == grpc.StatusCode.PERMISSION_DENIED:
                return AuthResponse(success=False, message=e.details() or "Account is inactive")
            if e.code() == grpc.StatusCode.UNAUTHENTICATED:
                return AuthResponse(success=False, message="Invalid credentials")
            return AuthResponse(success=False, message="Internal server error")

    @strawberry.mutation
    async def google_sign_in(
        self,
        id_token: str,
        role: typing.Optional[str] = None,
        address: typing.Optional[str] = None,
        latitude: typing.Optional[float] = None,
        longitude: typing.Optional[float] = None,
        bio: typing.Optional[str] = None,
        phone: typing.Optional[str] = None,
    ) -> AuthResponse:
        try:
            profile = auth_service_client.verify_google_token(id_token)
            if not getattr(profile, "success", False):
                return AuthResponse(success=False, message=getattr(profile, "message", None) or "Invalid Google account")

            user_proto = _get_user_by_email(profile.email)
            if not user_proto:
                if not role:
                    return AuthResponse(
                        success=False,
                        message="Google account not registered. Please sign up first.",
                    )
                new_user_id = str(uuid4())
                user_proto = user_service_client.create_user(
                    user_id=new_user_id,
                    first_name=profile.first_name,
                    last_name=profile.last_name,
                    email=profile.email,
                    phone=phone or "",
                    role=role,
                    bio=bio or "",
                    latitude=latitude,
                    longitude=longitude,
                )
                auth_service_client.register_credentials(
                    user_proto.id,
                    auth_service_client.random_oauth_password(),
                    "GOOGLE",
                )

            auth_response = auth_service_client.google_sign_in(
                id_token=id_token,
                user_id=user_proto.id,
                email=user_proto.email,
                role=user_proto.role,
            )
            user_service_client.update_verification_flags(user_proto.id, email_verified=True)
            refreshed = user_service_client.get_user(user_proto.id)
            return _auth_success(auth_response, refreshed, "Google sign-in successful")
        except grpc.RpcError as e:
            log_msg("error", f"Google sign-in error: {str(e)}")
            if e.code() == grpc.StatusCode.NOT_FOUND:
                return AuthResponse(success=False, message="Google account not registered. Please sign up first.")
            if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
                return AuthResponse(success=False, message=e.details() or "Missing Google signup details")
            if e.code() == grpc.StatusCode.PERMISSION_DENIED:
                return AuthResponse(success=False, message="Account is inactive")
            if e.code() == grpc.StatusCode.UNAUTHENTICATED:
                return AuthResponse(success=False, message=e.details() or "Invalid Google account")
            return AuthResponse(success=False, message="Google sign-in failed")

    @strawberry.mutation
    async def facebook_sign_in(
        self,
        access_token: str,
        role: typing.Optional[str] = None,
        address: typing.Optional[str] = None,
        latitude: typing.Optional[float] = None,
        longitude: typing.Optional[float] = None,
        bio: typing.Optional[str] = None,
        phone: typing.Optional[str] = None,
    ) -> AuthResponse:
        try:
            profile = auth_service_client.verify_facebook_token(access_token)
            if not getattr(profile, "success", False):
                return AuthResponse(
                    success=False,
                    message=getattr(profile, "message", None) or "Invalid Facebook account",
                )

            user_proto = _get_user_by_email(profile.email)
            if not user_proto:
                if not role:
                    return AuthResponse(
                        success=False,
                        message="Facebook account not registered. Please sign up first.",
                    )
                new_user_id = str(uuid4())
                user_proto = user_service_client.create_user(
                    user_id=new_user_id,
                    first_name=profile.first_name,
                    last_name=profile.last_name,
                    email=profile.email,
                    phone=phone or "",
                    role=role,
                    bio=bio or "",
                    latitude=latitude,
                    longitude=longitude,
                )
                auth_service_client.register_credentials(
                    user_proto.id,
                    auth_service_client.random_oauth_password(),
                    "FACEBOOK",
                )

            auth_response = auth_service_client.facebook_sign_in(
                access_token=access_token,
                user_id=user_proto.id,
                email=user_proto.email,
                role=user_proto.role,
            )
            user_service_client.update_verification_flags(user_proto.id, email_verified=True)
            refreshed = user_service_client.get_user(user_proto.id)
            return _auth_success(auth_response, refreshed, "Facebook sign-in successful")
        except grpc.RpcError as e:
            log_msg("error", f"Facebook sign-in error: {str(e)}")
            if e.code() == grpc.StatusCode.NOT_FOUND:
                return AuthResponse(success=False, message="Facebook account not registered. Please sign up first.")
            if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
                return AuthResponse(success=False, message=e.details() or "Missing Facebook signup details")
            if e.code() == grpc.StatusCode.PERMISSION_DENIED:
                return AuthResponse(success=False, message="Account is inactive")
            if e.code() == grpc.StatusCode.UNAUTHENTICATED:
                return AuthResponse(success=False, message=e.details() or "Invalid Facebook account")
            return AuthResponse(success=False, message="Facebook sign-in failed")

    @strawberry.mutation
    async def send_mobile_otp(self, phone: str) -> AuthResponse:
        try:
            user_proto = _get_user_by_phone(phone)
            if not user_proto:
                return AuthResponse(success=False, message="Phone number not registered")
            if not getattr(user_proto, "is_active", True):
                return AuthResponse(success=False, message="Account is inactive")

            response = auth_service_client.send_mobile_otp(user_proto.id, phone)
            return AuthResponse(
                success=response.success,
                message=response.message,
                channels=list(response.channels),
            )
        except grpc.RpcError as e:
            log_msg("error", f"SendMobileOTP error for {phone}: {str(e)}")
            if e.code() == grpc.StatusCode.NOT_FOUND:
                return AuthResponse(success=False, message="Phone number not registered")
            if e.code() == grpc.StatusCode.PERMISSION_DENIED:
                return AuthResponse(success=False, message="Account is inactive")
            if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
                return AuthResponse(success=False, message=e.details() or "Phone number is required")
            return AuthResponse(success=False, message="Failed to send mobile OTP")

    @strawberry.mutation
    async def verify_mobile_otp(self, phone: str, otp_code: str) -> AuthResponse:
        try:
            user_proto = _get_user_by_phone(phone)
            if not user_proto:
                return AuthResponse(success=False, message="Phone number not registered")
            if not getattr(user_proto, "is_active", True):
                return AuthResponse(success=False, message="Account is inactive")

            auth_response = auth_service_client.verify_mobile_otp(
                user_id=user_proto.id,
                phone=phone,
                otp_code=otp_code,
                email=user_proto.email,
                role=user_proto.role,
            )
            user_service_client.update_verification_flags(user_proto.id, phone_verified=True)
            refreshed = user_service_client.get_user(user_proto.id)
            return _auth_success(auth_response, refreshed, "Mobile sign-in successful")
        except grpc.RpcError as e:
            log_msg("error", f"VerifyMobileOTP error for {phone}: {str(e)}")
            if e.code() == grpc.StatusCode.NOT_FOUND:
                return AuthResponse(success=False, message=e.details() or "OTP expired or phone number not registered")
            if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
                return AuthResponse(success=False, message=e.details() or "Invalid OTP")
            if e.code() == grpc.StatusCode.PERMISSION_DENIED:
                return AuthResponse(success=False, message="Account is inactive")
            return AuthResponse(success=False, message="Failed to verify mobile OTP")

    @strawberry.mutation
    async def send_otp(
        self,
        email: str,
        phone: typing.Optional[str] = None,
        type: OTPType = OTPType.VERIFICATION,
    ) -> AuthResponse:
        try:
            log_msg("info", f"Sending OTP to {email}")
            user_proto = _get_user_by_email(email)
            if not user_proto:
                return AuthResponse(success=False, message="User not found")
            if not getattr(user_proto, "is_active", True):
                return AuthResponse(success=False, message="Account is inactive")
            if type == OTPType.VERIFICATION and user_proto.email_verified:
                return AuthResponse(success=False, message="Email already verified")

            response = auth_service_client.send_otp(user_proto.id, email, phone, type)
            return AuthResponse(
                success=response.success,
                message=response.message,
                channels=list(response.channels),
            )
        except grpc.RpcError as e:
            log_msg("error", f"SendOTP error for {email}: {str(e)}")
            if e.code() == grpc.StatusCode.NOT_FOUND:
                return AuthResponse(success=False, message="User not found")
            if e.code() == grpc.StatusCode.PERMISSION_DENIED:
                return AuthResponse(success=False, message="Account is inactive")
            return AuthResponse(success=False, message="Failed to send OTP")

    @strawberry.mutation
    async def verify_otp(
        self,
        email: str,
        otp_code: str,
        type: OTPType = OTPType.VERIFICATION,
    ) -> AuthResponse:
        try:
            log_msg("info", f"Verifying OTP for {email}")
            user_proto = _get_user_by_email(email)
            if not user_proto:
                return AuthResponse(success=False, message="User not found")
            if not getattr(user_proto, "is_active", True):
                return AuthResponse(success=False, message="Account is inactive")

            response = auth_service_client.verify_otp(user_proto.id, email, otp_code, type)
            if not response.success:
                return AuthResponse(success=False, message=response.message)

            refreshed = user_proto
            if type == OTPType.VERIFICATION:
                refreshed = user_service_client.update_verification_flags(
                    user_proto.id, email_verified=True
                )
            elif type == OTPType.LOGIN:
                auth_response = auth_service_client.issue_tokens(
                    user_proto.id, user_proto.email, user_proto.role
                )
                return _auth_success(auth_response, refreshed, response.message)

            return AuthResponse(success=True, message=response.message, user_info=_user_from_proto(refreshed))
        except grpc.RpcError as e:
            log_msg("error", f"VerifyOTP error for {email}: {str(e)}")
            if e.code() == grpc.StatusCode.NOT_FOUND:
                return AuthResponse(success=False, message="User not found or OTP expired")
            if e.code() == grpc.StatusCode.PERMISSION_DENIED:
                return AuthResponse(success=False, message="Account is inactive")
            if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
                return AuthResponse(success=False, message="Invalid OTP")
            return AuthResponse(success=False, message="Failed to verify OTP")

    @strawberry.mutation
    async def forgot_password(self, email: str, phone: typing.Optional[str] = None) -> AuthResponse:
        try:
            log_msg("info", f"Forgot password request for {email}")
            user_proto = _get_user_by_email(email)
            if not user_proto:
                return AuthResponse(success=False, message="User not found")
            if not getattr(user_proto, "is_active", True):
                return AuthResponse(success=False, message="Account is inactive")

            response = auth_service_client.forgot_password(user_proto.id, email, phone)
            return AuthResponse(
                success=response.success,
                message=response.message,
                channels=list(response.channels),
            )
        except grpc.RpcError as e:
            log_msg("error", f"ForgotPassword error for {email}: {str(e)}")
            if e.code() == grpc.StatusCode.NOT_FOUND:
                return AuthResponse(success=False, message="User not found")
            if e.code() == grpc.StatusCode.PERMISSION_DENIED:
                return AuthResponse(success=False, message="Account is inactive")
            return AuthResponse(success=False, message="Failed to process password reset request")

    @strawberry.mutation
    async def reset_password(
        self,
        email: str,
        otp_code: str,
        new_password: str,
        confirm_password: str,
    ) -> AuthResponse:
        try:
            if new_password != confirm_password:
                return AuthResponse(success=False, message="Passwords do not match")

            user_proto = _get_user_by_email(email)
            if not user_proto:
                return AuthResponse(success=False, message="User not found")
            if not getattr(user_proto, "is_active", True):
                return AuthResponse(success=False, message="Account is inactive")

            log_msg("info", f"Reset password request for {email}")
            response = auth_service_client.reset_password(
                user_proto.id,
                email,
                otp_code,
                new_password,
                confirm_password,
            )
            return AuthResponse(
                success=response.success,
                message=response.message,
                user_info=_user_from_proto(user_proto) if response.success else None,
            )
        except grpc.RpcError as e:
            log_msg("error", f"ResetPassword error for {email}: {str(e)}")
            if e.code() == grpc.StatusCode.NOT_FOUND:
                return AuthResponse(success=False, message="User not found")
            if e.code() == grpc.StatusCode.PERMISSION_DENIED:
                return AuthResponse(success=False, message="Account is inactive")
            if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
                return AuthResponse(success=False, message="Invalid or expired OTP")
            return AuthResponse(success=False, message="Failed to reset password")

    @strawberry.mutation
    async def logout(self, token: str, refresh_token: typing.Optional[str] = None) -> AuthResponse:
        try:
            log_msg("info", "Logout request")
            response = auth_service_client.logout(token, refresh_token)
            return AuthResponse(success=response.success, message=response.message)
        except grpc.RpcError as e:
            log_msg("error", f"Logout error: {str(e)}")
            return AuthResponse(success=False, message="Failed to logout")

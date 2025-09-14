import typing
import strawberry
from app.clients.auth.auth_client import auth_service_client
from app.utils.log_utils import log_msg
import grpc
from enum import Enum

@strawberry.enum
class OTPType(Enum):
    VERIFICATION = 0
    PASSWORD_RESET = 1
    LOGIN = 2

@strawberry.type
class UserInfo:
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

@strawberry.type
class AuthResponse:
    success: bool
    token: typing.Optional[str] = None
    refresh_token: typing.Optional[str] = None
    message: typing.Optional[str] = None
    user_info: typing.Optional[UserInfo] = None
    channels: typing.List[str] = strawberry.field(default_factory=list)

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
            response = auth_service_client.login(email, password)
            return AuthResponse(
                success=True,
                token=response.token,
                refresh_token=response.refresh_token,
                message="Login successful",
                user_info=UserInfo(
                    id=response.user_info.id,
                    first_name=response.user_info.first_name,
                    last_name=response.user_info.last_name,
                    email=response.user_info.email,
                    phone=response.user_info.phone,
                    profile_photo=response.user_info.profile_photo,
                    role=response.user_info.role,
                    address=response.user_info.address,
                    latitude=response.user_info.latitude,
                    longitude=response.user_info.longitude,
                    bio=response.user_info.bio,
                    isactive=response.user_info.isactive,
                    email_verified=response.user_info.email_verified,
                    phone_verified=response.user_info.phone_verified,
                    created_at=response.user_info.created_at
                ) if response.user_info else None
            )
        except grpc.RpcError as e:
            log_msg("error", f"Login error for {email}: {str(e)}")
            if e.code() == grpc.StatusCode.NOT_FOUND:
                return AuthResponse(success=False, message="User not found")
            if e.code() == grpc.StatusCode.PERMISSION_DENIED:
                return AuthResponse(success=False, message="Account is inactive")
            if e.code() == grpc.StatusCode.UNAUTHENTICATED:
                return AuthResponse(success=False, message="Invalid credentials")
            return AuthResponse(success=False, message="Internal server error")

    @strawberry.mutation
    async def send_otp(
        self, 
        email: str, 
        phone: typing.Optional[str] = None,
        type: OTPType = OTPType.VERIFICATION
    ) -> AuthResponse:
        try:
            log_msg("info", f"Sending OTP to {email}")
            response = auth_service_client.send_otp(email, phone, type)
            return AuthResponse(
                success=response.success,
                message=response.message,
                channels=response.channels
            )
        except grpc.RpcError as e:
            log_msg("error", f"SendOTP error for {email}: {str(e)}")
            if e.code() == grpc.StatusCode.NOT_FOUND:
                return AuthResponse(success=False, message="User not found")
            if e.code() == grpc.StatusCode.PERMISSION_DENIED:
                return AuthResponse(success=False, message="Account is inactive")
            if e.code() == grpc.StatusCode.ALREADY_EXISTS:
                return AuthResponse(success=False, message="Email already verified")
            return AuthResponse(success=False, message="Failed to send OTP")

    @strawberry.mutation
    async def verify_otp(
        self, 
        email: str, 
        otp_code: str,
        type: OTPType = OTPType.VERIFICATION
    ) -> AuthResponse:
        try:
            log_msg("info", f"Verifying OTP for {email}")
            response = auth_service_client.verify_otp(email, otp_code, type)
            return AuthResponse(
                success=response.success,
                token=response.token,
                message=response.message,
                user_info=UserInfo(
                    id=response.user_info.id,
                    first_name=response.user_info.first_name,
                    last_name=response.user_info.last_name,
                    email=response.user_info.email,
                    phone=response.user_info.phone,
                    profile_photo=response.user_info.profile_photo,
                    role=response.user_info.role,
                    address=response.user_info.address,
                    latitude=response.user_info.latitude,
                    longitude=response.user_info.longitude,
                    bio=response.user_info.bio,
                    isactive=response.user_info.isactive,
                    email_verified=response.user_info.email_verified,
                    phone_verified=response.user_info.phone_verified,
                    created_at=response.user_info.created_at
                ) if response.user_info else None
            )
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
    async def forgot_password(
        self, 
        email: str,
        phone: typing.Optional[str] = None
    ) -> AuthResponse:
        try:
            log_msg("info", f"Forgot password request for {email}")
            response = auth_service_client.forgot_password(email, phone)
            return AuthResponse(
                success=response.success,
                message=response.message,
                channels=response.channels
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
        confirm_password: str
    ) -> AuthResponse:
        try:
            if new_password != confirm_password:
                return AuthResponse(success=False, message="Passwords do not match")

            log_msg("info", f"Reset password request for {email}")
            response = auth_service_client.reset_password(
                email,
                otp_code,
                new_password,
                confirm_password
            )
            return AuthResponse(
                success=response.success,
                message=response.message,
                user_info=UserInfo(
                    id=response.user_info.id,
                    first_name=response.user_info.first_name,
                    last_name=response.user_info.last_name,
                    email=response.user_info.email,
                    phone=response.user_info.phone,
                    profile_photo=response.user_info.profile_photo,
                    role=response.user_info.role,
                    address=response.user_info.address,
                    latitude=response.user_info.latitude,
                    longitude=response.user_info.longitude,
                    bio=response.user_info.bio,
                    isactive=response.user_info.isactive,
                    email_verified=response.user_info.email_verified,
                    phone_verified=response.user_info.phone_verified,
                    created_at=response.user_info.created_at
                ) if response.user_info else None
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
    async def logout(
        self, 
        token: str,
        refresh_token: typing.Optional[str] = None
    ) -> AuthResponse:
        try:
            log_msg("info", "Logout request")
            response = auth_service_client.logout(token, refresh_token)
            return AuthResponse(
                success=response.success,
                message=response.message
            )
        except grpc.RpcError as e:
            log_msg("error", f"Logout error: {str(e)}")
            return AuthResponse(success=False, message="Failed to logout") 
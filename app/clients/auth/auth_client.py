import os
import secrets
from dotenv import load_dotenv

from app.clients.grpc_base_client import GRPCBaseClient
from app.proto_files.auth import auth_pb2, auth_pb2_grpc

load_dotenv()


def _str_id(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


class AuthServiceClient(GRPCBaseClient):
    def __init__(self):
        target = os.getenv("AUTH_SERVICE_URL", "localhost:50052")
        super().__init__(auth_pb2_grpc.AuthServiceStub, target=target)

    def register_credentials(self, user_id: str, password: str, auth_provider: str = "LOCAL"):
        request = auth_pb2.RegisterCredentialsRequest(
            user_id=_str_id(user_id),
            password=password or "",
            auth_provider=auth_provider or "LOCAL",
        )
        return self._call(self.stub.RegisterCredentials, request, require_token=False)

    def login(self, user_id: str, password: str, email: str = "", role: str = ""):
        request = auth_pb2.LoginRequest(
            user_id=_str_id(user_id),
            password=password,
            email=email or "",
            role=role or "",
        )
        return self._call(self.stub.Login, request, require_token=False)

    def issue_tokens(self, user_id: str, email: str = "", role: str = ""):
        request = auth_pb2.IssueTokensRequest(
            user_id=_str_id(user_id),
            email=email or "",
            role=role or "",
        )
        return self._call(self.stub.IssueTokens, request, require_token=False)

    def verify_google_token(self, id_token: str):
        request = auth_pb2.VerifyGoogleTokenRequest(id_token=id_token)
        return self._call(self.stub.VerifyGoogleToken, request, require_token=False)

    def verify_facebook_token(self, access_token: str):
        request = auth_pb2.VerifyFacebookTokenRequest(access_token=access_token)
        return self._call(self.stub.VerifyFacebookToken, request, require_token=False)

    def google_sign_in(self, id_token: str, user_id: str, email: str = "", role: str = ""):
        request = auth_pb2.GoogleSignInRequest(
            id_token=id_token,
            user_id=_str_id(user_id),
            email=email or "",
            role=role or "",
        )
        return self._call(self.stub.GoogleSignIn, request, require_token=False)

    def facebook_sign_in(self, access_token: str, user_id: str, email: str = "", role: str = ""):
        request = auth_pb2.FacebookSignInRequest(
            access_token=access_token,
            user_id=_str_id(user_id),
            email=email or "",
            role=role or "",
        )
        return self._call(self.stub.FacebookSignIn, request, require_token=False)

    def send_mobile_otp(self, user_id: str, phone: str):
        request = auth_pb2.MobileOTPRequest(user_id=_str_id(user_id), phone=phone)
        return self._call(self.stub.SendMobileOTP, request, require_token=False)

    def verify_mobile_otp(self, user_id: str, phone: str, otp_code: str, email: str = "", role: str = ""):
        request = auth_pb2.VerifyMobileOTPRequest(
            user_id=_str_id(user_id),
            phone=phone,
            otp_code=otp_code,
            email=email or "",
            role=role or "",
        )
        return self._call(self.stub.VerifyMobileOTP, request, require_token=False)

    def logout(self, token: str, refresh_token: str = None):
        request = auth_pb2.LogoutRequest(token=token, refresh_token=refresh_token or "")
        return self._call(self.stub.Logout, request, require_token=False)

    def validate_token(self, token: str):
        request = auth_pb2.ValidateTokenRequest(token=token)
        return self._call(self.stub.ValidateToken, request, require_token=False)

    def send_otp(self, user_id: str, email: str, phone: str = None, otp_type: int = 0):
        request = auth_pb2.OTPRequest(
            user_id=_str_id(user_id),
            email=email,
            phone=phone or "",
            type=otp_type.value if hasattr(otp_type, "value") else otp_type,
        )
        return self._call(self.stub.SendOTP, request, require_token=False)

    def verify_otp(self, user_id: str, email: str, otp_code: str, otp_type: int = 0):
        request = auth_pb2.VerifyOTPRequest(
            user_id=_str_id(user_id),
            email=email,
            otp_code=otp_code,
            type=otp_type.value if hasattr(otp_type, "value") else otp_type,
        )
        return self._call(self.stub.VerifyOTP, request, require_token=False)

    def forgot_password(self, user_id: str, email: str, phone: str = None):
        request = auth_pb2.ForgotPasswordRequest(
            user_id=_str_id(user_id),
            email=email,
            phone=phone or "",
        )
        return self._call(self.stub.ForgotPassword, request, require_token=False)

    def reset_password(
        self,
        user_id: str,
        email: str,
        otp_code: str,
        new_password: str,
        confirm_password: str,
    ):
        request = auth_pb2.ResetPasswordRequest(
            user_id=_str_id(user_id),
            email=email,
            otp_code=otp_code,
            new_password=new_password,
            confirm_password=confirm_password,
        )
        return self._call(self.stub.ResetPassword, request, require_token=False)

    @staticmethod
    def random_oauth_password() -> str:
        return secrets.token_urlsafe(32)


auth_service_client = AuthServiceClient()

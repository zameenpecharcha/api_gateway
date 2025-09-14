from app.clients.grpc_base_client import GRPCBaseClient
from app.proto_files.auth import auth_pb2_grpc, auth_pb2


class AuthServiceClient(GRPCBaseClient):
    def __init__(self):
        super().__init__(auth_pb2_grpc.AuthServiceStub, target='localhost:50052')

    def login(self, email: str, password: str):
        request = auth_pb2.LoginRequest(
            email=email,
            password=password
        )
        return self._call(self.stub.Login, request, require_token=False)

    def logout(self, token: str, refresh_token: str = None):
        request = auth_pb2.LogoutRequest(
            token=token,
            refresh_token=refresh_token or ""
        )
        return self._call(self.stub.Logout, request, require_token=False)

    def validate_token(self, token: str):
        request = auth_pb2.ValidateTokenRequest(token=token)
        return self._call(self.stub.ValidateToken, request,require_token=False)

    def send_otp(self, email: str, phone: str = None, otp_type: int = 0):
        request = auth_pb2.OTPRequest(
            email=email,
            phone=phone,
            type=otp_type.value if hasattr(otp_type, 'value') else otp_type
        )
        return self._call(self.stub.SendOTP, request, require_token=False)

    def verify_otp(self, email: str, otp_code: str, otp_type: int = 0):
        request = auth_pb2.VerifyOTPRequest(
            email=email,
            otp_code=otp_code,
            type=otp_type.value if hasattr(otp_type, 'value') else otp_type
        )
        return self._call(self.stub.VerifyOTP, request,require_token=False)

    def forgot_password(self, email: str, phone: str = None):
        request = auth_pb2.ForgotPasswordRequest(
            email=email,
            phone=phone
        )
        return self._call(self.stub.ForgotPassword, request,require_token=False)

    def reset_password(self, email: str, otp_code: str, new_password: str, confirm_password: str):
        request = auth_pb2.ResetPasswordRequest(
            email=email,
            otp_code=otp_code,
            new_password=new_password,
            confirm_password=confirm_password
        )
        return self._call(self.stub.ResetPassword, request,require_token=False)

auth_service_client=AuthServiceClient()
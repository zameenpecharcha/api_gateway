from typing import Optional

import jwt

# Load public key (safe to load on all services)
with open("config/public.pem", "r") as f:
    PUBLIC_KEY = f.read()

def decode_jwt_token(token: str):
    try:
        payload = jwt.decode(
            token,
            PUBLIC_KEY,
            algorithms=["RS256"],
            audience="graphql-api",
            issuer="ZPC"
        )

        return payload  # contains session_id, user_id, email, role, etc.

    except jwt.ExpiredSignatureError:
        raise Exception("Token expired")

    except jwt.InvalidTokenError as e:
        raise Exception(f"Invalid token: {str(e)}")


def get_token(info):
    auth_header = info.context["request"].headers.get("Authorization")
    if not auth_header:
        return None
    return auth_header.replace("Bearer ", "").strip()


def peek_user_id_from_authorization(auth_header: Optional[str]) -> Optional[str]:
    """Read user id from a JWT for logging only — does not authenticate the request."""
    if not auth_header:
        return None
    token = auth_header.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if not token or token.count(".") < 2:
        return None
    try:
        payload = jwt.decode(
            token,
            options={
                "verify_signature": False,
                "verify_aud": False,
                "verify_exp": False,
                "verify_iss": False,
            },
            algorithms=["HS256", "RS256"],
        )
    except Exception:
        return None
    for key in ("sub", "user_id", "userId", "id"):
        value = payload.get(key)
        if value:
            return str(value)
    return None

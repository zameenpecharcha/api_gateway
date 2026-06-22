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

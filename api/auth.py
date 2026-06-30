import os
from dataclasses import dataclass

from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client, create_client


load_dotenv()

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str
    email: str | None = None
    is_admin : bool = False


def _get_supabase_auth_client():
    supabase_url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    publishable_key = os.getenv("SUPABASE_PUBLISHABLE_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")

    if not supabase_url:
        raise RuntimeError("SUPABASE_URL is not set in the environment")
    if not publishable_key:
        raise RuntimeError("SUPABASE_PUBLISHABLE_KEY is not set in the environment")

    return create_client(supabase_url, publishable_key)

def get_is_admin(client : Client, user_id : str) -> bool:
    response = client.rpc(
        'check_admin_exists', 
        {'target_user_id': user_id}
        ).execute()
    is_admin = bool(response.data) # Output: True or False
    return is_admin

def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing bearer token")

    try:
        client = _get_supabase_auth_client()
        user_response = client.auth.get_user(credentials.credentials)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid bearer token") from exc

    user = getattr(user_response, "user", None)
    user_id = getattr(user, "id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid bearer token")

    is_admin = get_is_admin(client, user_id)

    return AuthenticatedUser(
        id=user_id,
        email=getattr(user, "email", None),
        is_admin= is_admin
    )

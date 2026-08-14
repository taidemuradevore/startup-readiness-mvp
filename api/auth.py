import os
from dataclasses import dataclass

from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import create_client


load_dotenv()

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str
    email: str | None = None
    is_admin: bool = False


def _get_supabase_url() -> str:
    supabase_url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    if not supabase_url:
        raise RuntimeError("SUPABASE_URL is not set in the environment")
    return supabase_url


def _get_supabase_auth_client():
    publishable_key = os.getenv("SUPABASE_PUBLISHABLE_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
    if not publishable_key:
        raise RuntimeError("SUPABASE_PUBLISHABLE_KEY is not set in the environment")

    return create_client(_get_supabase_url(), publishable_key)


def _get_supabase_admin_client():
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not service_role_key:
        return None

    return create_client(_get_supabase_url(), service_role_key)


def _coerce_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, list):
        if not value:
            return False
        return _coerce_bool(value[0])
    if isinstance(value, dict):
        for key in ("check_admin_exists", "exists", "is_admin"):
            if key in value:
                return _coerce_bool(value[key])
        if len(value) == 1:
            return _coerce_bool(next(iter(value.values())))
    return bool(value)


def get_is_admin(user_id: str) -> bool:
    client = _get_supabase_admin_client()
    if client is None:
        return False

    try:
        response = client.rpc(
            "check_admin_exists",
            {"target_user_id": user_id},
        ).execute()
    except Exception as exc:
        print("admin_lookup_failed", {"user_id": user_id, "error": str(exc)})
        return False

    return _coerce_bool(response.data)


def _metadata_marks_admin(metadata) -> bool:
    if not isinstance(metadata, dict):
        return False
    for key in ("is_admin", "admin"):
        if _coerce_bool(metadata.get(key)):
            return True
    roles = metadata.get("roles") or metadata.get("role")
    if isinstance(roles, str):
        return roles.lower() == "admin"
    if isinstance(roles, list):
        return any(str(role).lower() == "admin" for role in roles)
    return False

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

    is_admin = (
        get_is_admin(user_id)
        or _metadata_marks_admin(getattr(user, "app_metadata", None))
        or _metadata_marks_admin(getattr(user, "user_metadata", None))
    )

    return AuthenticatedUser(
        id=user_id,
        email=getattr(user, "email", None),
        is_admin=is_admin,
    )

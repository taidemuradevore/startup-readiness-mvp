import io
import os
import posixpath
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from supabase import Client, create_client


load_dotenv()


class SupabaseStorageError(RuntimeError):
    pass


class SupabaseStorageClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        service_role_key: str | None = None,
        bucket_name: str | None = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("SUPABASE_URL") or "").rstrip("/")
        self.service_role_key = service_role_key or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        self.bucket_name = bucket_name or os.getenv("SUPABASE_DECKS_BUCKET", "Decks")

        if not self.base_url:
            raise ValueError("SUPABASE_URL is not set in the environment")
        if not self.service_role_key:
            raise ValueError("SUPABASE_SERVICE_ROLE_KEY is not set in the environment")

        self.client: Client = create_client(self.base_url, self.service_role_key)

    def upload_deck_pdf(self, *, file_bytes: bytes, original_filename: str | None, content_type: str | None) -> dict:
        safe_filename = self._sanitize_filename(original_filename or "deck.pdf")
        object_path = self._build_object_path(safe_filename)

        try:
            response = self.client.storage.from_(self.bucket_name).upload(
                path=object_path,
                file=file_bytes,
                file_options={
                    "content-type": content_type or "application/pdf",
                    "upsert": "false",
                },
            )
        except Exception as exc:
            raise SupabaseStorageError(f"Supabase storage upload failed: {exc}") from exc

        if isinstance(response, dict):
            payload = response
        elif hasattr(response, "model_dump"):
            payload = response.model_dump()
        elif hasattr(response, "dict"):
            payload = response.dict()
        else:
            payload = {"response": str(response)}

        payload.setdefault("Key", f"{self.bucket_name}/{object_path}")
        payload.setdefault("path", object_path)
        return payload

    def create_signed_url(self, object_path: str, expires_in: int = 3600) -> str:
        try:
            response = self.client.storage.from_(self.bucket_name).create_signed_url(object_path, expires_in)
        except Exception as exc:
            raise SupabaseStorageError(f"Supabase signed URL generation failed: {exc}") from exc

        if isinstance(response, dict):
            payload = response
        elif hasattr(response, "model_dump"):
            payload = response.model_dump()
        elif hasattr(response, "dict"):
            payload = response.dict()
        else:
            payload = {"signedURL": str(response)}

        signed_url = payload.get("signedURL") or payload.get("signed_url")
        if not signed_url:
            raise SupabaseStorageError("Supabase signed URL generation failed: missing signed URL in response")

        if signed_url.startswith("http://") or signed_url.startswith("https://"):
            return signed_url
        return f"{self.base_url}{signed_url}"

    def delete_object(self, object_path: str) -> None:
        try:
            self.client.storage.from_(self.bucket_name).remove([object_path])
        except Exception as exc:
            raise SupabaseStorageError(f"Supabase object delete failed: {exc}") from exc

    def _build_object_path(self, filename: str) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y/%m/%d")
        unique_name = f"{uuid.uuid4().hex}_{filename}"
        return posixpath.join("evaluations", timestamp, unique_name)

    def _sanitize_filename(self, filename: str) -> str:
        cleaned = "".join(ch if ch.isalnum() or ch in {".", "-", "_"} else "_" for ch in filename)
        return cleaned.strip("._") or "deck.pdf"

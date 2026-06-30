import io
import os

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from google.genai import errors as genai_errors
import uvicorn

try:
    from .auth import AuthenticatedUser, get_current_user
    from .llm_parser import Deck, DeckParser, PitchDeckEvaluation
    from .supabase_storage import SupabaseStorageClient, SupabaseStorageError
    from .upload_to_sql import SQLDatabase
except ImportError:
    from auth import AuthenticatedUser, get_current_user
    from llm_parser import Deck, DeckParser, PitchDeckEvaluation
    from supabase_storage import SupabaseStorageClient, SupabaseStorageError
    from upload_to_sql import SQLDatabase


class JsonDeckRequest(BaseModel):
    json_path: str = Field(..., description="Path to a local JSON file containing a deck")

class IngestDeckRequest(BaseModel):
    json_path: str = Field(..., description="Path to a local JSON file containing a deck")

class SQLDeckRequest(BaseModel):
    deck_id: str = Field(..., description="ID of deck in SQL server")

class EvalDeckRequest(BaseModel):
    pdf_path: str = Field(..., description="Path to a local PDF file containing a deck")
    eval : bool = Field(..., description="Determines whether or not a deck is fully evaluated")

app = FastAPI(title="Deck Ingestion API")

def _cors_origins() -> list[str]:
    configured_origins = os.getenv("FRONTEND_ORIGINS", "")
    origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "https://startup-readiness-mvp.vercel.app",
    ]
    origins.extend(origin.strip().rstrip("/") for origin in configured_origins.split(",") if origin.strip())
    return list(dict.fromkeys(origins))


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
db = SQLDatabase()


def _get_storage_client() -> SupabaseStorageClient:
    return SupabaseStorageClient()


def _maybe_get_storage_client() -> SupabaseStorageClient | None:
    try:
        return _get_storage_client()
    except ValueError:
        return None


def _attach_storage_urls(deck_payload):
    storage = _maybe_get_storage_client()
    if storage is None:
        return deck_payload

    def enrich(item):
        storage_object_path = item.get("storage_object_path")
        if not storage_object_path:
            return item
        try:
            item["deck_pdf_url"] = storage.create_signed_url(storage_object_path, expires_in=3600)
        except SupabaseStorageError:
            item["deck_pdf_url"] = None
        return item

    if isinstance(deck_payload, list):
        return [enrich(item) for item in deck_payload]
    return enrich(deck_payload)


def _evaluate_and_ingest(pdf_path: str, eval_flag: bool, owner_id: str) -> PitchDeckEvaluation:
    parser = DeckParser(eval_flag)
    deck = parser.evaluate_pitch_deck(pdf_path)
    conn = db.connect()
    db.ingest_deck(conn, deck, eval_included=True, owner_id=owner_id)
    return deck

@app.get("/api/health")
def return_health():
    return {"status" : "healthy"}

@app.get("/api/decks")
def list_decks_endpoint(current_user: AuthenticatedUser = Depends(get_current_user)):
    try:
        conn = db.connect()
        try:
            decks = db.list_decks(conn, current_user.id, current_user.is_admin)
            print(
                "list_decks",
                {"user_id": current_user.id, "deck_ids": [deck.get("deck_id") for deck in decks]},
            )
            return _attach_storage_urls(decks)
        finally:
            conn.close()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/decks/{deck_id}")
def retrieve_deck_metadata_endpoint(
    deck_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        conn = db.connect()
        try:
            deck = db.retrieve_deck_metadata(conn, deck_id, current_user.id, current_user.is_admin)
            print(
                "retrieve_deck_metadata",
                {"user_id": current_user.id, "deck_id": deck_id, "found": True},
            )
            return _attach_storage_urls(deck)
        finally:
            conn.close()
    except ValueError as exc:
        print(
            "retrieve_deck_metadata",
            {"user_id": current_user.id, "deck_id": deck_id, "found": False, "error": str(exc)},
        )
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/decks/{deck_id}/slides")
def retrieve_deck_slides_endpoint(
    deck_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        conn = db.connect()
        try:
            slides = db.retrieve_slides(conn, deck_id, current_user.id, current_user.is_admin)
            print(
                "retrieve_deck_slides",
                {"user_id": current_user.id, "deck_id": deck_id, "slide_count": len(slides)},
            )
            return slides
        finally:
            conn.close()
    except ValueError as exc:
        print(
            "retrieve_deck_slides",
            {"user_id": current_user.id, "deck_id": deck_id, "found": False, "error": str(exc)},
        )
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.delete("/api/decks/{deck_id}")
def delete_deck_endpoint(
    deck_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        conn = db.connect()
        try:
            deleted = db.delete_deck(conn, deck_id, current_user.id)
        finally:
            conn.close()

        storage_object_path = deleted.get("storage_object_path")
        if storage_object_path:
            storage = _maybe_get_storage_client()
            if storage is not None:
                storage.delete_object(storage_object_path)

        return {"status": "ok", "deck_id": deck_id}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SupabaseStorageError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@app.post("/api/decks/from-json", response_model=Deck)
def load_deck_from_json_endpoint(
    request: JsonDeckRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Deck:
    try:
        return db.load_deck_from_json(request.json_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    
@app.post("/api/decks/retrieve", response_model=Deck)
def load_deck_from_sql_endpoint(
    request: SQLDeckRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Deck:
    try:
        conn = db.connect()
        return db.retrieve_deck(conn, request.deck_id, current_user.id, current_user.is_admin)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    
@app.post("/api/decks/evaluate", response_model=PitchDeckEvaluation)
def evaluate_deck_endpoint(
    request: EvalDeckRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> PitchDeckEvaluation:
    try:
        return _evaluate_and_ingest(request.pdf_path, request.eval, current_user.id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except genai_errors.ServerError as exc:
        raise HTTPException(
            status_code=503,
            detail="Gemini is temporarily unavailable due to high demand. Retry shortly.",
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/decks/evaluate-upload", response_model=PitchDeckEvaluation)
async def evaluate_deck_upload_endpoint(
    file: UploadFile = File(...),
    eval: bool = Form(True),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> PitchDeckEvaluation:
    try:
        print("evaluate_upload:start", {"user_id": current_user.id, "filename": file.filename})
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        print("evaluate_upload:file_read", {"bytes": len(file_bytes), "content_type": file.content_type})

        storage = _get_storage_client()
        storage_result = storage.upload_deck_pdf(
            file_bytes=file_bytes,
            original_filename=file.filename,
            content_type=file.content_type,
        )
        print("evaluate_upload:storage_uploaded", {"path": storage_result.get("path") or storage_result.get("Key")})

        parser = DeckParser(eval)
        uploaded_file = parser.client.files.upload(
            file=io.BytesIO(file_bytes),
            config={"mime_type": file.content_type or "application/pdf", "display_name": file.filename or "deck.pdf"},
        )
        print("evaluate_upload:gemini_uploaded", {"name": uploaded_file.name})

        deck = parser._evaluate_uploaded_file(uploaded_file)
        print("evaluate_upload:evaluated", {"company": deck.deck.company if deck.deck else None})

        conn = db.connect()
        db.ingest_deck(
            conn,
            deck,
            eval_included=True,
            storage_object_path=storage_result.get("path") or storage_result.get("Key"),
            owner_id=current_user.id,
        )
        print("evaluate_upload:ingested", {"user_id": current_user.id})
        return deck
    except HTTPException:
        raise
    except genai_errors.ServerError as exc:
        raise HTTPException(
            status_code=503,
            detail="Gemini is temporarily unavailable due to high demand. Retry shortly.",
        ) from exc
    except SupabaseStorageError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        await file.close()

@app.post("/api/decks/ingest-from-json")
def ingest_deck_from_json_endpoint(
    request: IngestDeckRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        deck = db.load_deck_from_json(request.json_path)
        conn = db.connect()
        db.ingest_deck(conn, deck, owner_id=current_user.id)
        deck_id = db._make_deck_id(deck, current_user.id)
        return {"status": "ok", "deck_id": deck_id, "company": deck.company}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


if __name__ == "__main__":
    uvicorn.run(app=app)

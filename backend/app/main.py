from contextlib import asynccontextmanager
import logging
from pathlib import Path
from urllib.parse import quote

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.auth import current_user, hash_password, issue_token, verify_password
from app.config import settings
from app.schemas import Credentials, Profile
from app.services.diet_engine import generate_plan
from app.services.store import Store, get_store

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.app_mode.lower() != "supabase":
        get_store()
    yield


app = FastAPI(title="AI-Powered Personal Diet Planner API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["Authorization", "Content-Type"])
logger = logging.getLogger("diet_planner")


@app.exception_handler(Exception)
async def safe_unexpected_error(request, exc):
    # Keep implementation details and provider error payloads out of the response body.
    logger.error("Unhandled request failure on %s %s (%s)", request.method, request.url.path, type(exc).__name__)
    return JSONResponse(status_code=503, content={"detail": "The data service is temporarily unavailable. Please retry."})


@app.get("/health")
def health():
    return {"status": "ok", "mode": settings.app_mode.lower()}


@app.post("/register", status_code=201)
def register(payload: Credentials, store: Store = Depends(get_store)):
    if settings.app_mode.lower() == "supabase":
        try:
            result = store.auth_client().auth.sign_up({"email": payload.email, "password": payload.password})
            if not result.user:
                raise HTTPException(status_code=400, detail="Registration could not be completed")
            token = result.session.access_token if result.session else ""
            return {"access_token": token, "token_type": "bearer", "user": {"user_id": result.user.id, "email": result.user.email}, "email_confirmation_required": not bool(token)}
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Could not register this account") from exc
    if store.local_user_by_email(payload.email):
        raise HTTPException(status_code=409, detail="Email is already registered")
    user = store.register(payload.email, hash_password(payload.password))
    return {"access_token": issue_token(user["user_id"], user["email"]), "token_type": "bearer", "user": user}


@app.post("/login")
def login(payload: Credentials, store: Store = Depends(get_store)):
    if settings.app_mode.lower() == "supabase":
        try:
            result = store.auth_client().auth.sign_in_with_password({"email": payload.email, "password": payload.password})
            return {"access_token": result.session.access_token, "token_type": "bearer", "user": {"user_id": result.user.id, "email": result.user.email}}
        except Exception as exc:
            raise HTTPException(status_code=401, detail="Invalid email or password") from exc
    user = store.local_user_by_email(payload.email)
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {"access_token": issue_token(user["id"], user["email"]), "token_type": "bearer", "user": {"user_id": user["id"], "email": user["email"]}}


@app.get("/profile")
def get_profile(user=Depends(current_user), store: Store = Depends(get_store)):
    profile = store.get_profile(user)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@app.put("/profile")
def update_profile(payload: Profile, user=Depends(current_user), store: Store = Depends(get_store)):
    return store.save_profile(user, payload.model_dump())


@app.post("/generate-plan", status_code=201)
async def create_plan(user=Depends(current_user), store: Store = Depends(get_store)):
    profile = store.get_profile(user)
    if not profile:
        raise HTTPException(status_code=400, detail="Complete your profile before generating a plan")
    result = await generate_plan(profile)
    return store.create_plan(user["user_id"], result)


@app.get("/plans")
def list_plans(user=Depends(current_user), store: Store = Depends(get_store)):
    return store.list_plans(user["user_id"])


@app.get("/plans/{plan_id}")
def get_plan(plan_id: str, user=Depends(current_user), store: Store = Depends(get_store)):
    plan = store.get_plan(user["user_id"], plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@app.delete("/plans/{plan_id}", status_code=204)
def delete_plan(plan_id: str, user=Depends(current_user), store: Store = Depends(get_store)):
    if not store.delete_plan(user["user_id"], plan_id):
        raise HTTPException(status_code=404, detail="Plan not found")


@app.post("/upload", status_code=201)
async def upload_file(file: UploadFile = File(...), user=Depends(current_user), store: Store = Depends(get_store)):
    name = Path(file.filename or "upload").name
    if file.content_type not in ALLOWED_TYPES or Path(name).suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(status_code=415, detail="Upload a JPEG, PNG, or WebP image")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if not content or len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File must be between 1 byte and 5 MB")
    signatures = {"image/png": content.startswith(b"\x89PNG\r\n\x1a\n"), "image/jpeg": content.startswith(b"\xff\xd8\xff"), "image/webp": len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP"}
    if not signatures.get(file.content_type, False):
        raise HTTPException(status_code=415, detail="The file contents do not match an allowed image format")
    return store.save_file(user["user_id"], name, content, file.content_type)


@app.get("/files")
def list_files(user=Depends(current_user), store: Store = Depends(get_store)):
    return store.list_files(user["user_id"])


@app.get("/files/{file_id}/download")
def download_file(file_id: str, user=Depends(current_user), store: Store = Depends(get_store)):
    result = store.download_file(user["user_id"], file_id)
    if not result:
        raise HTTPException(status_code=404, detail="File not found")
    metadata, content = result
    media_type = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}.get(Path(metadata["filename"]).suffix.lower(), "application/octet-stream")
    safe_filename = quote(metadata["filename"], safe="")
    return Response(content, media_type=media_type, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{safe_filename}"})


@app.delete("/files/{file_id}", status_code=204)
def delete_file(file_id: str, user=Depends(current_user), store: Store = Depends(get_store)):
    if not store.delete_file(user["user_id"], file_id):
        raise HTTPException(status_code=404, detail="File not found")

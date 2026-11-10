from contextlib import asynccontextmanager
import asyncio
import io
import logging
from pathlib import Path
from urllib.parse import quote
import wave

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import httpx

from app.auth import current_user, hash_password, issue_token, verify_password
from app.config import settings
from app.schemas import Credentials, Profile, VoiceQuestion, VoiceSpeech
from app.services.diet_engine import generate_plan
from app.services.store import Store, get_store

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_VOICE_SECONDS = 30
GNANI_STT_URL = "https://api.vachana.ai/stt/v3"
GNANI_TTS_URL = "https://api.vachana.ai/api/v1/tts/inference"
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


@app.post("/transcribe")
async def transcribe_voice(audio_file: UploadFile = File(...), user=Depends(current_user)):
    """Proxy a short WAV recording to Gnani Prisma without exposing its key."""
    if not settings.gnani_api_key:
        raise HTTPException(status_code=503, detail="Voice transcription is not configured yet. Add GNANI_API_KEY to backend/.env and restart the API.")
    filename = Path(audio_file.filename or "recording.wav").name
    if audio_file.content_type != "audio/wav" or Path(filename).suffix.lower() != ".wav":
        raise HTTPException(status_code=415, detail="This audio format is not supported. Record a WAV audio clip and try again.")
    content = await audio_file.read(MAX_UPLOAD_BYTES + 1)
    if not content or len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="The recording is empty or too large. Record a clip under 30 seconds and try again.")
    try:
        with wave.open(io.BytesIO(content), "rb") as audio:
            duration = audio.getnframes() / audio.getframerate()
            valid_wav = audio.getnchannels() == 1 and audio.getsampwidth() == 2 and 8000 <= audio.getframerate() <= 44100
    except (wave.Error, EOFError, ZeroDivisionError):
        valid_wav = False
        duration = 0
    if not valid_wav:
        raise HTTPException(status_code=415, detail="The recording could not be read. Please record again using a supported WAV microphone format.")
    if duration <= 0 or duration > MAX_VOICE_SECONDS:
        raise HTTPException(status_code=413, detail="Record a question between 1 and 30 seconds long.")

    try:
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(
                GNANI_STT_URL,
                headers={"X-API-Key-ID": settings.gnani_api_key},
                files={"audio_file": (filename, content, "audio/wav")},
                data={"model": "prisma-v3.0", "language_code": "indic-auto", "format": "transcribe"},
            )
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Transcription took too long. Please try again with a shorter recording.") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="Could not reach the transcription service. Check your connection and try again.") from exc
    if response.is_error:
        logger.warning("Gnani transcription failed with HTTP %s", response.status_code)
        raise HTTPException(status_code=502, detail="The transcription service could not process this recording. Please try again.")
    try:
        result = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="The transcription service returned an unreadable response. Please try again.") from exc
    transcript = result.get("transcript") if isinstance(result, dict) else None
    if not isinstance(transcript, str) or not transcript.strip():
        raise HTTPException(status_code=502, detail="No speech was detected. Try speaking clearly and recording again.")
    return {"transcript": transcript.strip(), "detected_language_code": result.get("detected_language_code")}


@app.post("/ask")
async def answer_voice_question(payload: VoiceQuestion, user=Depends(current_user), store: Store = Depends(get_store)):
    """Answer an edited voice transcript with a server-side Gemini model call."""
    if not settings.gemini_api_key:
        raise HTTPException(status_code=503, detail="AI replies are not configured yet. Add GEMINI_API_KEY to backend/.env and restart the API.")

    profile = store.get_profile(user)
    plans = store.list_plans(user["user_id"])
    planner_context = {"food_preference": profile.get("dietary_preference")} if profile else {}
    if profile:
        planner_context["general_goal"] = profile.get("goal")
    if plans:
        latest = plans[0]
        planner_context["latest_sample_plan"] = {
            meal: latest.get(meal) for meal in ("breakfast", "lunch", "snack", "dinner")
        }

    system_instruction = (
        "You are a friendly meal-idea assistant. Give a short, practical reply in the language of the user's question when possible. "
        "Use only the provided planner context when personalizing. Offer general meal ideas and wellness information only. "
        "Do not diagnose, treat, prescribe, recommend medication, promise health outcomes, or guarantee calorie or nutrition values. "
        "For medical or medication questions, say you cannot advise and suggest asking a qualified health professional. "
        "Do not claim to know allergies or health details that were not provided."
    )
    prompt = f"Planner context (may be empty): {planner_context}\n\nQuestion: {payload.question.strip()}"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            for attempt in range(2):
                response = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent",
                    headers={"x-goog-api-key": settings.gemini_api_key},
                    json={
                        "systemInstruction": {"parts": [{"text": system_instruction}]},
                        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 256},
                    },
                )
                if response.status_code != 503 or attempt == 1:
                    break
                await asyncio.sleep(0.7)
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="The AI reply took too long. Please try again.") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="Could not reach the AI reply service. Please check your connection and try again.") from exc
    if response.status_code == 429:
        raise HTTPException(status_code=503, detail="The Gemini free-tier request limit has been reached for now. Please wait and try again.")
    if response.status_code == 503:
        logger.warning("Gemini answer request is temporarily unavailable (HTTP 503)")
        raise HTTPException(status_code=503, detail="Gemini is temporarily unavailable right now. Please try sending your question again shortly.")
    if response.status_code in (401, 403):
        logger.warning("Gemini rejected the configured API credentials (HTTP %s)", response.status_code)
        raise HTTPException(status_code=503, detail="Gemini rejected the configured API key. Check that GEMINI_API_KEY is active and enabled for the Gemini API, then restart the backend.")
    if response.status_code == 404:
        logger.warning("Configured Gemini model is unavailable (HTTP 404)")
        raise HTTPException(status_code=503, detail="The configured Gemini model is unavailable. Check GEMINI_MODEL in backend/.env and restart the backend.")
    if response.is_error:
        logger.warning("Gemini answer request failed with HTTP %s", response.status_code)
        raise HTTPException(status_code=502, detail="The AI service could not answer this question right now. Please try again.")
    try:
        result = response.json()
        parts = result["candidates"][0]["content"]["parts"]
        answer = "\n".join(part["text"] for part in parts if isinstance(part.get("text"), str)).strip()
    except (ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
        raise HTTPException(status_code=502, detail="The AI service returned an unreadable reply. Please try again.") from exc
    if not answer:
        raise HTTPException(status_code=502, detail="The AI service returned an empty reply. Please try again.")
    return {"answer": answer, "model": settings.gemini_model}


@app.post("/speak")
async def speak_voice_reply(payload: VoiceSpeech, user=Depends(current_user)):
    """Synthesize the visible reply with Gnani Timbre and return real WAV audio."""
    if not settings.gnani_api_key:
        raise HTTPException(status_code=503, detail="Spoken replies are not configured. Add GNANI_API_KEY to backend/.env and restart the API.")

    request_data = {
        "text": payload.text.strip(),
        "voice": "Shivani",
        "model": settings.gnani_tts_model,
        "language": payload.language,
        "speed": 1.0,
        "audio_config": {
            "sample_rate": 24000,
            "num_channels": 1,
            "sample_width": 2,
            "encoding": "linear_pcm",
            "container": "wav",
        },
    }
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                GNANI_TTS_URL,
                headers={"X-API-Key-ID": settings.gnani_api_key},
                json=request_data,
            )
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Speech generation took too long. Please try again.") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="Could not reach Gnani Timbre. Please try again.") from exc

    if response.status_code == 429:
        raise HTTPException(status_code=503, detail="Gnani Timbre is busy with another request. Wait a moment and try again.")
    if response.status_code in (401, 403, 402):
        logger.warning("Gnani Timbre rejected the configured API key or account (HTTP %s)", response.status_code)
        raise HTTPException(status_code=503, detail="Gnani Timbre could not use this API key. Check its TTS access and available credits in Gnani, then restart the backend.")
    if response.status_code == 503:
        raise HTTPException(status_code=503, detail="Gnani Timbre is temporarily unavailable. Please try again shortly.")
    if response.is_error:
        logger.warning("Gnani Timbre request failed with HTTP %s", response.status_code)
        raise HTTPException(status_code=502, detail="Gnani Timbre could not generate speech for this reply. Please try again.")
    if not response.content.startswith(b"RIFF") or response.content[8:12] != b"WAVE":
        logger.warning("Gnani Timbre returned a non-WAV response")
        raise HTTPException(status_code=502, detail="Gnani Timbre returned an unreadable audio file. Please try again.")
    return Response(
        content=response.content,
        media_type="audio/wav",
        headers={"Cache-Control": "no-store", "X-Audio-Model": settings.gnani_tts_model},
    )


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

from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings
from app.services.store import Store, get_store

passwords = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return passwords.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return passwords.verify(password, hashed)


def issue_token(user_id: str, email: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode({"sub": user_id, "email": email, "exp": expires}, settings.jwt_secret, algorithm="HS256")


async def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    store: Store = Depends(get_store),
) -> dict:
    if not credentials:
        raise HTTPException(status_code=401, detail="Bearer token required")
    token = credentials.credentials
    if settings.app_mode.lower() == "supabase":
        try:
            user = store.verify_supabase_token(token)
            return {"user_id": user["id"], "email": user.get("email", "")}
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid or expired Supabase token")
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return {"user_id": claims["sub"], "email": claims["email"]}
    except (JWTError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

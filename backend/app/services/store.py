import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends
from supabase import Client, create_client

from app.config import settings


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    """A small adapter: local SQLite/files for offline demos; Supabase for cloud mode."""

    def __init__(self):
        self.cloud = settings.app_mode.lower() == "supabase"
        self.client: Client | None = None
        if self.cloud:
            if not settings.supabase_url or not settings.supabase_service_role_key or not settings.supabase_anon_key:
                raise RuntimeError("Supabase mode requires URL, anon key, and service role key")
            self.client = create_client(settings.supabase_url, settings.supabase_service_role_key)
        else:
            db_path = Path(settings.database_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            with self.connect() as conn:
                conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, profile TEXT, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS plans (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, data TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS files (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, filename TEXT NOT NULL, storage_path TEXT NOT NULL, uploaded_at TEXT NOT NULL);
                """)

    def connect(self):
        conn = sqlite3.connect(settings.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def verify_supabase_token(self, token: str) -> dict:
        result = self.auth_client().auth.get_user(token)
        user = result.user
        return {"id": user.id, "email": user.email}

    @staticmethod
    def auth_client():
        """Use an isolated anon-key client so Auth session state cannot alter DB credentials."""
        if not settings.supabase_url or not settings.supabase_anon_key:
            raise RuntimeError("Supabase Auth URL and anon key are required")
        return create_client(settings.supabase_url, settings.supabase_anon_key)

    def register(self, email: str, password_hash: str) -> dict:
        uid, created = str(uuid.uuid4()), now_iso()
        with self.connect() as conn:
            conn.execute("INSERT INTO users VALUES (?, ?, ?, NULL, ?)", (uid, email.lower(), password_hash, created))
        return {"user_id": uid, "email": email.lower(), "created_at": created}

    def local_user_by_email(self, email: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()
        return dict(row) if row else None

    def get_profile(self, user: dict) -> dict | None:
        if self.cloud:
            result = self.client.table("profiles").select("*").eq("user_id", user["user_id"]).maybe_single().execute()
            return result.data
        with self.connect() as conn:
            row = conn.execute("SELECT profile FROM users WHERE id = ?", (user["user_id"],)).fetchone()
        if not row or not row["profile"]:
            return None
        return {**json.loads(row["profile"]), "user_id": user["user_id"], "email": user["email"], "created_at": ""}

    def save_profile(self, user: dict, profile: dict) -> dict:
        record = {**profile, "user_id": user["user_id"], "email": user["email"], "created_at": now_iso()}
        if self.cloud:
            result = self.client.table("profiles").upsert({**profile, "user_id": user["user_id"], "email": user["email"]}).execute()
            return result.data[0]
        with self.connect() as conn:
            conn.execute("UPDATE users SET profile = ? WHERE id = ?", (json.dumps(profile), user["user_id"]))
        return record

    def create_plan(self, user_id: str, data: dict) -> dict:
        plan_id, created = str(uuid.uuid4()), now_iso()
        record = {**data, "plan_id": plan_id, "user_id": user_id, "created_at": created}
        if self.cloud:
            result = self.client.table("diet_plans").insert({"id": plan_id, "user_id": user_id, **data}).execute()
            return self._plan_from_db(result.data[0])
        with self.connect() as conn:
            conn.execute("INSERT INTO plans VALUES (?, ?, ?, ?)", (plan_id, user_id, json.dumps(data), created))
        return record

    def list_plans(self, user_id: str) -> list[dict]:
        if self.cloud:
            rows = self.client.table("diet_plans").select("*").eq("user_id", user_id).order("created_at", desc=True).execute().data
            return [self._plan_from_db(row) for row in rows]
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM plans WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
        return [{**json.loads(row["data"]), "plan_id": row["id"], "user_id": user_id, "created_at": row["created_at"]} for row in rows]

    def get_plan(self, user_id: str, plan_id: str) -> dict | None:
        return next((plan for plan in self.list_plans(user_id) if plan["plan_id"] == plan_id), None)

    @staticmethod
    def _plan_from_db(row: dict) -> dict:
        return {"plan_id": row.get("id", row.get("plan_id")), "user_id": row["user_id"], **{k: row[k] for k in ("breakfast", "lunch", "snack", "dinner", "nutrition_summary", "hydration_reminder", "educational_notice", "source")}, "created_at": row["created_at"]}

    def save_file(self, user_id: str, filename: str, content: bytes, content_type: str) -> dict:
        file_id, uploaded = str(uuid.uuid4()), now_iso()
        safe_name = Path(filename).name
        storage_path = f"{user_id}/{file_id}/{safe_name}"
        if self.cloud:
            self.client.storage.from_("user-files").upload(storage_path, content, {"content-type": content_type, "upsert": "false"})
            self.client.table("user_files").insert({"id": file_id, "user_id": user_id, "filename": safe_name, "storage_path": storage_path}).execute()
        else:
            target = Path(settings.local_storage_path) / storage_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            with self.connect() as conn:
                conn.execute("INSERT INTO files VALUES (?, ?, ?, ?, ?)", (file_id, user_id, safe_name, storage_path, uploaded))
        return {"file_id": file_id, "user_id": user_id, "filename": safe_name, "storage_path": storage_path, "uploaded_at": uploaded}

    def list_files(self, user_id: str) -> list[dict]:
        if self.cloud:
            rows = self.client.table("user_files").select("*").eq("user_id", user_id).order("uploaded_at", desc=True).execute().data
            return [{"file_id": r["id"], "user_id": user_id, "filename": r["filename"], "storage_path": r["storage_path"], "uploaded_at": r["uploaded_at"]} for r in rows]
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM files WHERE user_id = ? ORDER BY uploaded_at DESC", (user_id,)).fetchall()
        return [{"file_id": r["id"], "user_id": user_id, "filename": r["filename"], "storage_path": r["storage_path"], "uploaded_at": r["uploaded_at"]} for r in rows]

    def download_file(self, user_id: str, file_id: str) -> tuple[dict, bytes] | None:
        record = next((item for item in self.list_files(user_id) if item["file_id"] == file_id), None)
        if not record:
            return None
        if self.cloud:
            content = self.client.storage.from_("user-files").download(record["storage_path"])
        else:
            content = (Path(settings.local_storage_path) / record["storage_path"]).read_bytes()
        return record, content

    def delete_plan(self, user_id: str, plan_id: str) -> bool:
        if not self.get_plan(user_id, plan_id):
            return False
        if self.cloud:
            self.client.table("diet_plans").delete().eq("user_id", user_id).eq("id", plan_id).execute()
        else:
            with self.connect() as conn:
                conn.execute("DELETE FROM plans WHERE user_id = ? AND id = ?", (user_id, plan_id))
        return True

    def delete_file(self, user_id: str, file_id: str) -> bool:
        record = next((item for item in self.list_files(user_id) if item["file_id"] == file_id), None)
        if not record:
            return False
        if self.cloud:
            self.client.storage.from_("user-files").remove([record["storage_path"]])
            self.client.table("user_files").delete().eq("user_id", user_id).eq("id", file_id).execute()
        else:
            (Path(settings.local_storage_path) / record["storage_path"]).unlink(missing_ok=True)
            with self.connect() as conn:
                conn.execute("DELETE FROM files WHERE user_id = ? AND id = ?", (user_id, file_id))
        return True


_store: Store | None = None


def get_store() -> Store:
    global _store
    if _store is None:
        _store = Store()
    return _store

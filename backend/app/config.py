from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_mode: str = "local"
    database_path: str = "./data/diet_planner.db"
    local_storage_path: str = "./data/uploads"
    jwt_secret: str = "replace-with-a-long-random-value"
    jwt_expire_minutes: int = 720
    cors_origins: str = "http://localhost:5173"
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()

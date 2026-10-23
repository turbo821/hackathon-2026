from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- БД ---
    # SQLite. Относительный путь (sqlite:///) Flask-SQLAlchemy разрешает
    # относительно папки instance приложения: backend/instance/app.db
    database_url: str = "sqlite:///app.db"
    sqlalchemy_track_modifications: bool = False

    # --- JWT ---
    jwt_secret_key: str = "dev-only-secret-change-me-in-env-file-please"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 720

    # --- Администратор (только из .env, через API не управляется) ---
    admin_username: str = "admin"
    admin_password: str = "admin"

    # --- Даты ---
    # Единый часовой пояс приложения: «сегодня», просрочка и напоминания считаются в нём
    app_timezone: str = "Europe/Moscow"

    # --- Напоминания ---
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    reminder_days_before: int = 3
    reminder_check_interval_seconds: int = 60

    # --- CORS ---
    cors_origins: str = "*"


settings = Settings()

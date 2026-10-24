from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # .env ищется и в корне репозитория (как в docker-compose), и в папке backend/
    # (как при локальном запуске `uvicorn main:app` из backend/). Файл рядом с
    # backend/ имеет приоритет. В Docker значения приходят из переменных окружения —
    # они важнее любого файла.
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    # --- БД ---
    # SQLite-файл backend/instance/app.db (путь относительно папки backend)
    database_url: str = "sqlite:///./instance/app.db"

    # --- JWT ---
    jwt_secret_key: str = "dev-only-secret-change-me-in-env-file-please"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 720

    # --- Администратор (только из .env, через API не управляется) ---
    admin_username: str = "admin"
    admin_password: str = "admin"
    admin_email: str = "admin@example.com"

    # --- Даты ---
    # Единый часовой пояс приложения: «сегодня», просрочка и напоминания считаются в нём
    app_timezone: str = "Europe/Moscow"

    # --- Напоминания ---
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    reminder_days_before: int = 3
    reminder_check_interval_seconds: int = 60

    # --- Тестовые данные ---
    # Скрипт scripts.seed_demo создаёт демо-платежи (аренда/сервер/подписка).
    seed_demo_data: bool = True

    # --- CORS ---
    cors_origins: str = "*"


settings = Settings()
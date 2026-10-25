from pydantic import BaseModel, EmailStr, SecretStr
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

    # --- Суперадмин (только из .env, через API не управляется)
    superadmin_username: str = "superadmin"
    superadmin_password: str = "superadmin"
    superadmin_email: str = "superadmin@example.com"

    # --- Даты ---
    # Единый часовой пояс приложения: «сегодня», просрочка и напоминания считаются в нём
    app_timezone: str = "Europe/Moscow"

    # --- Напоминания ---
    reminder_days_before: int = 3
    reminder_check_interval_seconds: int = 60
    # --- Telegram ---
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    # Чат, в который пользователи вступают по ссылке с сайта. Бот должен быть
    # в нём администратором с правом can_invite_users.
    telegram_group_chat_id: str = ""
    # --- SMTP ---
    smtp_host: str = "smtp.mail.ru"
    smtp_port: int = 465
    # Адрес ящика (он же логин на сервере) и пароль задаются только в .env:
    # в коде секреты и чужие адреса не держим.
    smtp_addr: EmailStr | None = None
    smtp_password: SecretStr = SecretStr("")
    smtp_name: str = "Invoice Keeper"
    smtp_subject: str = "Напоминание об оплате"
    # SOCKS5-прокси для SMTP: socks5://host:port. Нужен там, где до почтового
    # сервера не достучаться напрямую (например, провайдер режет исходящие
    # SMTP-порты или закрыт IPv4).
    smtp_proxy: str = ""
    # STARTTLS вместо TLS на подключении: порт 587 вместо 465. У Mail.ru
    # на 465 отказывает, а 587 работает.
    smtp_starttls: bool = False

    # --- Тестовые данные ---
    # Скрипт scripts.seed_demo создаёт демо-платежи (аренда/сервер/подписка).
    seed_demo_data: bool = True

    # --- CORS ---
    cors_origins: str = "*"

    # --- Логирование ---
    # Уровень корневого логгера: DEBUG, INFO, WARNING, ERROR.
    # DEBUG подробно показывает запросы SQL — полезно при разборе, но шумно.
    log_level: str = "INFO"
    # Формат записей: text (человекочитаемо) или json (для сервера и парсинга).
    log_format: str = "text"
    # Уровень для сторонних библиотек (uvicorn, httpx, sqlalchemy).
    # WARNING — видны только проблемы, а не рутина.
    log_level_libraries: str = "WARNING"

    telegram_bot_username: str = ""


settings = Settings()

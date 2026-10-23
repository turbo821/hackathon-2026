from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # SQLALCHEMY_TRACK_MODIFICATIONS = False
    sqlalchemy_track_modifications: bool = False
    # SQLite. Относительный путь (sqlite:///) Flask-SQLAlchemy разрешает
    # относительно папки instance приложения: backend/instance/app.db
    database_url: str = "sqlite:///app.db"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # jwt
    jwt_secret_key: str = "qwerty"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60


settings = Settings()

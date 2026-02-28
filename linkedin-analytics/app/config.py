"""Application configuration loaded from environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_port: int = 8050
    data_dir: Path = Path("/app/data")
    log_level: str = "info"
    max_upload_size_mb: int = 50

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "linkedin.db"

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.db_path}"


settings = Settings()

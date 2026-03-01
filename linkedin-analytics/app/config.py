"""Application configuration loaded from environment variables."""

from pathlib import Path
from urllib.parse import urlparse

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_port: int = 8050
    data_dir: Path = Path("/app/data")
    log_level: str = "info"
    max_upload_size_mb: int = 50

    # LinkedIn OAuth (all optional; if client_id is empty, OAuth features are disabled)
    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""
    token_encryption_key: str = ""  # Fernet key (generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    linkedin_api_version: str = "202601"
    linkedin_redirect_uri: str = "http://localhost:8050/oauth/callback"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @field_validator("token_encryption_key")
    @classmethod
    def validate_fernet_key(cls, v: str) -> str:
        """Validate that the token encryption key is a valid Fernet key at startup.

        If the key is empty, OAuth is disabled (no error). If the key is set but
        invalid, fail fast with a clear error rather than crashing mid-token-exchange.
        """
        if not v:
            return v
        try:
            from cryptography.fernet import Fernet
            Fernet(v.encode())
        except Exception as e:
            raise ValueError(
                f"TOKEN_ENCRYPTION_KEY is not a valid Fernet key: {e}. "
                f"Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        return v

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "linkedin.db"

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.db_path}"

    @property
    def oauth_enabled(self) -> bool:
        """Return True if LinkedIn OAuth is fully configured."""
        return bool(
            self.linkedin_client_id
            and self.linkedin_client_secret
            and self.token_encryption_key
        )


def validate_redirect_uri(s: "Settings") -> None:
    """Validate redirect URI path matches the callback route at startup."""
    import logging
    parsed = urlparse(s.linkedin_redirect_uri)
    if parsed.path != "/oauth/callback":
        raise ValueError(
            f"LINKEDIN_REDIRECT_URI path must be '/oauth/callback', got '{parsed.path}'"
        )
    if parsed.hostname not in ("localhost", "127.0.0.1"):
        logging.getLogger(__name__).warning(
            "LINKEDIN_REDIRECT_URI host is '%s', not localhost. "
            "Ensure HTTPS is configured and the URI matches the LinkedIn developer portal.",
            parsed.hostname,
        )


settings = Settings()

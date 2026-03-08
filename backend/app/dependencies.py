# Shared dependency injection helpers
# Example: get_db, get_current_user, etc.

from app.config import get_settings, Settings


def get_settings_dep() -> Settings:
    """FastAPI dependency to inject settings."""
    return get_settings()

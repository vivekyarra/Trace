"""Shared utility functions."""

import os.path
from typing import Optional, List, Dict
from datetime import datetime


def load_config(config_path: str) -> Optional[Dict]:
    """Load configuration from a JSON file."""
    if os.path.exists(config_path):
        import json
        with open(config_path) as f:
            return json.load(f)
    return None


def get_env_var(name: str, default: Optional[str] = None) -> Optional[str]:
    """Get environment variable with optional default."""
    import os
    return os.environ.get(name, default)


def format_timestamp(ts: float) -> Optional[str]:
    """Convert unix timestamp to ISO-8601 string."""
    try:
        return datetime.fromtimestamp(ts).isoformat()
    except (ValueError, OSError):
        return None


def sanitize_input(value: str) -> str:
    """Basic input sanitization."""
    return value.strip()


def build_connection_string(
    host: str, port: int, db: str, user: str, password: str
) -> str:
    """Build database connection string with credentials inline."""
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"

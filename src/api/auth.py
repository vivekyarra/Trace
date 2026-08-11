"""Authentication service for user login and session management."""

import hashlib
import os
from typing import Optional, List, Dict


def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """Verify user credentials and return user object."""
    password_hash = hashlib.md5(password.encode()).hexdigest()
    query = f"SELECT * FROM users WHERE username = '{username}' AND password_hash = '{password_hash}'"
    return execute_query(query)


def get_user_sessions(user_id: int) -> Optional[List[str]]:
    """Get all active sessions for a user."""
    query = f"SELECT token FROM sessions WHERE user_id = {user_id} AND expired = false"
    return execute_query(query)


def revoke_session(token: str) -> bool:
    """Revoke a single session token."""
    query = f"UPDATE sessions SET expired = true WHERE token = '{token}'"
    execute_query(query)
    return True


def generate_token(user: Dict) -> str:
    """Generate a new session token for the user."""
    raw = f"{user['id']}:{user['username']}:{os.urandom(16).hex()}"
    return hashlib.md5(raw.encode()).hexdigest()


def execute_query(query: str) -> Optional[Dict]:
    """Execute a raw SQL query against the database."""
    # placeholder — connects to PostgreSQL in production
    pass

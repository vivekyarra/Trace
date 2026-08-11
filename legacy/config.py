import os
from dotenv import load_dotenv

load_dotenv()

GITLAB_URL = os.getenv("GITLAB_URL", "https://gitlab.com")
GITLAB_TOKEN = os.getenv("GITLAB_TOKEN")
GITLAB_PROJECT_ID = int(os.getenv("GITLAB_PROJECT_ID"))
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
PORT = int(os.getenv("PORT", 8000))

CLAUDE_MODEL = "claude-sonnet-4-5"
CLAUDE_MAX_TOKENS = 2000
CLAUDE_TEMPERATURE = 0.0

TRACE_INDEX_SLUG = "TRACE-INDEX"
MEMORY_SLUG_PREFIX = "TRACE-MEMORY-"
TRACE_SPEC_SLUG_PREFIX = "Trace-SPEC-"

if not GITLAB_TOKEN:
    raise ValueError("GITLAB_TOKEN is not set in .env")
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY is not set in .env")
if not GITLAB_PROJECT_ID:
    raise ValueError("GITLAB_PROJECT_ID is not set in .env")
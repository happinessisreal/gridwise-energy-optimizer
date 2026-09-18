"""
Configuration settings for the GridWise Energy Optimizer service.
"""
import os
from pathlib import Path

# Automatically load .env file if present
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    try:
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k and k not in os.environ:
                        os.environ[k] = v
    except Exception:
        pass

class Settings:
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # LLM Configuration
    # Supported providers: deepseek, groq, openai, gemini, openrouter, local, fallback
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "").lower().strip()
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "")
    
    # Auto-detection if not explicitly specified
    if not LLM_PROVIDER:
        if os.getenv("DEEPSEEK_API_KEY"):
            LLM_PROVIDER = "deepseek"
        elif os.getenv("GROQ_API_KEY"):
            LLM_PROVIDER = "groq"
        elif os.getenv("OPENAI_API_KEY"):
            LLM_PROVIDER = "openai"
        elif os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
            LLM_PROVIDER = "gemini"
        else:
            LLM_PROVIDER = "fallback"

    # Populate defaults based on the resolved LLM_PROVIDER
    if LLM_PROVIDER == "deepseek":
        LLM_API_KEY = LLM_API_KEY or os.getenv("DEEPSEEK_API_KEY", "")
        LLM_MODEL = LLM_MODEL or "deepseek-flash"
        LLM_BASE_URL = LLM_BASE_URL or "https://api.deepseek.com"
    elif LLM_PROVIDER == "groq":
        LLM_API_KEY = LLM_API_KEY or os.getenv("GROQ_API_KEY", "")
        LLM_MODEL = LLM_MODEL or "llama-3.3-70b-versatile"
        LLM_BASE_URL = LLM_BASE_URL or "https://api.groq.com/openai/v1"
    elif LLM_PROVIDER == "openai":
        LLM_API_KEY = LLM_API_KEY or os.getenv("OPENAI_API_KEY", "")
        LLM_MODEL = LLM_MODEL or "gpt-4o-mini"
        LLM_BASE_URL = LLM_BASE_URL or os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
    elif LLM_PROVIDER == "gemini":
        LLM_API_KEY = LLM_API_KEY or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
        LLM_MODEL = LLM_MODEL or "gemini-1.5-flash"
        LLM_BASE_URL = LLM_BASE_URL or "https://generativelanguage.googleapis.com/v1beta/openai"

    REQUEST_TIMEOUT: float = float(os.getenv("REQUEST_TIMEOUT", "20.0"))

settings = Settings()

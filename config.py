"""
Hermes Agent Configuration Module
Handles environment variables, runtime settings, and strict single-user owner lock.
"""

import json
import os
from pathlib import Path
from typing import List, Optional

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
CONFIG_JSON_PATH = BASE_DIR / "data" / "config.json"

# Strict authorized owner username
OWNER_USERNAME = "kissbilla2"


def load_env() -> None:
    """Manually parse .env without external dependencies."""
    if not ENV_PATH.exists():
        return
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


load_env()

# API Keys & Secrets
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8954487031:AAEv9-RzsecVcnJyVfd3pfEOYYfiBGh9Fzg")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_KEY_2 = os.getenv("GEMINI_API_KEY_2", "")
APIKEY_2CAPTCHA = os.getenv("APIKEY_2CAPTCHA", os.getenv("TWO_CAPTCHA_API_KEY", ""))
_keys_raw = os.getenv("GEMINI_API_KEYS", "")
if _keys_raw:
    GEMINI_API_KEYS = [k.strip() for k in _keys_raw.split(",") if k.strip()]
else:
    GEMINI_API_KEYS = [k for k in [GEMINI_API_KEY, GEMINI_API_KEY_2] if k]
WORKSPACE_DIR = Path(os.getenv("WORKSPACE_DIR", str(BASE_DIR))).resolve()

# Multi-Provider Models (2026 Verified Working)
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_MODELS = [
    "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-20b",
]

GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-flash-latest",
    "gemini-2.5-pro",
]
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

OPENROUTER_MODELS = [
    "qwen/qwen3.8-27b:free",
    "nvidia/nemotron-3.5-lightning:free",
    "liquid/lfm-2.5-2.6b:free",
]

# Ensure data dir exists
(BASE_DIR / "data").mkdir(exist_ok=True)
(BASE_DIR / "logs").mkdir(exist_ok=True)


def get_runtime_config() -> dict:
    """Load dynamic settings from data/config.json."""
    if not CONFIG_JSON_PATH.exists():
        default_config = {
            "owner_username": OWNER_USERNAME,
            "owner_user_id": 8616271645,
            "allowed_user_ids": [8616271645],
            "bot_name": "Dadijiibot",
            "active_model": "gemini",
        }
        with open(CONFIG_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=2)
        return default_config
    try:
        with open(CONFIG_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"owner_username": OWNER_USERNAME, "owner_user_id": 8616271645, "allowed_user_ids": [8616271645]}


def save_runtime_config(data: dict) -> None:
    """Save dynamic settings to data/config.json."""
    with open(CONFIG_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def set_owner(user_id: int) -> None:
    """Lock ownership to given user_id."""
    cfg = get_runtime_config()
    cfg["owner_user_id"] = user_id
    cfg["allowed_user_ids"] = [user_id]
    save_runtime_config(cfg)


def is_user_allowed(user_id: int, username: Optional[str] = None) -> bool:
    """
    STRICT AUTHORIZATION:
    ONLY @kissbilla2 (and user_id 8616271645) is permitted full access.
    All other users are completely blocked.
    """
    # 1. Match by Telegram @username
    if username and username.lower().lstrip("@") == OWNER_USERNAME.lower():
        cfg = get_runtime_config()
        if cfg.get("owner_user_id") != user_id:
            cfg["owner_user_id"] = user_id
            cfg["allowed_user_ids"] = [user_id]
            save_runtime_config(cfg)
        return True

    # 2. Match by verified numeric ID
    cfg = get_runtime_config()
    owner_id = cfg.get("owner_user_id")
    if owner_id and user_id == owner_id:
        return True

    return False

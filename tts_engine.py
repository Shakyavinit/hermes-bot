"""
Multi-Provider TTS Engine Module
Supports Edge-TTS (with SSML Deep Baritone & Native Devanagari Tuning),
and pluggable adapters for Sarvam Bulbul v3 & ElevenLabs v4.
"""

import os
import json
import logging
import asyncio
from pathlib import Path
from typing import Dict, Optional

from normalizer import normalize_for_hindi_tts

logger = logging.getLogger("TTSEngine")

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = DATA_DIR / "voice_config.json"

# Voice Profiles Registry
VOICE_PROFILES: Dict[str, dict] = {
    "andrew_copilot": {
        "name": "Andrew Copilot (Realistic Male)",
        "voice": "en-US-AndrewMultilingualNeural",
        "provider": "edge_tts",
        "is_ssml": False,
        "volume": "+40%",
        "lang": "en-US",
        "description": "Warm, natural realistic male voice (100% Free Default)",
    },
    "brian_copilot": {
        "name": "Brian Copilot (Casual Male)",
        "voice": "en-US-BrianMultilingualNeural",
        "provider": "edge_tts",
        "is_ssml": False,
        "volume": "+40%",
        "lang": "en-US",
        "description": "Friendly, approachable male voice (100% Free)",
    },
    "madhur_deep": {
        "name": "JARVIS Deep Bass (Madhur)",
        "voice": "hi-IN-MadhurNeural",
        "provider": "edge_tts",
        "is_ssml": True,
        "pitch": "-5%",
        "rate": "+5%",
        "volume": "+40%",
        "lang": "hi-IN",
        "description": "Crisp Indian male voice with slight bass",
    },
    "madhur_default": {
        "name": "Madhur Indian Male",
        "voice": "hi-IN-MadhurNeural",
        "provider": "edge_tts",
        "is_ssml": True,
        "pitch": "+0%",
        "rate": "+5%",
        "volume": "+40%",
        "lang": "hi-IN",
        "description": "Fast natural Indian male voice",
    },
    "ava_copilot": {
        "name": "Ava Copilot (Realistic Female)",
        "voice": "en-US-AvaMultilingualNeural",
        "provider": "edge_tts",
        "is_ssml": False,
        "volume": "+40%",
        "lang": "en-US",
        "description": "Expressive, sweet natural female voice (100% Free)",
    },
    "swara_natural": {
        "name": "Swara Indian Female",
        "voice": "hi-IN-SwaraNeural",
        "provider": "edge_tts",
        "is_ssml": False,
        "volume": "+40%",
        "lang": "hi-IN",
        "description": "Soft clear Indian female voice",
    },
}

DEFAULT_VOICE = "andrew_copilot"


def get_current_voice_id() -> str:
    """Retrieve the currently active voice profile id from config."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                vid = data.get("active_voice", DEFAULT_VOICE)
                if vid in VOICE_PROFILES:
                    return vid
        except Exception as e:
            logger.warning(f"Error reading voice config: {e}")
    return DEFAULT_VOICE


def set_current_voice_id(voice_id: str) -> bool:
    """Persist the active voice profile selection."""
    if voice_id not in VOICE_PROFILES:
        return False
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"active_voice": voice_id}, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving voice config: {e}")
        return False


def get_all_voice_options() -> Dict[str, dict]:
    """Return dictionary of all available voice options with active flag."""
    active = get_current_voice_id()
    res = {}
    for vid, meta in VOICE_PROFILES.items():
        res[vid] = {**meta, "is_active": (vid == active)}
    return res


def get_available_voices() -> Dict[str, dict]:
    """Alias for get_all_voice_options."""
    return get_all_voice_options()


def get_voice_profile(voice_id: str) -> Optional[dict]:
    """Get metadata dictionary for a specific voice profile ID."""
    return VOICE_PROFILES.get(voice_id)


async def _synthesize_edge_tts(text: str, profile: dict, output_path: str) -> bool:
    """Synthesize speech using Microsoft Edge Neural TTS with SSML tuning."""
    import edge_tts

    voice_name = profile["voice"]
    is_ssml = profile.get("is_ssml", False)
    
    if is_ssml:
        pitch = profile.get("pitch", "-14%")
        rate = profile.get("rate", "-4%")
        volume = profile.get("volume", "+50%")
        lang = profile.get("lang", "hi-IN")
        
        # Escape XML special characters
        safe_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")
        
        ssml = (
            f"<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='{lang}'>"
            f"<voice name='{voice_name}'>"
            f"<prosody pitch='{pitch}' rate='{rate}' volume='{volume}'>"
            f"{safe_text}"
            f"</prosody>"
            f"</voice>"
            f"</speak>"
        )
        comm = edge_tts.Communicate(ssml, voice_name)
    else:
        volume = profile.get("volume", "+50%")
        comm = edge_tts.Communicate(text, voice_name, volume=volume)

    await comm.save(output_path)
    return os.path.exists(output_path) and os.path.getsize(output_path) > 500


def synthesize_speech(text: str, output_path: str = "/tmp/hermes_tts.mp3", voice_id: Optional[str] = None) -> bool:
    """
    Main synthesis entrypoint.
    Normalizes text to native Devanagari phonetics and synthesizes MP3.
    """
    if not text or not text.strip():
        return False

    vid = voice_id or get_current_voice_id()
    profile = VOICE_PROFILES.get(vid, VOICE_PROFILES[DEFAULT_VOICE])

    # 1. Phonetically normalize text for native Indian pronunciation
    normalized_text = normalize_for_hindi_tts(text.strip())

    if os.path.exists(output_path):
        try:
            os.remove(output_path)
        except Exception:
            pass

    # 2. Check for Premium Sarvam Bulbul Adapter
    sarvam_key = os.getenv("SARVAM_API_KEY")
    if sarvam_key and profile.get("provider") == "sarvam":
        # Sarvam Bulbul v3 adapter
        try:
            import requests
            url = "https://api.sarvam.ai/text-to-speech"
            headers = {"api-subscription-key": sarvam_key, "Content-Type": "application/json"}
            payload = {
                "inputs": [normalized_text],
                "target_language_code": "hi-IN",
                "speaker": "meera",
                "model": "bulbul:v1",
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            if resp.status_code == 200:
                import base64
                aud_b64 = resp.json().get("audios", [None])[0]
                if aud_b64:
                    with open(output_path, "wb") as f:
                        f.write(base64.b64decode(aud_b64))
                    return True
        except Exception as e:
            logger.warning(f"Sarvam adapter fallback to Edge TTS: {e}")

    # 3. Built-in Edge Neural Engine (Default)
    try:
        success = asyncio.run(_synthesize_edge_tts(normalized_text, profile, output_path))
        if success:
            return True
    except Exception as e:
        logger.error(f"Edge TTS synthesis error: {e}")

    # 4. Emergency Offline Fallback
    try:
        safe_fallback = normalized_text.replace('"', '\\"')
        os.system(f'espeak-ng "{safe_fallback}" 2>/dev/null || spd-say "{safe_fallback}" 2>/dev/null')
        return False
    except Exception:
        return False

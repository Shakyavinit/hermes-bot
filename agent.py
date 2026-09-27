"""
Hermes Autonomous Agent Engine
Powered by Google Gemini 2.5 Flash with native function calling,
persistent SQLite memory, anti-loop controls, and live progress callbacks.
"""

import base64
import json
import logging
import time
from typing import Callable, Dict, List, Optional
import requests

from config import (
    GEMINI_API_KEYS,
    GEMINI_MODELS,
    WORKSPACE_DIR,
)
from memory import add_message, get_all_facts, get_history
from tools import GEMINI_FUNCTION_DECLARATIONS, dispatch_tool_call

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = f"""You are Hermes, an autonomous AI assistant strictly dedicated to controlling the user's physical laptop (@kissbilla2).
The user is interacting with you via Telegram.

PRIMARY EXECUTION GUIDELINES:
1. LAPTOP FIRST: When the user asks anything about system status, files, storage, battery, Wi-Fi, audio, video, camera, or running scripts, the target is ALWAYS their physical laptop. Use the dedicated tools:
   - `ghost_mode_screen_off`: Turn screen OFF (keep tasks running).
   - `screen_on`: Turn screen ON.
   - `capture_laptop_screenshot`: Desktop screenshot.
   - `capture_laptop_webcam`: Front camera photo.
   - `capture_laptop_video`: 10-second webcam video clip with audio.
   - `record_laptop_mic`: Record audio from room mic.
   - `toggle_laptop_cctv`: Enable/disable motion CCTV.
   - `trigger_laptop_alarm`: Sound loud siren.
   - `stop_laptop_alarm`: Stop siren.
   - `find_laptop_location`: Live location & IP.
   - `play_music_on_laptop`: Play song/music on speakers.
   - `stop_music_on_laptop`: Stop music.
   - `speak_on_laptop`: Text to speech on laptop.
   - `send_laptop_key`: Keystroke simulation ('enter', 'y', 'n', 'ctrl+c').
   - `open_url_on_laptop`: Open URL in laptop browser.
   - `get_laptop_battery`, `control_laptop_volume`, `lock_laptop_screen`, `get_laptop_wifi`, `get_laptop_apps`.
2. GENERAL SHELL: For any terminal command, use `execute_bash` (which automatically executes on the physical laptop when connected). Only use `execute_cloud_bash` if the user explicitly asks for the cloud server.
3. TRUTHFULNESS & GROUNDING: NEVER guess or hallucinate. Rely 100% on tool outputs. If a tool reports laptop is offline, state it honestly in 1 sentence.
4. ULTRA SHORT & DIRECT: Answer in 1 to 3 short lines in Hindi / Hinglish / English. Strictly NO long paragraphs or robotic filler.
"""


class AgentEngine:
    def __init__(self):
        self.keys = GEMINI_API_KEYS
        self.models = GEMINI_MODELS
        self.max_steps = 10

    def _call_gemini_api(self, contents: List[Dict], with_tools: bool = True) -> Optional[Dict]:
        """Execute generateContent with dual-key and multi-model automatic failover."""
        payload = {
            "contents": contents,
            "system_instruction": {
                "parts": [{"text": SYSTEM_PROMPT}]
            },
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 4096,
            },
        }
        if with_tools:
            payload["tools"] = [{"function_declarations": GEMINI_FUNCTION_DECLARATIONS}]

        for model_name in self.models:
            for key in self.keys:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
                try:
                    resp = requests.post(
                        url,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                        timeout=35,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            return candidates[0].get("content", {})
                    elif resp.status_code in (429, 404, 503):
                        logger.warning(
                            f"Model {model_name} with key returned {resp.status_code}, failing over..."
                        )
                        continue
                    else:
                        logger.error(f"Gemini API returned HTTP {resp.status_code}: {resp.text[:200]}")
                except Exception as e:
                    logger.error(f"Gemini API call failed for {model_name}: {e}")
                    continue

        return None

    def run_task(
        self,
        session_id: str,
        user_message: str,
        image_bytes: Optional[bytes] = None,
        image_mime: str = "image/jpeg",
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        Execute an autonomous ReAct loop for the user's prompt.
        Supports multimodal image input (screenshots, photos, diagrams).
        Optional progress_callback(status_text) sends live updates to Telegram.
        """
        # Save user message to memory
        add_message(session_id, "user", user_message)

        # Build context from facts & recent history
        facts = get_all_facts()
        facts_context = ""
        if facts:
            facts_context = "User Preferences / Known Facts:\n" + "\n".join(
                [f"- {k}: {v}" for k, v in facts.items()]
            ) + "\n\n"

        # Prepare initial Gemini contents
        contents = []

        # Include prior conversation history
        history = get_history(session_id, limit=6)
        # Exclude the message we just added
        for h in history[:-1]:
            role = "user" if h["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": h["content"]}]})

        # Append current user prompt + optional image
        user_parts = [{"text": f"{facts_context}{user_message}"}]
        if image_bytes:
            b64_img = base64.b64encode(image_bytes).decode("utf-8")
            user_parts.append({
                "inline_data": {
                    "mime_type": image_mime,
                    "data": b64_img
                }
            })

        contents.append({"role": "user", "parts": user_parts})

        step_count = 0
        executed_tools_history = []

        while step_count < self.max_steps:
            step_count += 1

            if progress_callback and step_count > 1:
                progress_callback(f"Thinking... (Step {step_count}/{self.max_steps})")

            model_content = self._call_gemini_api(contents, with_tools=True)

            if not model_content:
                return "⚠️ Error: Unable to contact Gemini API backend. Please verify your connection."

            parts = model_content.get("parts", [])

            # Check if any tool call is requested
            tool_calls = [p.get("functionCall") for p in parts if "functionCall" in p]

            if not tool_calls:
                # Text answer ready
                text_parts = [p.get("text", "") for p in parts if "text" in p]
                final_answer = "\n".join(text_parts).strip()
                if not final_answer:
                    final_answer = "✅ Task completed."
                add_message(session_id, "assistant", final_answer)
                return final_answer

            # Add model's tool call turn to contents
            contents.append(model_content)

            # Execute tool calls
            for tcall in tool_calls:
                func_name = tcall.get("name")
                args = tcall.get("args", {})

                # Prevent repetitive execution loops
                call_sig = (func_name, json.dumps(args, sort_keys=True))
                if executed_tools_history.count(call_sig) >= 2:
                    tool_output = f"Warning: Tool '{func_name}' was repeatedly called with identical parameters. Halting repeat."
                else:
                    executed_tools_history.append(call_sig)

                    # Notify user of tool action
                    if progress_callback:
                        desc = func_name
                        if func_name == "execute_bash":
                            cmd = args.get("command", "")
                            desc = f"Running command: `{cmd[:60]}`"
                        elif func_name in ("read_file", "write_file"):
                            desc = f"{func_name}: `{args.get('filepath', '')}`"
                        elif func_name == "fetch_url":
                            desc = f"Fetching URL: `{args.get('url', '')[:60]}`"
                        progress_callback(desc)

                    # Execute the tool
                    tool_output = dispatch_tool_call(func_name, args)

                # Feed tool observation back to model as user turn with functionResponse
                contents.append(
                    {
                        "role": "user",
                        "parts": [
                            {
                                "functionResponse": {
                                    "name": func_name,
                                    "response": {"output": tool_output},
                                }
                            }
                        ],
                    }
                )

        # Loop limit reached
        limit_msg = "⚠️ Reached maximum autonomous execution steps (10 steps). Task paused."
        add_message(session_id, "assistant", limit_msg)
        return limit_msg

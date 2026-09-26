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

SYSTEM_PROMPT = f"""You are Hermes, an autonomous AI engineer and personal command-line assistant running locally on the user's Linux server.
Your home workspace directory is: {WORKSPACE_DIR}

CAPABILITIES & DIRECTIVES:
1. You have direct access to tools: execute_bash, read_file, write_file, list_directory, system_status, and fetch_url.
2. Proactively use tools to complete tasks:
   - If asked to create, edit, or run code or scripts, do so directly with tools.
   - If asked to inspect or monitor the machine/files/network, run the commands directly.
3. LANGUAGE: Always respond naturally in the language the user speaks (Hindi, Hinglish, or English).
4. INTEGRITY: Rely strictly on verified tool outputs. Never invent or hallucinate command outcomes.
5. ULTRA SHORT & CRISP: Keep all responses extremely short, concise, and direct (maximum 2-3 lines). Strictly NO essays, long intros, or unnecessary filler words unless the user explicitly asks for detailed explanations or code.
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

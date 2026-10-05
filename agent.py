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
    GROQ_API_KEY,
    GROQ_MODEL,
    GROQ_MODELS,
    OPENROUTER_API_KEY,
    OPENROUTER_MODELS,
    HUGGINGFACE_API_KEY,
    HUGGINGFACE_MODELS,
    BLUESMINDS_API_KEY,
    BLUESMINDS_MODELS,
    WORKSPACE_DIR,
)
from memory import (
    add_message,
    get_all_facts,
    get_history,
    get_incident_solutions,
    save_incident,
)
from tools import GEMINI_FUNCTION_DECLARATIONS, dispatch_tool_call

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = f"""You are Hermes, a personal AI companion and autonomous assistant dedicated to your Malik / Billa (@kissbilla2 / @Billahackerking).
The user is interacting with you via Telegram and physical laptop voice/screen.

👑 USER ADDRESSING & IDENTITY RULE (CRITICAL):
- NEVER EVER call the user by any real name (like "Vinit", "Shakya", etc.). Any real name is STRICTLY FORBIDDEN!
- ALWAYS address the user as "Malik", "Billa", or "Boss" (e.g. "Haan Malik", "Theek hai Malik", "Boss").
- Never claim to be a biological human being or pretend to have capabilities you lack.

⚡ STRICT BREVITY & ULTRA-SHORT REPLIES (HIGHEST PRIORITY):
- Malik ko lambe bhashan, lambi explanations ya faltu baatein BILKUL PASAND NAHI HAIN!
- HAMESHA ULTRA-SHORT, CRISP AUR DIRECT BAAT KARNI HAI (Max 1 to 2 short punchy lines).
- Seedha kaam ki baat bolo. Koi faltu preamble ("Maine aapka kaam kar diya...", "Aapka swagat hai..."), unnecessary context ya lambi summary mat do.
- Default to easy, natural Hindi/Hinglish. Keep technical terms in English when clearer.
- Be calm, attentive, and direct. No fake laughter, no theatrical fillers.
- RESPONSE LENGTH:
  * Normal conversational turns: STRICTLY 1 to 2 SHORT SENTENCES (Max 15-20 words total).
  * Task execution: Sirf direct result bolo (e.g. "Chrome open kar diya, Malik.", "Volume 80% par set hai.", "Gaana chala diya, Malik.").
  * Put code, tables, and long details on screen in markdown only. Never dictate them.
  * Agar Malik ko detail chahiye hogi, wo khud "detail me batao" bolenge. Tab tak hamesha ultra-short raho!
- Never report a tool operation as completed until the tool result actually succeeds.
- When laptop is offline: state it in 1 short sentence: "Laptop offline hai, Malik."


PRIMARY EXECUTION GUIDELINES:
1. SEEING & SCREEN VISION (CRITICAL):
   - When the user asks to see the screen ("dekho", "kya chal raha hai", "screen par kya hai", "screen dekho", "what is on screen", "screen inspect karo", "chizein dekho", "dekh nahi paa raha hai"):
     YOU MUST CALL `inspect_screen_vision` IMMEDIATELY! It captures the live laptop screen and analyzes it with Gemini Multimodal Vision.
   - When the user asks to click an icon, button, search bar, or link on screen ("click karo", "button dabao", "search bar pe click karo"):
     CALL `screen_vision_interact` with the target element description!
   - When the user asks to solve a slider, CAPTCHA, or drag a puzzle on screen ("slider kheecho", "captcha solve karo", "puzzle slide karo", "slider drag karo", "puzzle fit karo", "recaptcha solve karo", "turnstile solve karo", "verification clear karo"):
     * For web CAPTCHAs (reCAPTCHA v2/v3, Cloudflare Turnstile, hCaptcha): CALL `solve_web_captcha`! It automatically extracts the sitekey from the active browser DOM, solves the challenge, injects the response token, and triggers form verification callbacks.
     * For slider puzzles or visual drag challenges: CALL `solve_slider_captcha`! It uses AI Vision to locate the slider button and target puzzle gap, and drags it with human-like Bézier physics and micro-jitter!
2. HUMAN GUI & APP LAUNCHING:
   - When the user asks to open an app (e.g. Chrome, Telegram, VS Code, Terminal, Settings, Calculator, YouTube):
     CALL `human_open_app` to open it on screen like a human using Super key and typing.
   - For mouse movements & clicks: use `human_mouse_click`, `human_mouse_move`, `human_mouse_drag`, `human_mouse_scroll`.
   - For typing: use `human_type_text`.
   - Dedicated laptop controls: `ghost_mode_screen_off`, `screen_on`, `capture_laptop_screenshot`, `capture_laptop_webcam`, `capture_laptop_video`, `record_laptop_mic`, `toggle_laptop_cctv`, `trigger_laptop_alarm`, `stop_laptop_alarm`, `find_laptop_location`, `play_music_on_laptop`, `stop_music_on_laptop`, `speak_on_laptop`, `send_laptop_key`, `open_url_on_laptop`.
3. GENERAL SHELL: For terminal commands, use `execute_bash` (which automatically executes on the physical laptop when connected). Only use `execute_cloud_bash` if the user explicitly asks for cloud server.
4. LIVE APIS & REAL-TIME DATA: For crypto rates, live weather, IP info, Wikipedia, or dictionary, use `query_public_api`. For external URLs or REST APIs, use `call_api` or `fetch_url`.
5. SELF-HEALING & ERROR RESOLUTION:
   - When a command or tool returns an error, DO NOT just stop and dump the error to the user.
   - Analyze the root cause, inspect any provided Diagnostic Memory hints, and autonomously attempt a corrected alternative command or solution.
6. TRUTHFULNESS & GROUNDING: NEVER guess or hallucinate. Rely 100% on tool outputs. If a tool reports laptop is offline, state it honestly and casually in 1 sentence.
"""


class AgentEngine:
    def __init__(self):
        self.keys = GEMINI_API_KEYS
        self.models = GEMINI_MODELS
        self.groq_models = GROQ_MODELS
        self.bluesminds_models = BLUESMINDS_MODELS
        self.huggingface_models = HUGGINGFACE_MODELS
        self.openrouter_models = OPENROUTER_MODELS
        self.max_steps = None  # None = Unlimited steps: runs continuously until task is fully completed

    def _call_gemini_api(self, contents: List[Dict], with_tools: bool = True) -> Optional[Dict]:
        """Execute generateContent with dual-key and multi-model automatic failover."""
        payload = {
            "contents": contents,
            "system_instruction": {
                "parts": [{"text": SYSTEM_PROMPT}]
            },
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 600,
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
                        timeout=12,
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

    def _call_groq_fallback(self, user_message: str) -> Optional[str]:
        """Tier-2 high-speed fallback to Groq Cloud (LPU Inference)."""
        if not GROQ_API_KEY:
            return None
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        }
        for model in self.groq_models:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                "temperature": 0.3,
                "max_tokens": 600,
            }
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=20)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "").strip()
                elif resp.status_code in (429, 404, 503):
                    logger.warning(f"Groq model {model} HTTP {resp.status_code}, trying next...")
                    continue
            except Exception as e:
                logger.warning(f"Groq fallback failed for {model}: {e}")
                continue
        return None

    def _call_openrouter_fallback(self, user_message: str) -> Optional[str]:
        """Tier-3 zero-cost fallback to OpenRouter Free tier."""
        if not OPENROUTER_API_KEY:
            return None
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/Shakyavinit/hermes-bot",
            "X-Title": "Hermes Autonomous Agent",
        }
        for model in self.openrouter_models:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                "temperature": 0.3,
                "max_tokens": 500,
            }
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=25)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "").strip()
                elif resp.status_code in (429, 404, 503):
                    logger.warning(f"OpenRouter model {model} HTTP {resp.status_code}, trying next...")
                    continue
            except Exception as e:
                logger.warning(f"OpenRouter fallback failed for {model}: {e}")
                continue
        return None

    def _call_huggingface_fallback(self, user_message: str) -> Optional[str]:
        """Tier-3 high-performance fallback via Hugging Face Serverless Router (DeepSeek-V3, Llama 3.3, Qwen)."""
        if not HUGGINGFACE_API_KEY:
            return None
        url = "https://router.huggingface.co/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {HUGGINGFACE_API_KEY}",
            "Content-Type": "application/json",
        }
        for model in self.huggingface_models:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                "temperature": 0.3,
                "max_tokens": 500,
            }
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=25)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "").strip()
                elif resp.status_code in (429, 404, 503):
                    logger.warning(f"HuggingFace model {model} HTTP {resp.status_code}, trying next...")
                    continue
            except Exception as e:
                logger.warning(f"HuggingFace fallback failed for {model}: {e}")
                continue
        return None

    def _call_bluesminds_fallback(self, user_message: str) -> Optional[str]:
        """Tier-3 high-speed fallback via Bluesminds API Gateway (Llama 3.2 Vision, DiffusionGemma)."""
        if not BLUESMINDS_API_KEY:
            return None
        url = "https://api.bluesminds.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {BLUESMINDS_API_KEY}",
            "Content-Type": "application/json",
        }
        for model in self.bluesminds_models:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                "temperature": 0.3,
                "max_tokens": 500,
            }
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=20)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "").strip()
                elif resp.status_code in (429, 404, 503):
                    logger.warning(f"Bluesminds model {model} HTTP {resp.status_code}, trying next...")
                    continue
            except Exception as e:
                logger.warning(f"Bluesminds fallback failed for {model}: {e}")
                continue
        return None

    def run_task(
        self,
        session_id: str,
        user_message: str,
        image_bytes: Optional[bytes] = None,
        image_mime: str = "image/jpeg",
        audio_bytes: Optional[bytes] = None,
        audio_mime: str = "audio/ogg",
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        Execute an autonomous ReAct loop for the user's prompt.
        Supports multimodal image input (screenshots, photos, diagrams) and voice notes.
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

        # Append current user prompt + optional image / audio
        user_parts = [{"text": f"{facts_context}{user_message}"}]
        if image_bytes:
            b64_img = base64.b64encode(image_bytes).decode("utf-8")
            user_parts.append({
                "inline_data": {
                    "mime_type": image_mime,
                    "data": b64_img
                }
            })
        if audio_bytes:
            b64_audio = base64.b64encode(audio_bytes).decode("utf-8")
            user_parts.append({
                "inline_data": {
                    "mime_type": audio_mime,
                    "data": b64_audio
                }
            })

        contents.append({"role": "user", "parts": user_parts})

        step_count = 0
        executed_tools_history = []

        # Unlimited loop: runs continuously until task is fully completed
        while self.max_steps is None or step_count < self.max_steps:
            step_count += 1

            if self.max_steps is None and step_count > 200:
                logger.warning("Safety circuit-breaker triggered after 200 continuous steps.")
                break

            if progress_callback and step_count > 1:
                step_str = f"Step {step_count}" if self.max_steps is None else f"Step {step_count}/{self.max_steps}"
                progress_callback(f"Thinking... ({step_str})")

            model_content = self._call_gemini_api(contents, with_tools=True)

            if not model_content:
                # Multi-Tier Fallback: Tier 2 Groq -> Tier 3 Bluesminds -> Tier 4 Hugging Face -> Tier 5 OpenRouter
                if progress_callback:
                    progress_callback("⚡ Gemini busy/failing, switching to Groq LPU engine...")
                groq_reply = self._call_groq_fallback(user_message)
                if groq_reply:
                    add_message(session_id, "assistant", groq_reply)
                    return f"{groq_reply}\n\n_(⚡ Handled via Groq LPU Fallback)_"

                if progress_callback:
                    progress_callback("🧠 Groq unavailable, switching to Bluesminds API Gateway...")
                bm_reply = self._call_bluesminds_fallback(user_message)
                if bm_reply:
                    add_message(session_id, "assistant", bm_reply)
                    return f"{bm_reply}\n\n_(🧠 Handled via Bluesminds Gateway)_"

                if progress_callback:
                    progress_callback("🤗 Bluesminds unavailable, switching to Hugging Face Serverless Router...")
                hf_reply = self._call_huggingface_fallback(user_message)
                if hf_reply:
                    add_message(session_id, "assistant", hf_reply)
                    return f"{hf_reply}\n\n_(🤗 Handled via Hugging Face Fallback - DeepSeek/Llama 3.3)_"

                if progress_callback:
                    progress_callback("🌐 Hugging Face unavailable, switching to OpenRouter Cloud...")
                openrouter_reply = self._call_openrouter_fallback(user_message)
                if openrouter_reply:
                    add_message(session_id, "assistant", openrouter_reply)
                    return f"{openrouter_reply}\n\n_(🌐 Handled via OpenRouter Fallback)_"

                return "⚠️ Notice: Gemini, Groq, Bluesminds, Hugging Face aur OpenRouter sabhi busy hain. Kripya thodi der baad dobara try karein."

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

            # Execute tool calls with Self-Healing Diagnostic Observation
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
                            desc = f"Running: `{cmd[:60]}`"
                        elif func_name in ("read_file", "write_file"):
                            desc = f"{func_name}: `{args.get('filepath', '')}`"
                        elif func_name == "fetch_url":
                            desc = f"Fetching URL: `{args.get('url', '')[:60]}`"
                        progress_callback(desc)

                    # Execute the tool
                    tool_output = dispatch_tool_call(func_name, args)

                    # Self-Healing Check: inspect output for errors & attach incident hints
                    if isinstance(tool_output, str):
                        lower_out = tool_output.lower()
                        has_error = any(
                            e in lower_out
                            for e in [
                                "error",
                                "exit code: 1",
                                "exit code: 127",
                                "command not found",
                                "permission denied",
                                "failed",
                                "timed out",
                            ]
                        )
                        if has_error:
                            incident_sols = get_incident_solutions(tool_output)
                            if incident_sols:
                                hint_msg = (
                                    "\n\n[🩺 HERMES SELF-HEALING DIAGNOSTIC]\n"
                                    "Verified past resolutions found for this error:\n"
                                    + "\n".join(incident_sols)
                                    + "\n\nInstruction: Diagnose the error and immediately try an alternative approach, flag, or tool."
                                )
                                tool_output += hint_msg

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

        # Loop limit reached (only reached if safety ceiling or explicit max_steps is hit)
        limit_msg = f"⚠️ Task paused after {step_count} continuous autonomous steps. Malik, agle instructions bhejein."
        add_message(session_id, "assistant", limit_msg)
        return limit_msg

"""
Hermes Autonomous Web Captcha Solver Engine
Incorporates patterns from 2captcha MCP Captcha Solver:
- Dedicated tools over prompt hacks
- Automatic sitekey extraction (reCAPTCHA v2/v3, Turnstile, hCaptcha)
- Token solving via 2Captcha API
- Direct DOM token injection & event dispatching
- grecaptcha / turnstile / hcaptcha callback triggering
- Fallback to Gemini Multimodal Vision for visual & slider captchas
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import websocket

from config import APIKEY_2CAPTCHA

logger = logging.getLogger("HermesCaptchaSolver")
CDP_HTTP = "http://localhost:9222"


@dataclass
class CaptchaChallenge:
    challenge_type: str  # 'recaptcha_v2', 'recaptcha_v3', 'turnstile', 'hcaptcha', 'slider', 'none', 'unknown'
    sitekey: Optional[str] = None
    page_url: Optional[str] = None
    action: Optional[str] = None
    input_field: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class CaptchaSolverEngine:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or APIKEY_2CAPTCHA or os.getenv("APIKEY_2CAPTCHA", "")
        self._twocaptcha_client = None

    def _get_solver(self):
        if not self._twocaptcha_client:
            if not self.api_key or self.api_key == "APIKEY_2CAPTCHA":
                raise ValueError("2Captcha API key is not configured. Set APIKEY_2CAPTCHA in .env.")
            from twocaptcha import TwoCaptcha
            self._twocaptcha_client = TwoCaptcha(self.api_key)
        return self._twocaptcha_client

    def get_cdp_tab(self) -> Tuple[Optional[str], Optional[str]]:
        """Find active browser tab via Chrome DevTools Protocol."""
        try:
            req = urllib.request.Request(f"{CDP_HTTP}/json/list")
            with urllib.request.urlopen(req, timeout=3) as resp:
                tabs = json.loads(resp.read().decode("utf-8"))
            pages = [t for t in tabs if t.get("type") == "page"]
            if not pages:
                return None, None
            active = pages[0]
            for p in pages:
                if "http" in p.get("url", "") and "newtab" not in p.get("url", ""):
                    active = p
                    break
            return active.get("webSocketDebuggerUrl"), active.get("url")
        except Exception as e:
            logger.warning(f"Could not connect to CDP on {CDP_HTTP}: {e}")
            return None, None

    def execute_cdp_js(self, ws_url: str, js_code: str, timeout: int = 10) -> Any:
        """Execute JavaScript inside active Chromium page via CDP WebSocket."""
        ws = websocket.create_connection(ws_url, timeout=timeout)
        try:
            req = {
                "id": 101,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": js_code,
                    "returnByValue": True,
                    "awaitPromise": True,
                },
            }
            ws.send(json.dumps(req))
            start_t = time.time()
            while time.time() - start_t < timeout:
                raw = ws.recv()
                msg = json.loads(raw)
                if msg.get("id") == 101:
                    result = msg.get("result", {}).get("result", {})
                    return result.get("value")
            return None
        finally:
            ws.close()

    def detect_captcha(self, ws_url: Optional[str] = None) -> CaptchaChallenge:
        """
        Inspect current DOM to detect any active CAPTCHA challenges:
        - reCAPTCHA v2 / v3 ([data-sitekey], g-recaptcha-response)
        - Cloudflare Turnstile ([data-sitekey], cf-turnstile-response)
        - hCaptcha ([data-sitekey], h-captcha-response)
        - Slider / puzzle challenges
        """
        if not ws_url:
            ws_url, _ = self.get_cdp_tab()
        if not ws_url:
            return CaptchaChallenge(challenge_type="unknown", details={"error": "No browser CDP session found"})

        detection_js = """
        (function() {
            var url = window.location.href;

            // 1. Check hCaptcha first (specific iframe or container)
            var hcaptchaEl = document.querySelector('.h-captcha, [data-hcaptcha-widget-id], iframe[src*="hcaptcha"], [name="h-captcha-response"]');
            if (hcaptchaEl) {
                var hk = hcaptchaEl.getAttribute ? hcaptchaEl.getAttribute('data-sitekey') : null;
                if (!hk) {
                    var hContainer = document.querySelector('[data-sitekey].h-captcha, [data-hcaptcha-widget-id]');
                    if (hContainer) hk = hContainer.getAttribute('data-sitekey');
                }
                if (!hk) {
                    var hIfr = document.querySelector('iframe[src*="hcaptcha"]');
                    if (hIfr) {
                        var hm = hIfr.src.match(/[?&]sitekey=([a-zA-Z0-9_-]+)/);
                        if (hm) hk = hm[1];
                    }
                }
                return {
                    type: 'hcaptcha',
                    sitekey: hk,
                    url: url,
                    field: 'h-captcha-response'
                };
            }

            // 2. Check Cloudflare Turnstile
            var turnstileEl = document.querySelector('.cf-turnstile, iframe[src*="challenges.cloudflare.com"], [name="cf-turnstile-response"]');
            if (turnstileEl) {
                var tk = turnstileEl.getAttribute ? turnstileEl.getAttribute('data-sitekey') : null;
                if (!tk) {
                    var tContainer = document.querySelector('[data-sitekey].cf-turnstile');
                    if (tContainer) tk = tContainer.getAttribute('data-sitekey');
                }
                return {
                    type: 'turnstile',
                    sitekey: tk,
                    url: url,
                    field: 'cf-turnstile-response'
                };
            }

            // 3. Check Google reCAPTCHA
            var recaptchaIframe = document.querySelector('iframe[src*="recaptcha"]');
            var recaptchaEl = document.querySelector('.g-recaptcha, [data-sitekey]:not(.cf-turnstile):not(.h-captcha)');
            var recaptchaResp = document.getElementById('g-recaptcha-response') || document.querySelector('[name="g-recaptcha-response"]');
            if (recaptchaIframe || recaptchaEl || recaptchaResp) {
                var sitekey = null;
                if (recaptchaEl) sitekey = recaptchaEl.getAttribute('data-sitekey');
                if (!sitekey && recaptchaIframe) {
                    var m = recaptchaIframe.src.match(/[?&]k=([a-zA-Z0-9_-]+)/);
                    if (m) sitekey = m[1];
                }
                return {
                    type: 'recaptcha_v2',
                    sitekey: sitekey,
                    url: url,
                    field: 'g-recaptcha-response'
                };
            }

            // 4. Check Slider puzzle
            var slider = document.querySelector('.geetest_slider, .slide-btn, .puzzle-slider, .nc_iconfont.btn_slide');
            if (slider) {
                return {
                    type: 'slider',
                    url: url,
                    details: 'Slider puzzle challenge detected on screen'
                };
            }

            return { type: 'none', url: url };
        })()
        """
        try:
            res = self.execute_cdp_js(ws_url, detection_js)
            if not res or res.get("type") == "none":
                return CaptchaChallenge(challenge_type="none", page_url=res.get("url") if res else None)
            return CaptchaChallenge(
                challenge_type=res.get("type", "unknown"),
                sitekey=res.get("sitekey"),
                page_url=res.get("url"),
                input_field=res.get("field"),
                details=res,
            )
        except Exception as e:
            return CaptchaChallenge(challenge_type="error", details={"error": str(e)})

    def solve_recaptcha_v2(self, page_url: str, sitekey: str) -> str:
        """Call 2Captcha solver to solve reCAPTCHA v2 challenge and return token."""
        solver = self._get_solver()
        logger.info(f"Submitting reCAPTCHA v2 to 2Captcha for {page_url} (sitekey: {sitekey[:8]}...)")
        result = solver.recaptcha(sitekey=sitekey, url=page_url)
        return str(result["code"])

    def solve_turnstile(self, page_url: str, sitekey: str) -> str:
        """Call 2Captcha solver to solve Cloudflare Turnstile and return token."""
        solver = self._get_solver()
        logger.info(f"Submitting Turnstile to 2Captcha for {page_url} (sitekey: {sitekey[:8]}...)")
        result = solver.turnstile(sitekey=sitekey, url=page_url)
        return str(result["code"])

    def solve_hcaptcha(self, page_url: str, sitekey: str) -> str:
        """Call 2Captcha solver to solve hCaptcha and return token."""
        solver = self._get_solver()
        logger.info(f"Submitting hCaptcha to 2Captcha for {page_url} (sitekey: {sitekey[:8]}...)")
        result = solver.hcaptcha(sitekey=sitekey, url=page_url)
        return str(result["code"])

    def inject_token_and_submit(self, ws_url: str, token: str, challenge_type: str = "recaptcha_v2") -> bool:
        """
        Inject solved token into the page and trigger standard callback functions:
        - g-recaptcha-response / cf-turnstile-response / h-captcha-response
        - window.___grecaptcha_cfg callbacks
        - window.turnstile callbacks
        """
        inject_js = f"""
        (function() {{
            var token = {json.dumps(token)};
            var type = {json.dumps(challenge_type)};
            var injected = false;

            // 1. Inject into response field
            var fieldId = 'g-recaptcha-response';
            if (type === 'turnstile') fieldId = 'cf-turnstile-response';
            if (type === 'hcaptcha') fieldId = 'h-captcha-response';

            var fields = document.querySelectorAll('#' + fieldId + ', [name="' + fieldId + '"]');
            fields.forEach(function(f) {{
                f.value = token;
                f.innerHTML = token;
                f.dispatchEvent(new Event('input', {{ bubbles: true }}));
                f.dispatchEvent(new Event('change', {{ bubbles: true }}));
                injected = true;
            }});

            // 2. Invoke grecaptcha client callback if present
            try {{
                if (window.___grecaptcha_cfg && window.___grecaptcha_cfg.clients) {{
                    Object.values(window.___grecaptcha_cfg.clients).forEach(function(client) {{
                        Object.values(client).forEach(function(val) {{
                            if (val && typeof val.callback === 'function') {{
                                val.callback(token);
                                injected = true;
                            }}
                            if (val && typeof val.promise === 'object' && val.callback) {{
                                val.callback(token);
                            }}
                        }});
                    }});
                }}
            }} catch(e) {{}}

            // 3. Optional submit button trigger if available
            var submitBtn = document.querySelector('[data-action="demo_action"], button[type="submit"], input[type="submit"]');
            if (submitBtn) {{
                setTimeout(function() {{ submitBtn.click(); }}, 400);
            }}

            return injected;
        }})()
        """
        res = self.execute_cdp_js(ws_url, inject_js)
        return bool(res)

    def solve_active_captcha(self) -> str:
        """
        Master method: inspect active browser tab, detect captcha, solve it via 2Captcha or Vision,
        and inject response token.
        """
        ws_url, page_url = self.get_cdp_tab()
        if not ws_url:
            return "❌ Browser CDP connection not found on port 9222. Make sure Chromium is running."

        challenge = self.detect_captcha(ws_url)
        logger.info(f"Detected challenge: {challenge.challenge_type} on {challenge.page_url}")

        if challenge.challenge_type == "none":
            return "ℹ️ Screen/page par koi active reCAPTCHA, Turnstile ya hCaptcha challenge nahi mila."

        if challenge.challenge_type == "slider":
            from human_gui import solve_slider_captcha
            res = solve_slider_captcha()
            return f"🧩 Slider challenge detect hua. Vision solver execution:\n{res}"

        if not challenge.sitekey:
            return f"⚠️ {challenge.challenge_type.upper()} challenge detect hua lekin sitekey extract nahi ho paya."

        if not self.api_key or self.api_key == "APIKEY_2CAPTCHA":
            return (
                f"🔑 {challenge.challenge_type.upper()} detect hua (sitekey: `{challenge.sitekey}`).\n"
                f"Lekin `APIKEY_2CAPTCHA` configured nahi hai. 2Captcha API key add karo (.env me) taaki automatic solve ho sake."
            )

        try:
            if challenge.challenge_type in ("recaptcha_v2", "recaptcha_v3"):
                token = self.solve_recaptcha_v2(challenge.page_url or page_url, challenge.sitekey)
            elif challenge.challenge_type == "turnstile":
                token = self.solve_turnstile(challenge.page_url or page_url, challenge.sitekey)
            elif challenge.challenge_type == "hcaptcha":
                token = self.solve_hcaptcha(challenge.page_url or page_url, challenge.sitekey)
            else:
                return f"⚠️ Unsupported challenge type: {challenge.challenge_type}"

            injected = self.inject_token_and_submit(ws_url, token, challenge.challenge_type)
            return (
                f"✅ {challenge.challenge_type.upper()} successfully solved!\n"
                f"• Sitekey: `{challenge.sitekey}`\n"
                f"• Token injected: {'Yes' if injected else 'Manual injection needed'}\n"
                f"• Token snippet: `{token[:25]}...`"
            )
        except Exception as e:
            return f"❌ CAPTCHA solving failed: {str(e)}"


# Singleton instance
solver_engine = CaptchaSolverEngine()


def solve_web_captcha() -> str:
    """Public tool function to solve CAPTCHAs on the active browser tab."""
    return solver_engine.solve_active_captcha()


if __name__ == "__main__":
    print("Testing CaptchaSolverEngine detection...")
    print(solver_engine.solve_active_captcha())

"""
Hermes Local Laptop Runner Node
Runs in background on user's physical laptop.
Allows the 24/7 Render Cloud Telegram Bot to execute bash commands, check files,
and control this laptop remotely.
"""

import json
import logging
import os
import subprocess
import sys
import time
import requests

logging.basicConfig(
    format="%(asctime)s - [LaptopNode] - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("LaptopNode")

CLOUD_URL = os.getenv("HERMES_CLOUD_URL", "https://hermes-bot-kqv8.onrender.com").rstrip("/")
SECRET = os.getenv("LAPTOP_BRIDGE_SECRET", "hermes_secret_8616271645")
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))


def start_node() -> None:
    logger.info("=" * 60)
    logger.info("💻 Hermes Laptop Node Started")
    logger.info(f"Target Cloud Gateway: {CLOUD_URL}")
    logger.info(f"Local Workspace: {WORKSPACE_DIR}")
    logger.info("Waiting for tasks from Telegram...")
    logger.info("=" * 60)

    consecutive_errors = 0

    while True:
        try:
            poll_url = f"{CLOUD_URL}/api/laptop/poll"
            resp = requests.get(
                poll_url,
                params={"secret": SECRET},
                timeout=25,
            )

            if resp.status_code == 200:
                consecutive_errors = 0
                data = resp.json()
                task = data.get("task")

                if task:
                    task_id = task.get("task_id")
                    cmd = task.get("command", "").strip()
                    logger.info(f"⚡ Received task [{task_id}]: {cmd[:80]}")

                    try:
                        proc = subprocess.run(
                            cmd,
                            shell=True,
                            cwd=WORKSPACE_DIR,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            timeout=60,
                        )
                        output_parts = []
                        if proc.stdout.strip():
                            output_parts.append(proc.stdout.strip())
                        if proc.stderr.strip():
                            output_parts.append(f"STDERR:\n{proc.stderr.strip()}")
                        out_str = "\n".join(output_parts)
                        if not out_str:
                            out_str = "(Command finished with empty output)"
                    except subprocess.TimeoutExpired:
                        out_str = "Error: Local command execution timed out (60s)."
                    except Exception as e:
                        out_str = f"Error executing local command: {e}"

                    # Send result back to cloud
                    res_url = f"{CLOUD_URL}/api/laptop/result"
                    requests.post(
                        res_url,
                        json={"secret": SECRET, "task_id": task_id, "output": out_str},
                        timeout=15,
                    )
                    logger.info(f"✅ Completed task [{task_id}]")

            else:
                consecutive_errors += 1
                time.sleep(2)

        except requests.exceptions.RequestException as e:
            consecutive_errors += 1
            delay = min(consecutive_errors * 2, 10)
            time.sleep(delay)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            time.sleep(2)


if __name__ == "__main__":
    start_node()

"""
Hermes Bridge Module
Enables bidirectional communication between 24/7 Render Cloud Bot
and the user's physical local laptop.
"""

import queue
import time
from typing import Dict, Optional

LAPTOP_SECRET = "hermes_secret_8616271645"

# In-memory queues & state (runs in Render web process)
_task_queue: "queue.Queue[Dict]" = queue.Queue()
_task_results: Dict[str, str] = {}
_last_heartbeat = [0.0]


def is_laptop_online() -> bool:
    """Return True if laptop sent a ping in the last 15 seconds."""
    return (time.time() - _last_heartbeat[0]) < 15.0


def record_heartbeat() -> None:
    """Update last seen timestamp for the physical laptop."""
    _last_heartbeat[0] = time.time()


def get_pending_task() -> Optional[Dict]:
    """Retrieve the next queued command for the laptop (non-blocking)."""
    try:
        return _task_queue.get_nowait()
    except queue.Empty:
        return None


def store_task_result(task_id: str, output: str) -> None:
    """Store output received from the laptop."""
    _task_results[task_id] = output


def dispatch_to_laptop(command: str, timeout: int = 40) -> str:
    """
    Queue a command for the physical laptop and wait synchronously for the result.
    """
    if not is_laptop_online():
        return "⚠️ Laptop is currently OFFLINE (laptop band hai ya laptop_node disconnect hai)."

    task_id = f"task_{int(time.time() * 1000)}"
    _task_queue.put({"task_id": task_id, "command": command})

    start_time = time.time()
    while (time.time() - start_time) < timeout:
        if task_id in _task_results:
            return _task_results.pop(task_id)
        time.sleep(0.5)

    return f"⚠️ Timeout: Laptop did not return response within {timeout} seconds."

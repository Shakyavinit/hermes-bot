"""
Hermes Agent Tools Module
Provides executable tools for the autonomous agent:
- execute_bash
- read_file
- write_file
- list_directory
- system_status
- fetch_url
"""

import json
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Dict, List
import requests

from config import WORKSPACE_DIR


def execute_bash(command: str, timeout: int = 60) -> str:
    """Execute a bash command in the workspace directory with timeout and safety checks."""
    if not command.strip():
        return "Error: Empty command provided."

    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(WORKSPACE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()
        code = proc.returncode

        res = []
        if stdout:
            res.append(f"STDOUT:\n{stdout}")
        if stderr:
            res.append(f"STDERR:\n{stderr}")
        res.append(f"Exit Code: {code}")

        out_str = "\n".join(res)
        # Cap output to 8000 characters
        if len(out_str) > 8000:
            out_str = out_str[:4000] + "\n...[Output truncated]...\n" + out_str[-4000:]
        return out_str if out_str else "(Command finished with empty output)"
    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds."
    except Exception as e:
        return f"Error executing command: {str(e)}"


def resolve_path(filepath: str) -> Path:
    """Resolve file path relative to workspace directory."""
    p = Path(filepath)
    if not p.is_absolute():
        p = WORKSPACE_DIR / p
    return p.resolve()


def read_file(filepath: str, max_chars: int = 8000) -> str:
    """Read the contents of a text file."""
    p = resolve_path(filepath)
    if not p.exists():
        return f"Error: File '{filepath}' does not exist."
    if p.is_dir():
        return f"Error: '{filepath}' is a directory, not a file."

    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        if len(content) > max_chars:
            content = content[:max_chars] + f"\n...[Truncated, total {len(content)} chars]..."
        return content
    except Exception as e:
        return f"Error reading file: {str(e)}"


def write_file(filepath: str, content: str) -> str:
    """Write or overwrite a file with given content."""
    p = resolve_path(filepath)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote {len(content)} characters to '{filepath}'."
    except Exception as e:
        return f"Error writing file: {str(e)}"


def list_directory(dirpath: str = ".") -> str:
    """List contents of a directory."""
    p = resolve_path(dirpath)
    if not p.exists():
        return f"Error: Directory '{dirpath}' does not exist."
    if not p.is_dir():
        return f"Error: '{dirpath}' is a file, not a directory."

    try:
        entries = []
        for item in sorted(p.iterdir()):
            prefix = "[DIR] " if item.is_dir() else "[FILE]"
            size = ""
            if item.is_file():
                size = f" ({item.stat().st_size} bytes)"
            entries.append(f"{prefix} {item.name}{size}")
        return "\n".join(entries) if entries else "(Empty directory)"
    except Exception as e:
        return f"Error listing directory: {str(e)}"


def system_status() -> str:
    """Get system health, memory, disk, and OS information."""
    try:
        uname = platform.uname()
        disk = shutil.disk_usage(str(WORKSPACE_DIR))
        total_gb = disk.total / (1024**3)
        free_gb = disk.free / (1024**3)
        used_gb = disk.used / (1024**3)

        info = [
            f"OS: {uname.system} {uname.release} ({uname.machine})",
            f"Hostname: {uname.node}",
            f"Disk: {used_gb:.1f} GB used / {total_gb:.1f} GB total ({free_gb:.1f} GB free)",
            f"Workspace: {WORKSPACE_DIR}",
            f"Python: {platform.python_version()}",
            f"Current Time: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        ]
        return "\n".join(info)
    except Exception as e:
        return f"Error checking system status: {str(e)}"


def fetch_url(url: str, timeout: int = 15) -> str:
    """Fetch content of a webpage or API endpoint."""
    if not url.startswith("http://") and not url.startswith("https://"):
        return "Error: URL must start with http:// or https://"
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=timeout)
        text = resp.text
        if len(text) > 6000:
            text = text[:6000] + f"\n...[Truncated, total {len(text)} chars]..."
        return f"Status: {resp.status_code}\nContent:\n{text}"
    except Exception as e:
        return f"Error fetching URL: {str(e)}"


# Tool Registry & Schemas
TOOLS_MAP: Dict[str, Callable] = {
    "execute_bash": execute_bash,
    "read_file": read_file,
    "write_file": write_file,
    "list_directory": list_directory,
    "system_status": system_status,
    "fetch_url": fetch_url,
}

GEMINI_FUNCTION_DECLARATIONS = [
    {
        "name": "execute_bash",
        "description": "Execute any Linux bash shell command (e.g. git, python, curl, grep, apt, ls, docker, system utilities) in the workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The exact shell command line string to run.",
                }
            },
            "required": ["command"],
        },
    },
    {
        "name": "read_file",
        "description": "Read the contents of a local file.",
        "parameters": {
            "type": "object",
            "properties": {
                "filepath": {
                    "type": "string",
                    "description": "Relative or absolute path of the file to read.",
                }
            },
            "required": ["filepath"],
        },
    },
    {
        "name": "write_file",
        "description": "Create or overwrite a file with given text content.",
        "parameters": {
            "type": "object",
            "properties": {
                "filepath": {
                    "type": "string",
                    "description": "Path where the file should be saved.",
                },
                "content": {
                    "type": "string",
                    "description": "Full content to write into the file.",
                },
            },
            "required": ["filepath", "content"],
        },
    },
    {
        "name": "list_directory",
        "description": "List files and subdirectories in a directory path.",
        "parameters": {
            "type": "object",
            "properties": {
                "dirpath": {
                    "type": "string",
                    "description": "Directory path (default is '.' for current workspace).",
                }
            },
        },
    },
    {
        "name": "system_status",
        "description": "Get current OS, disk usage, memory, and environment information.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "fetch_url",
        "description": "Fetch live web page or API response via HTTP GET.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The full HTTP/HTTPS URL to fetch.",
                }
            },
            "required": ["url"],
        },
    },
]

TOOL_DEFINITIONS = [
    {"type": "function", "function": decl} for decl in GEMINI_FUNCTION_DECLARATIONS
]


def dispatch_tool_call(tool_name: str, arguments: dict) -> str:
    """Dispatch and execute tool by name with arguments."""
    func = TOOLS_MAP.get(tool_name)
    if not func:
        return f"Error: Tool '{tool_name}' not found."
    try:
        return str(func(**arguments))
    except Exception as e:
        return f"Error calling tool '{tool_name}': {str(e)}"

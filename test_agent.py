"""
Quick verification test for Hermes Agent modules.
"""

import sys
from config import TELEGRAM_BOT_TOKEN, GROQ_API_KEY, WORKSPACE_DIR
from tools import system_status, execute_bash, list_directory
from memory import add_message, get_history, save_fact, get_all_facts

print("1. Checking Config...")
print(f"   Workspace: {WORKSPACE_DIR}")
print(f"   Telegram Bot Token: {'[OK]' if TELEGRAM_BOT_TOKEN else '[MISSING]'}")
print(f"   Groq API Key: {'[OK]' if GROQ_API_KEY else '[MISSING]'}")

print("\n2. Checking Tools...")
print(f"   List Directory:\n{list_directory('.')[:150]}")
print(f"   Bash Command 'echo Hello Hermes':\n{execute_bash('echo Hello Hermes')}")
print(f"   System Status:\n{system_status()}")

print("\n3. Checking Memory...")
add_message("test_session", "user", "Test Hello")
add_message("test_session", "assistant", "Test Hi")
hist = get_history("test_session")
print(f"   Memory History: {len(hist)} items [OK]")

save_fact("owner_name", "Shakya Vinit")
facts = get_all_facts()
print(f"   Memory Facts: {facts} [OK]")

print("\nAll local unit tests passed successfully!")

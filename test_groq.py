import os
import sys
from config.settings import settings
from core.llm import get_llm
from core.intent import parse_intent

print(f"Provider: {settings.llm_provider}")
print(f"Model: {settings.llm_model}")
print(f"API Key set: {bool(settings.llm_api_key)}")

print("Testing parse_intent directly...")
try:
    intent = parse_intent("Install nginx", "Put it on web-1 in prod", ["ansible"])
    print("Parsed Intent:", intent)
except Exception as e:
    import traceback
    traceback.print_exc()


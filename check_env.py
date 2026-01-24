import os
from dotenv import load_dotenv

# Load .env like the app does
_project_root = os.path.dirname(os.path.abspath('main.py'))
load_dotenv(os.path.join(_project_root, '.env'), override=True)

print('=== Environment Variables ===')
key = os.environ.get('OPENAI_API_KEY', 'NOT SET')
# Nur Länge prüfen, keine Substrings
print(f'API Key configured: {len(key) > 0 if isinstance(key, str) else False} (length: {len(key) if isinstance(key, str) else 0})')
print(f'OPENAI_API_BASE: {os.environ.get("OPENAI_API_BASE", "NOT SET")}')
print(f'OPENAI_BASE_URL: {os.environ.get("OPENAI_BASE_URL", "NOT SET")}')

print()
print('=== Testing CrewAI ===')
from crewai import Agent
print('CrewAI imported successfully')

# Check how CrewAI reads API settings
print()
print('=== CrewAI LLM Provider Check ===')
try:
    from crewai.llms.providers.openai import OpenAI as CrewAIOpenAI
    print('CrewAI OpenAI provider imported')
except Exception as e:
    print(f'Error: {e}')

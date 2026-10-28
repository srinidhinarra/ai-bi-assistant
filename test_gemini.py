import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise SystemExit("GEMINI_API_KEY not found. Check your .env file.")

# timeout is in milliseconds, so it fails after 20s instead of hanging
client = genai.Client(
    api_key=api_key,
    http_options=types.HttpOptions(timeout=20000),
)

# Step 1: see which models your key can actually use
print("Available models:")
available = []
try:
    for m in client.models.list():
        name = m.name.replace("models/", "")
        if "flash" in name:
            available.append(name)
            print("  -", name)
except Exception as error:
    raise
from dotenv import load_dotenv
load_dotenv()
import os, requests

r = requests.get(
    "https://generativelanguage.googleapis.com/v1beta/models",
    headers={"x-goog-api-key": os.environ["GROQ_API_KEY"]},
)
print(r.status_code)
models = r.json().get("models", [])
print([m["name"] for m in models if "generateContent" in m.get("supportedGenerationMethods", [])])
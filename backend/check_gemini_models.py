
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("No GEMINI_API_KEY found.")
    exit()

genai.configure(api_key=api_key)

print("Listing available models...")
with open("models.txt", "w") as f:
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                f.write(f"{m.name}\n")
    except Exception as e:
        f.write(f"Error: {e}\n")
print("Done writing to models.txt")

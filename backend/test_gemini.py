import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
    try:
        with open("available_models.txt", "w") as f:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    f.write(m.name + "\n")
        print("Models written to available_models.txt")
    except Exception as e:
        print(f"Error: {e}")
else:
    print("No GEMINI_API_KEY")

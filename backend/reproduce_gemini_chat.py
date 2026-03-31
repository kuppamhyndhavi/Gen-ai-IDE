import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=api_key)

def test_chat():
    try:
        model = genai.GenerativeModel('gemini-flash-latest')
        
        prompt_parts = ["Hello"]
        
        print("Sending prompt to gemini-flash-latest...")
        
        response = model.generate_content(prompt_parts)
        print("Success!")
        print(response.text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_chat()

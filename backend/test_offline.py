
import requests
import json
import time

system_prompt = (
    "You are a helpful AI assistant. "
    "Answer general questions normally and concisely. "
    "Only generate code if the user explicitly asks for it or if it is required to answer the request. "
    "If you do generate code (e.g. for a website or app), you MUST generate three separate markdown blocks: "
    "1. `html` for index.html "
    "2. `css` for style.css "
    "3. `javascript` for script.js "
    "IMPORTANT: Use ONLY standard HTML, CSS, and JavaScript. "
    "Do NOT use external frameworks (React, Vue, etc.) or Python for frontend. "
    "Ensure the code is full, working, and complete. "
    "Never refuse a valid coding request."
)

user_prompt = "Create a simple calculator app"

print("Sending request to Ollama...")
start = time.time()

try:
    response = requests.post(
        "http://localhost:11434/api/chat",
        json={
            "model": "mistral:latest",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "stream": False
        }
    )
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print("Response:")
        print(response.json()['message']['content'])
    else:
        print(response.text)

except Exception as e:
    print(f"Error: {e}")

print(f"Time: {time.time() - start:.2f}s")

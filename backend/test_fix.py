import requests
import uuid

url = "http://localhost:8000/api/chat/message"
session_id = str(uuid.uuid4())

payload = {
    "session_id": session_id,
    "task_type": "chat",
    "messages": [
        {"role": "user", "content": "Write a python function to add two numbers."}
    ],
    "code_context": None
}

try:
    print(f"Sending request to {url}...")
    # Increased timeout for local models
    response = requests.post(url, json=payload, timeout=120)
    
    if response.status_code == 200:
        print("Success!")
        print("Response:", response.json())
    else:
        print(f"Failed with status {response.status_code}")
        print("Response:", response.text)

except Exception as e:
    print(f"Connection failed: {e}")

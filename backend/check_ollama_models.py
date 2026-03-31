
import requests

try:
    response = requests.get("http://localhost:11434/api/tags")
    if response.status_code == 200:
        models = [m['name'] for m in response.json().get('models', [])]
        print("Models found:")
        for m in models:
            print(f"- {m}")
    else:
        print(f"Error: {response.status_code}")
except Exception as e:
    print(f"Error: {e}")

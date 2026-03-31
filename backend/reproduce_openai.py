import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.environ.get("OPENAI_API_KEY")
print(f"API Key present: {bool(api_key)}")

client = OpenAI(api_key=api_key)

try:
    print("Testing gpt-4.1-mini...")
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=10
    )
    print("Success!")
    print(response.choices[0].message.content)
except Exception as e:
    print(f"Error executing gpt-4.1-mini: {e}")

try:
    print("\nTesting gpt-4o-mini...")
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=10
    )
    print("Success!")
    print(response.choices[0].message.content)
except Exception as e:
    print(f"Error executing gpt-4o-mini: {e}")

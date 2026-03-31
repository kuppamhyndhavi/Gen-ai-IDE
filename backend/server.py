from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import subprocess
import tempfile
import json
from git import Repo
import shutil
import openai
from contextlib import asynccontextmanager
from openai import OpenAI
############################ollama
import google.generativeai as genai
import requests

from fastapi.exceptions import RequestValidationError
from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse
import json




ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env', override=True)

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    client.close()

app = FastAPI(lifespan=lifespan)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print("❌ VALIDATION ERROR:")
    print(exc.errors())

    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "body": str(exc.body)
        }
    )

api_router = APIRouter(prefix="/api")

# Pydantic Models
class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    role: str
    content: str
    code_context: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ChatRequest(BaseModel):
    session_id: str
    task_type: str = "chat"
    messages: List[dict]
    code_context: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str

class CodeExecuteRequest(BaseModel):
    code: str
    language: str = "python"

class CodeExecuteResponse(BaseModel):
    output: str
    error: Optional[str] = None
    execution_time: float

class GitHubRequest(BaseModel):
    action: str
    repo_path: Optional[str] = None
    repo_url: Optional[str] = None
    commit_message: Optional[str] = None
    token: Optional[str] = None
    code: Optional[str] = None
    language: Optional[str] = None
    files: Optional[List[dict]] = None  # List of {name, content}

class GitHubResponse(BaseModel):
    success: bool
    message: str

class CodeProject(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    code: str
    language: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CodeProjectCreate(BaseModel):
    name: str
    code: str
    language: str

# LLM Helpers
# ================= MEMORY HELPERS =================

async def get_recent_chat_history(session_id: str, limit: int = 8):
    """
    Fetch last N messages (user + assistant), text-only.
    Oldest → newest.
    """
    messages = await db.chat_messages.find(
        {"session_id": session_id},
        {"_id": 0, "role": 1, "content": 1}
    ).sort("timestamp", -1).to_list(limit)

    # reverse to chronological order
    messages.reverse()
    return messages

# ================= LLM SYSTEM PROMPTS =================
def get_system_message(task_type: str) -> str:
    messages = {
        "generate": (
            "You are an expert software engineer and coding assistant. "
            "Write correct, production-quality code. "
            "Think step by step internally, but only output the final answer. "
            "Follow best practices, handle edge cases, and avoid hallucinations. "
            "If something is unclear, ask for clarification."
            "If a response is long, ALWAYS complete the full code."
            "If truncated, continue until finished."
            "If you generated code earlier, continue it."
            "NEVER say you lack context."
            "NEVER refuse to generate full code."
        ),

        "debug": (
            "You are an expert debugger. "
            "Carefully analyze the given code, identify bugs, logical errors, "
            "and edge cases. Explain the issue clearly and provide a corrected version."
        ),

        "optimize": (
            "You are an expert performance engineer. "
            "Analyze the code and suggest optimizations for speed, memory usage, "
            "readability, and maintainability. Do not change behavior."
        ),

        "document": (
            "You are a technical writer and senior engineer. "
            "Generate clear docstrings, comments, and concise documentation. "
            "Explain inputs, outputs, and behavior."
        ),

    }
    return messages.get(task_type, messages["generate"])

def get_dynamic_system_prompt(task_type: str, has_code: bool) -> str:
    # Code-focused modes
    if task_type in ["debug", "optimize", "document"]:
        return get_system_message(task_type)

    # Code was explicitly provided → act as code expert
    if has_code:
        return get_system_message("generate")

    # Normal chat (default)
    # Normal chat (default)
    return (
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

# ================= OFFLINE AI HELPERS =================

def call_ollama(system_prompt: str, user_prompt: str) -> str:
    ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    
    # Auto-detect best available model if not explicitly set
    ollama_model = os.environ.get("OLLAMA_MODEL")
    if not ollama_model:
        try:
            res = requests.get(f"{ollama_url}/api/tags", timeout=2)
            if res.status_code == 200:
                models = [m['name'] for m in res.json()['models']]
                # Preference list
                for preferred in ['deepseek-coder:6.7b', 'deepseek-coder', 'mistral', 'llama3', 'llama2', 'codellama']:
                    for m in models:
                        if preferred in m:
                            ollama_model = m
                            break
                    if ollama_model: break
                
                if not ollama_model and models:
                    ollama_model = models[0] # Fallback to first available
        except Exception:
            pass

    ollama_model = ollama_model or "mistral:latest" # Final fallback

    # Simplified system prompt for smaller local models
    if "You are a helpful AI assistant" in system_prompt:
         system_prompt = (
            "You are an expert Frontend Developer and UI/UX Designer. "
            "When asked for code, generate ONLY valid HTML, CSS, and JS. "
            "Use separate markdown blocks: ```html, ```css, ```javascript. "
            "CRITICAL RULES:\n"
            "1. Make the design MODERN, BEAUTIFUL, and RESPONSIVE.\n"
            "2. Use Flexbox/Grid centering, soft shadows, rounded corners (border-radius), and gradients.\n"
            "3. Use a nice font (e.g., system-ui, Inter, or Roboto).\n"
            "4. Do NOT produce 'barebones' or ugly 1990s-style HTML.\n"
            "5. OUTPUT FORMAT: Write clean, PROPERLY INDENTED code with actual newlines. Do NOT collapse code into a single line.\n"
            "6. Keep the code complete and working."
            "7. FULL CODE ONLY: Do NOT use placeholders like '<!-- Add more buttons -->' or '// logic here'. Write every single line of code."
        )
    
    try:
        logging.info(f"Ollama using model: {ollama_model}")
        response = requests.post(
            f"{ollama_url}/api/chat",
            json={
                "model": ollama_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": (
                        f"{user_prompt}\n\n"
                        "IMPORTANT DESIGN & QUALITY REQUIREMENTS:\n"
                        "1. FULL CODE ONLY: Do NOT use placeholders like '<!-- Add more buttons -->' or '// logic here'. Write every single line of code.\n"
                        "2. MODERN UI: Use nice gradients, shadows, and rounded corners (border-radius: 12px).\n"
                        "3. FUNCTIONAL: Ensure the JavaScript actually works.\n"
                    )}
                ],
                "options": {
                    "num_predict": 4096,
                    "temperature": 0.7
                },
                "stream": False
            },
            timeout=300
        )

        if response.status_code != 200:
            raise RuntimeError(f"Ollama error: {response.status_code} - {response.text}")

        data = response.json()

        if "message" in data and "content" in data["message"]:
            return data["message"]["content"]

        if "response" in data:
            return data["response"]

        raise RuntimeError(f"Ollama invalid response format: {data}")
    
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            f"❌ Cannot connect to Ollama at {ollama_url}\n"
            f"Make sure Ollama is running: ollama serve\n"
            f"Or set OLLAMA_URL in .env to your Ollama address"
        )
    except requests.exceptions.Timeout:
        raise RuntimeError(
            f"❌ Ollama request timed out (120s).\n"
            f"Check if model '{ollama_model}' is loaded: ollama pull {ollama_model}"
        )
    except Exception as e:
        raise RuntimeError(f"❌ Ollama error: {str(e)}")

def call_ollama_stream(system_prompt: str, user_prompt: str):
    """
    Yields chunks of text from Ollama for streaming responses.
    """
    ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    ollama_model = os.environ.get("OLLAMA_MODEL", "mistral:latest")

    # Reuse the same system prompt logic if needed, or caller passes full prompt
    # For simplicity, we assume caller passes the final prompts
    
    payload = {
        "model": ollama_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "options": {
            "num_predict": 4096,
            "temperature": 0.7
        },
        "stream": True  # ENABLE STREAMING
    }

    try:
        with requests.post(f"{ollama_url}/api/chat", json=payload, stream=True, timeout=300) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    try:
                        body = json.loads(line)
                        if "message" in body and "content" in body["message"]:
                            content = body["message"]["content"]
                            yield content
                        if "done" in body and body["done"]:
                            break
                    except json.JSONDecodeError:
                        pass
    except Exception as e:
        yield f"Error: {e}"

# ================= AI CLIENT SETUP =================

# Test Ollama connection on startup
def test_ollama_connection() -> bool:
    """Test if Ollama is available"""
    ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    try:
        response = requests.get(f"{ollama_url}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            if models:
                model_names = [m.get("name", "unknown") for m in models]
                logging.info(f"✅ Ollama is online at {ollama_url}")
                logging.info(f"   Available models: {', '.join(model_names[:3])}")
                return True
    except Exception as e:
        logging.warning(f"⚠️ Ollama not available at {ollama_url}: {e}")
    return False

# Check on import
if os.environ.get("USE_OFFLINE_AI", "false").lower() == "true":
    test_ollama_connection()

def check_internet() -> bool:
    """
    Check if the internet (specifically Gemini) is reachable.
    """
    try:
        # Check connectivity to Google's public DNS or Gemini endpoint
        requests.get("https://generativelanguage.googleapis.com", timeout=3)
        return True
    except Exception:
        return False

def get_ai_status() -> dict:
    """
    Detects whether AI is online (Gemini) or offline (Ollama)
    """
    # Forced offline mode
    if os.environ.get("USE_OFFLINE_AI", "false").lower() == "true":
        return {
            "mode": "offline",
            "provider": "ollama"
        }

    # Auto Switching Logic
    is_online = check_internet()

    # Gemini Check
    if is_online and os.environ.get("AI_PROVIDER") == "gemini" and os.environ.get("GEMINI_API_KEY"):
         return {
            "mode": "online",
            "provider": "gemini"
        }

    # If Gemini is not configured or internet is down, fallback to Offline/Ollama
    return {
        "mode": "offline",
        "provider": "ollama"
    }

# Initialize Gemini if key exists
if os.environ.get("GEMINI_API_KEY"):
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# client_ai removed
###################################################################

@api_router.get("/ai/status")
async def ai_status():
    status = get_ai_status()
    return {
        "status": status["mode"],
        "provider": status["provider"]
    }

######################################################################
@api_router.post("/chat/message")
async def chat_with_ai(request: ChatRequest):
    try:
        # -----
        # -------------------------
        has_code = bool(request.code_context)

        system_prompt = get_dynamic_system_prompt(
            task_type=request.task_type,
            has_code=has_code
        )

        # -------------------------
        # 2. Load recent memory
        # -------------------------
        history = await get_recent_chat_history(request.session_id)

        # -------------------------
        # 3. Build OpenAI-style messages
        # -------------------------
        messages = [
            {"role": "system", "content": system_prompt}
        ]

        # Inject past history
        for msg in history:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        # Inject current user message(s) from frontend
        # (frontend sends messages = [{role, content}])
        messages.extend(request.messages)

        # Inject code context ONCE (only if provided)
        if request.code_context:
            messages.append({
                "role": "user",
                "content": (
                    "Here is the code:\n"
                    "```python\n"
                    f"{request.code_context}\n"
                    "```"
                )
            })

        # -------------------------
        # 4. AUTO MODEL SELECTION
        # -------------------------
        ai_status = get_ai_status()
        use_ollama = ai_status["mode"] != "online"
        text = None

        if ai_status["provider"] == "gemini":
            # =========================
            # GOOGLE GEMINI
            # =========================
            try:
                # Use gemini-2.5-flash as requested
                model = genai.GenerativeModel('gemini-2.5-flash')
                
                # Construct prompt for Gemini
                prompt_parts = [system_prompt]
                
                for msg in history:
                    prompt_parts.append(f"{msg['role'].upper()}: {msg['content']}")
                
                # Current user message
                prompt_parts.append(f"USER: {request.messages[-1]['content']}")
                
                if request.code_context:
                    prompt_parts.append(f"\nCONTEXT:\n{request.code_context}")

                response = model.generate_content(prompt_parts)
                text = response.text
            except Exception as e:
                 logging.error(f"Gemini Request Failed: {e}. Falling back to Ollama...")
                 # Detailed logging to help debug
                 import traceback
                 error_msg = traceback.format_exc()
                 logging.error(error_msg)
                 with open("backend_error.log", "w") as f:
                     f.write(error_msg)
                 use_ollama = True

        elif not use_ollama and ai_status["provider"] == "openai":
            # REMOVED OpenAI Support
            logging.warning("OpenAI is disabled. Falling back to Ollama.")
            use_ollama = True

        if use_ollama:
            # =========================
            # OLLAMA / DEEPSEEK (STREAMING)
            # =========================
            user_prompt = ""

            # Inject filtered memory (text only)
            for msg in history:
                user_prompt += msg["content"] + "\n"

            # Inject Current User Message
            user_prompt += request.messages[-1]["content"]

            # Add the Custom Design Injection (from before)
            user_prompt += (
                "\n\nIMPORTANT CODE QUALITY RULES:\n"
                "1. NO LAZINESS: Write the FULL code. No placeholders.\n"
                "2. PROPER FORMATTING: Use actual newlines and indentation. NEVER output code in a single line.\n"
                "3. DESIGN: Use modern CSS (gradients, rounded corners, shadows).\n"
                "4. FUNCTIONAL: Ensure the JavaScript logic is complete and error-free.\n"
            )

            # Chat-only constraint
            if request.task_type == "chat":
                user_prompt += "\n\nIMPORTANT: Do NOT generate code unless explicitly asked."

            # Inject code context if present
            if request.code_context:
                user_prompt += (
                    "\n\n--- CODE ---\n"
                    f"{request.code_context}"
                )

            # --- PERSISTENCE ---
            # Save USER message immediately
            await db.chat_messages.insert_one(
                ChatMessage(
                    session_id=request.session_id,
                    role="user",
                    content=request.messages[-1]["content"],
                    code_context=request.code_context
                ).model_dump()
            )

            async def stream_and_save():
                full_text = ""
                # We iterate the sync generator. FastAPI handles this fine in async contexts generally,
                # but valid to just yield.
                for chunk in call_ollama_stream(system_prompt, user_prompt):
                    full_text += chunk
                    yield chunk
                
                # Save ASSISTANT message after stream completes
                await db.chat_messages.insert_one(
                    ChatMessage(
                        session_id=request.session_id,
                        role="assistant",
                        content=full_text
                    ).model_dump()
                )

            return StreamingResponse(stream_and_save(), media_type="text/event-stream")

        # -------------------------
        # 5. Persist chat messages (Only for Gemini/Non-streaming fallback)
        # -------------------------
        await db.chat_messages.insert_many([
            ChatMessage(
                session_id=request.session_id,
                role="user",
                content=request.messages[-1]["content"],
                code_context=request.code_context
            ).model_dump(),
            ChatMessage(
                session_id=request.session_id,
                role="assistant",
                content=text
            ).model_dump()
        ])

        # -------------------------
        # 6. Return response
        # -------------------------
        return ChatResponse(
             response=text,
             session_id=request.session_id
        )

    except Exception as e:
        logging.exception("Chat endpoint crashed")
        raise HTTPException(
            status_code=500,
            detail=f"Chat failed: {e}"
        )


################################################

@api_router.get("/chat/history/{session_id}", response_model=List[ChatMessage])
async def get_chat_history(session_id: str):
    try:
        messages = await db.chat_messages.find(
            {"session_id": session_id},
            {"_id": 0}
        ).sort("timestamp", 1).to_list(1000)
        
        for msg in messages:
            if isinstance(msg['timestamp'], str):
                msg['timestamp'] = datetime.fromisoformat(msg['timestamp'])
        
        return messages
    except Exception as e:
        logging.error(f"History fetch error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/execute/code", response_model=CodeExecuteResponse)
async def execute_code(request: CodeExecuteRequest):
    import time
    start_time = time.time()
    
    try:
        if request.language == "python":
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(request.code)
                temp_file = f.name
            
            try:
                result = subprocess.run(
                    ['python3', temp_file],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                execution_time = time.time() - start_time
                
                if result.returncode != 0:
                    return CodeExecuteResponse(
                        output="",
                        error=result.stderr,
                        execution_time=execution_time
                    )
                
                return CodeExecuteResponse(
                    output=result.stdout,
                    error=None,
                    execution_time=execution_time
                )
            finally:
                os.unlink(temp_file)
        
        elif request.language == "javascript":
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
                f.write(request.code)
                temp_file = f.name
            
            try:
                result = subprocess.run(
                    ['node', temp_file],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                execution_time = time.time() - start_time
                
                if result.returncode != 0:
                    return CodeExecuteResponse(
                        output="",
                        error=result.stderr,
                        execution_time=execution_time
                    )
                
                return CodeExecuteResponse(
                    output=result.stdout,
                    error=None,
                    execution_time=execution_time
                )
            finally:
                os.unlink(temp_file)
        
        else:
            execution_time = time.time() - start_time
            raise HTTPException(status_code=400, detail="Unsupported language")
    
    except subprocess.TimeoutExpired:
        return CodeExecuteResponse(
            output="",
            error="Execution timeout (5s limit)",
            execution_time=5.0
        )
    except Exception as e:
        logging.error(f"Execute error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/github/action", response_model=GitHubResponse)
async def github_action(request: GitHubRequest):
    try:
        if request.action == "init":
            if not request.repo_path:
                raise HTTPException(status_code=400, detail="repo_path required")
            
            repo_path = Path(tempfile.gettempdir()) / request.repo_path
            repo_path.mkdir(parents=True, exist_ok=True)
            
            Repo.init(repo_path)
            return GitHubResponse(success=True, message=f"Repository initialized at {repo_path}")
        
        
        elif request.action == "commit":
            if not request.repo_path or not request.commit_message:
                raise HTTPException(status_code=400, detail="repo_path and commit_message required")

            repo_path = Path(tempfile.gettempdir()) / request.repo_path
            repo_path.mkdir(parents=True, exist_ok=True)

            # init repo if it doesn't exist
            if not (repo_path / ".git").exists():
                repo = Repo.init(repo_path)
            else:
                repo = Repo(repo_path)

            # Configure git user (required for commits)
            with repo.config_writer() as config:
                config.set_value("user", "name", "Gen-AI IDE User").release()
                config.set_value("user", "email", "ide@genai.local").release()

            # Ensure main branch exists
            try:
                repo.heads.main
            except IndexError:
                repo.create_head('main')

            # WRITE FILES
            if request.files:
                for file_data in request.files:
                    try:
                         # dict access or object check
                         fname = file_data['name'] if isinstance(file_data, dict) else file_data.name
                         fcontent = file_data['content'] if isinstance(file_data, dict) else file_data.content
                         
                         file_path = repo_path / fname
                         with open(file_path, "w", encoding="utf-8") as f:
                            f.write(fcontent)
                    except Exception as e:
                         logging.error(f"Failed to write file {file_data}: {e}")
            
            # Legacy fallback
            elif request.code and request.language:
                # Map language to correct file extension
                file_extensions = {
                    'python': 'main.py',
                    'javascript': 'main.js',
                    'html': 'index.html',
                    'css': 'style.css',
                    'java': 'Main.java',
                    'cpp': 'main.cpp',
                    'csharp': 'Program.cs',
                    'ruby': 'main.rb',
                    'go': 'main.go',
                    'rust': 'main.rs'
                }
                filename = file_extensions.get(request.language, f"main.{request.language}")
                file_path = repo_path / filename
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(request.code)

            repo.git.add(A=True)
            try:
                repo.index.commit(request.commit_message)
            except Exception:
                # nothing to commit
                pass
            
            # Ensure we're on main branch
            repo.heads.main.checkout()

            return GitHubResponse(success=True, message="Code committed successfully")
        
        
        elif request.action == "push":
            if not request.repo_path or not request.repo_url or not request.token:
                raise HTTPException(status_code=400, detail="repo_path, repo_url, and token required")
            
            repo_path = Path(tempfile.gettempdir()) / request.repo_path
            
            if not (repo_path / ".git").exists():
                raise HTTPException(status_code=400, detail="Repository not initialized. Run init and commit first.")
            
            repo = Repo(repo_path)
            
            # Configure git user
            with repo.config_writer() as config:
                try:
                    config.get_value("user", "name")
                except:
                    config.set_value("user", "name", "Gen-AI IDE User").release()
                try:
                    config.get_value("user", "email")
                except:
                    config.set_value("user", "email", "ide@genai.local").release()
            
            # Construct authentication URL
            auth_url = request.repo_url.replace("https://github.com/", f"https://{request.token}@github.com/")
            
            try:
                # Set or update remote
                if 'origin' not in [remote.name for remote in repo.remotes]:
                    origin = repo.create_remote('origin', auth_url)
                else:
                    origin = repo.remote('origin')
                    origin.set_url(auth_url)
                
                # Ensure we're on main branch
                try:
                    repo.heads.main.checkout()
                except IndexError:
                    repo.create_head('main')
                    repo.heads.main.checkout()
                
                # Use raw git command for more reliable push with upstream tracking
                logging.info(f"Attempting to push main branch to {request.repo_url}")
                result = repo.git.push('-u', 'origin', 'main', '--porcelain')
                logging.info(f"Push result: {result}")
                
                return GitHubResponse(success=True, message="Pushed to GitHub successfully!")
            
            except Exception as push_error:
                error_msg = str(push_error)
                logging.error(f"Push failed: {error_msg}")
                
                # Try with --force-with-lease as fallback
                try:
                    logging.warning("Attempting fallback with --force-with-lease...")
                    repo.git.push('-u', '--force-with-lease', 'origin', 'main')
                    return GitHubResponse(success=True, message="Pushed to GitHub (force-with-lease)!")
                except Exception as force_error:
                    error_msg = str(force_error)
                    logging.error(f"Force push also failed: {error_msg}")
                    
                    if "403" in error_msg or "fatal: unable to access" in error_msg:
                        return GitHubResponse(
                            success=False, 
                            message="❌ Permission denied (403). The token may belong to a different GitHub account than the repository owner. Verify: token user matches repo owner, or you're a collaborator with push access."
                        )
                    elif "404" in error_msg:
                        return GitHubResponse(
                            success=False,
                            message="❌ Repository not found (404). Check the URL exists and you have access."
                        )
                    elif "rejected" in error_msg.lower():
                        return GitHubResponse(
                            success=False,
                            message="❌ Push rejected. The repository might require authentication or the URL might be wrong. Create a new empty repository first."
                        )
                    else:
                        return GitHubResponse(success=False, message=f"❌ Push error: {error_msg}")
        
        else:
            raise HTTPException(status_code=400, detail="Invalid action")
    
    except Exception as e:
        logging.error(f"GitHub action error: {str(e)}")
        return GitHubResponse(success=False, message=str(e))

@api_router.post("/projects", response_model=CodeProject)
async def save_project(project: CodeProjectCreate):
    try:
        project_obj = CodeProject(**project.model_dump())
        doc = project_obj.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        doc['updated_at'] = doc['updated_at'].isoformat()
        
        await db.code_projects.insert_one(doc)
        return project_obj
    except Exception as e:
        logging.error(f"Save project error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/projects", response_model=List[CodeProject])
async def get_projects():
    try:
        projects = await db.code_projects.find({}, {"_id": 0}).sort("updated_at", -1).to_list(1000)
        
        for proj in projects:
            if isinstance(proj['created_at'], str):
                proj['created_at'] = datetime.fromisoformat(proj['created_at'])
            if isinstance(proj['updated_at'], str):
                proj['updated_at'] = datetime.fromisoformat(proj['updated_at'])
        
        return projects
    except Exception as e:
        logging.error(f"Get projects error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/")
async def root():
    return {"message": "Gen-AI Coding Environment API"}

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

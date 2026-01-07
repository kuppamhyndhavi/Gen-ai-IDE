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
from emergentintegrations.llm.chat import LlmChat, UserMessage
import subprocess
import tempfile
import json
from git import Repo
import shutil

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI()
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
    message: str
    code_context: Optional[str] = None
    task_type: str = "generate"  # generate, debug, optimize, document

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
    action: str  # init, commit, push
    repo_path: Optional[str] = None
    repo_url: Optional[str] = None
    commit_message: Optional[str] = None
    token: Optional[str] = None

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

# LLM Helper
def get_system_message(task_type: str) -> str:
    messages = {
        "generate": "You are an expert code generator. Generate clean, efficient, well-documented code based on user requirements. Always explain your code.",
        "debug": "You are an expert debugger. Analyze code, identify bugs, and provide corrected versions with explanations.",
        "optimize": "You are a code optimization expert. Analyze code and suggest performance improvements, better algorithms, and cleaner structure.",
        "document": "You are a technical documentation expert. Generate clear docstrings, comments, and README-style documentation for code."
    }
    return messages.get(task_type, messages["generate"])

@api_router.post("/chat/message", response_model=ChatResponse)
async def chat_with_ai(request: ChatRequest):
    try:
        api_key = os.environ.get('EMERGENT_LLM_KEY')
        system_msg = get_system_message(request.task_type)
        
        chat = LlmChat(
            api_key=api_key,
            session_id=request.session_id,
            system_message=system_msg
        ).with_model("openai", "gpt-5.1")
        
        full_message = request.message
        if request.code_context:
            full_message = f"Code context:\n```\n{request.code_context}\n```\n\nUser request: {request.message}"
        
        user_msg = UserMessage(text=full_message)
        response = await chat.send_message(user_msg)
        
        user_chat = ChatMessage(
            session_id=request.session_id,
            role="user",
            content=request.message,
            code_context=request.code_context
        )
        ai_chat = ChatMessage(
            session_id=request.session_id,
            role="assistant",
            content=response
        )
        
        user_doc = user_chat.model_dump()
        user_doc['timestamp'] = user_doc['timestamp'].isoformat()
        await db.chat_messages.insert_one(user_doc)
        
        ai_doc = ai_chat.model_dump()
        ai_doc['timestamp'] = ai_doc['timestamp'].isoformat()
        await db.chat_messages.insert_one(ai_doc)
        
        return ChatResponse(response=response, session_id=request.session_id)
    except Exception as e:
        logging.error(f"Chat error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

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
            repo = Repo(repo_path)
            
            repo.git.add(A=True)
            repo.index.commit(request.commit_message)
            
            return GitHubResponse(success=True, message="Changes committed")
        
        elif request.action == "push":
            if not request.repo_path or not request.repo_url or not request.token:
                raise HTTPException(status_code=400, detail="repo_path, repo_url, and token required")
            
            repo_path = Path(tempfile.gettempdir()) / request.repo_path
            repo = Repo(repo_path)
            
            auth_url = request.repo_url.replace("https://", f"https://{request.token}@")
            
            if 'origin' not in [remote.name for remote in repo.remotes]:
                origin = repo.create_remote('origin', auth_url)
            else:
                origin = repo.remote('origin')
                origin.set_url(auth_url)
            
            origin.push(refspec='main:main')
            
            return GitHubResponse(success=True, message="Pushed to GitHub")
        
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

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
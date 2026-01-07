import { useState, useEffect, useRef } from 'react';
import Editor from '@monaco-editor/react';
import axios from 'axios';
import { Play, Bug, Zap, FileText, Github, Settings, MessageSquare, Terminal as TerminalIcon, Save, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { toast } from 'sonner';
import { Toaster } from '@/components/ui/sonner';
import SettingsDialog from '../components/SettingsDialog';
import GitHubDialog from '../components/GitHubDialog';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const MainIDE = () => {
  const [code, setCode] = useState('# Write your Python code here\nprint("Hello, AI Coding Environment!")');
  const [language, setLanguage] = useState('python');
  const [output, setOutput] = useState('');
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [sessionId] = useState(() => `session-${Date.now()}`);
  const [isExecuting, setIsExecuting] = useState(false);
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [showTerminal, setShowTerminal] = useState(true);
  const [showChat, setShowChat] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const [showGitHub, setShowGitHub] = useState(false);
  const chatEndRef = useRef(null);
  const editorRef = useRef(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  useEffect(() => {
    loadChatHistory();
  }, []);

  const loadChatHistory = async () => {
    try {
      const response = await axios.get(`${API}/chat/history/${sessionId}`);
      setChatMessages(response.data);
    } catch (error) {
      console.error('Failed to load chat history:', error);
    }
  };

  const handleEditorDidMount = (editor, monaco) => {
    editorRef.current = editor;
    editor.focus();
  };

  const executeCode = async () => {
    setIsExecuting(true);
    setOutput('Executing...');
    try {
      const response = await axios.post(`${API}/execute/code`, {
        code,
        language
      });

      if (response.data.error) {
        setOutput(`Error:\n${response.data.error}`);
        toast.error('Execution failed');
      } else {
        setOutput(response.data.output || 'Execution completed (no output)');
        toast.success(`Executed in ${response.data.execution_time.toFixed(3)}s`);
      }
    } catch (error) {
      setOutput(`Error: ${error.response?.data?.detail || error.message}`);
      toast.error('Execution failed');
    } finally {
      setIsExecuting(false);
    }
  };

  const sendChatMessage = async (taskType = 'generate') => {
    if (!chatInput.trim()) return;

    const userMessage = {
      id: `msg-${Date.now()}`,
      session_id: sessionId,
      role: 'user',
      content: chatInput,
      timestamp: new Date().toISOString()
    };

    setChatMessages(prev => [...prev, userMessage]);
    setChatInput('');
    setIsChatLoading(true);

    try {
      const response = await axios.post(`${API}/chat/message`, {
        session_id: sessionId,
        message: chatInput,
        code_context: code,
        task_type: taskType
      });

      const aiMessage = {
        id: `msg-${Date.now()}-ai`,
        session_id: sessionId,
        role: 'assistant',
        content: response.data.response,
        timestamp: new Date().toISOString()
      };

      setChatMessages(prev => [...prev, aiMessage]);
    } catch (error) {
      console.error('Chat error:', error);
      toast.error('Failed to get AI response');
    } finally {
      setIsChatLoading(false);
    }
  };

  const handleDebug = () => {
    setChatInput('Please debug this code and explain any issues you find.');
    setTimeout(() => sendChatMessage('debug'), 100);
  };

  const handleOptimize = () => {
    setChatInput('Please optimize this code for better performance.');
    setTimeout(() => sendChatMessage('optimize'), 100);
  };

  const handleDocument = () => {
    setChatInput('Please generate documentation for this code with docstrings.');
    setTimeout(() => sendChatMessage('document'), 100);
  };

  const saveProject = async () => {
    try {
      await axios.post(`${API}/projects`, {
        name: `Project ${new Date().toLocaleString()}`,
        code,
        language
      });
      toast.success('Project saved!');
    } catch (error) {
      console.error('Save error:', error);
      toast.error('Failed to save project');
    }
  };

  return (
    <div data-testid="main-ide" className="h-screen flex flex-col bg-background text-foreground">
      <Toaster position="top-right" duration={2000} />
      
      {/* Toolbar */}
      <div data-testid="toolbar" className="h-14 border-b border-border flex items-center justify-between px-4 bg-card">
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-mono font-bold tracking-tight text-primary">Gen-AI IDE</h1>
          <span className="text-xs text-muted-foreground font-mono">v1.0</span>
        </div>
        
        <div className="flex items-center gap-2">
          <Button
            data-testid="run-code-button"
            onClick={executeCode}
            disabled={isExecuting}
            className="bg-accent hover:bg-accent/90 text-accent-foreground"
            size="sm"
          >
            {isExecuting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            <span className="ml-2">Run</span>
          </Button>
          
          <Button
            data-testid="debug-button"
            onClick={handleDebug}
            variant="outline"
            size="sm"
          >
            <Bug className="h-4 w-4" />
            <span className="ml-2">Debug</span>
          </Button>
          
          <Button
            data-testid="optimize-button"
            onClick={handleOptimize}
            variant="outline"
            size="sm"
          >
            <Zap className="h-4 w-4" />
            <span className="ml-2">Optimize</span>
          </Button>
          
          <Button
            data-testid="document-button"
            onClick={handleDocument}
            variant="outline"
            size="sm"
          >
            <FileText className="h-4 w-4" />
            <span className="ml-2">Document</span>
          </Button>
          
          <div className="w-px h-6 bg-border mx-2" />
          
          <Button
            data-testid="save-project-button"
            onClick={saveProject}
            variant="outline"
            size="sm"
          >
            <Save className="h-4 w-4" />
          </Button>
          
          <Button
            data-testid="github-button"
            onClick={() => setShowGitHub(true)}
            variant="outline"
            size="sm"
          >
            <Github className="h-4 w-4" />
          </Button>
          
          <Button
            data-testid="settings-button"
            onClick={() => setShowSettings(true)}
            variant="outline"
            size="sm"
          >
            <Settings className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Code Editor */}
        <div data-testid="code-editor-container" className="flex-1 flex flex-col border-r border-border">
          <div className="h-10 border-b border-border flex items-center px-4 bg-secondary">
            <select
              data-testid="language-select"
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="bg-background border border-border rounded px-2 py-1 text-sm font-mono"
            >
              <option value="python">Python</option>
              <option value="javascript">JavaScript</option>
            </select>
          </div>
          <div className="flex-1">
            <Editor
              height="100%"
              language={language}
              value={code}
              onChange={(value) => setCode(value || '')}
              onMount={handleEditorDidMount}
              theme="vs-dark"
              options={{
                fontSize: 14,
                minimap: { enabled: false },
                fontFamily: 'Fira Code, monospace',
                fontLigatures: true,
                lineNumbers: 'on',
                scrollBeyondLastLine: false,
                automaticLayout: true,
              }}
            />
          </div>
        </div>

        {/* AI Chat Panel */}
        {showChat && (
          <div data-testid="chat-panel" className="w-96 flex flex-col border-r border-border bg-card">
            <div className="h-10 border-b border-border flex items-center justify-between px-4 bg-secondary">
              <div className="flex items-center gap-2">
                <MessageSquare className="h-4 w-4 text-primary" />
                <span className="text-sm font-mono font-semibold">AI Assistant</span>
              </div>
              <Button
                data-testid="close-chat-button"
                onClick={() => setShowChat(false)}
                variant="ghost"
                size="sm"
                className="h-6 w-6 p-0"
              >
                ×
              </Button>
            </div>
            
            <ScrollArea className="flex-1 p-4">
              <div className="space-y-3">
                {chatMessages.map((msg) => (
                  <div
                    key={msg.id}
                    data-testid={`chat-message-${msg.role}`}
                    className={`p-3 rounded-md text-sm ${msg.role === 'user'
                      ? 'bg-primary/20 border border-primary/40 ml-8'
                      : 'bg-secondary border border-border mr-8'
                    }`}
                  >
                    <div className="font-mono text-xs text-muted-foreground mb-1">
                      {msg.role === 'user' ? 'You' : 'AI'}
                    </div>
                    <div className="whitespace-pre-wrap break-words">{msg.content}</div>
                  </div>
                ))}
                {isChatLoading && (
                  <div data-testid="chat-loading" className="flex items-center gap-2 text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span className="text-sm">AI is thinking...</span>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>
            </ScrollArea>
            
            <div className="border-t border-border p-4">
              <div className="flex gap-2">
                <Input
                  data-testid="chat-input"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && sendChatMessage()}
                  placeholder="Ask AI to generate, debug, or optimize..."
                  className="flex-1 bg-background border-border font-sans"
                />
                <Button
                  data-testid="send-chat-button"
                  onClick={() => sendChatMessage()}
                  disabled={isChatLoading || !chatInput.trim()}
                  size="sm"
                  className="bg-primary hover:bg-primary/90"
                >
                  Send
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Terminal Output */}
      {showTerminal && (
        <div data-testid="terminal-panel" className="h-64 border-t border-border bg-black flex flex-col">
          <div className="h-10 border-b border-border flex items-center justify-between px-4 bg-secondary">
            <div className="flex items-center gap-2">
              <TerminalIcon className="h-4 w-4 text-accent" />
              <span className="text-sm font-mono font-semibold">Terminal Output</span>
            </div>
            <Button
              data-testid="close-terminal-button"
              onClick={() => setShowTerminal(false)}
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0"
            >
              ×
            </Button>
          </div>
          <ScrollArea className="flex-1">
            <pre data-testid="terminal-output" className="terminal-output">{output || 'No output yet. Run your code to see results here.'}</pre>
          </ScrollArea>
        </div>
      )}

      {/* Floating buttons to reopen panels */}
      {!showChat && (
        <Button
          data-testid="reopen-chat-button"
          onClick={() => setShowChat(true)}
          className="fixed right-4 bottom-20 bg-primary hover:bg-primary/90"
          size="sm"
        >
          <MessageSquare className="h-4 w-4" />
        </Button>
      )}
      
      {!showTerminal && (
        <Button
          data-testid="reopen-terminal-button"
          onClick={() => setShowTerminal(true)}
          className="fixed right-4 bottom-4 bg-accent hover:bg-accent/90"
          size="sm"
        >
          <TerminalIcon className="h-4 w-4" />
        </Button>
      )}

      <SettingsDialog open={showSettings} onClose={() => setShowSettings(false)} />
      <GitHubDialog open={showGitHub} onClose={() => setShowGitHub(false)} code={code} language={language} />
    </div>
  );
};

export default MainIDE;
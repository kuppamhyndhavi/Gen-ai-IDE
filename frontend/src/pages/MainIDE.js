/* eslint-disable react-hooks/exhaustive-deps */
import { useState, useEffect, useRef, useCallback } from 'react';
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
  const templates = {
    python: '# Write your Python code here\nprint("Hello World")',
    javascript: '// JavaScript file\nconsole.log("Hello World");',
    html:
      `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<title>My Page</title>


<link rel="stylesheet" href="style.css" />
</head>
<body>
<h1>Hello World</h1>


<script src="script.js"></script>
</body>
</html>`,
    css:
      `/* style.css */
body {
  font-family: Arial, sans-serif;
  background: #f5f5f5;
  padding: 20px;
}

h1 {
  color: #2563eb;
}`

  };

  const [files, setFiles] = useState([
    {
      id: 'py',
      name: 'main.py',
      language: 'python',
      content: templates.python
    },
    {
      id: 'html',
      name: 'index.html',
      language: 'html',
      content: templates.html
    },
    {
      id: 'css',
      name: 'style.css',
      language: 'css',
      content: templates.css
    },
    {
      id: 'js',
      name: 'script.js',
      language: 'javascript',
      content: templates.javascript
    }
  ]);

  const [activeFileId, setActiveFileId] = useState('py');

  const activeFile = files.find(f => f.id === activeFileId);

  const code = activeFile?.content || '';
  const fileType = activeFile?.language || null;

  const getFileByName = (name) =>
    files.find(f => f.name === name);

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
  const previewWindowRef = useRef(null);

  ////////////////////////////////////////////////////////////////////////////////////
  // AI online/offline status
  const [aiStatus, setAiStatus] = useState({
    status: 'checking',
    provider: 'unknown'
  });
  //////////////////////////////////////////////////////////////////////////////////

  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: 'auto' });
    }
  }, [chatMessages.length]);




  useEffect(() => {//////////////////////////////////////////////////////////
    fetchAIStatus(); // initial check
    const interval = setInterval(fetchAIStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  // Update language when switching files
  useEffect(() => {
    if (activeFile?.language) {
      setLanguage(activeFile.language);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeFileId]);

  useEffect(() => {
    if (
      previewWindowRef.current &&
      !previewWindowRef.current.closed &&
      (fileType === 'html' || fileType === 'css' || fileType === 'javascript')
    ) {
      openWebPreview();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [files]);



  const loadChatHistory = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/chat/history/${sessionId}`);
      setChatMessages(response.data);
    } catch (error) {
      console.error('Failed to load chat history:', error);
    }
  }, [sessionId]);

  useEffect(() => {
    loadChatHistory();
  }, [loadChatHistory]);

  const handleEditorDidMount = (editor, monaco) => {
    editorRef.current = editor;
    editor.focus();
  };

  const executeCode = async () => {
    // 🌐 FRONTEND PREVIEW FILES
    if (fileType === 'html' || fileType === 'css' || fileType === 'javascript') {
      openWebPreview();
      return;
    }

    // 🐍 BACKEND EXECUTION (Python / Node)
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

  ///web preview function
  const openWebPreview = () => {
    const htmlFile = getFileByName('index.html');
    const cssFile = getFileByName('style.css');
    const jsFile = getFileByName('script.js');

    if (!htmlFile) {
      toast.error('index.html not found');
      return;
    }

    let combinedHTML = htmlFile.content;

    // Inject CSS before </head>
    if (cssFile?.content) {
      combinedHTML = combinedHTML.replace(
        '</head>',
        `<style>${cssFile.content}</style></head>`
      );
    }

    // Inject JS before </body>
    if (jsFile?.content) {
      combinedHTML = combinedHTML.replace(
        '</body>',
        `<script>${jsFile.content}</script></body>`
      );
    }

    if (!previewWindowRef.current || previewWindowRef.current.closed) {
      previewWindowRef.current = window.open('', '_blank');
    }

    previewWindowRef.current.document.open();
    previewWindowRef.current.document.write(combinedHTML);
    previewWindowRef.current.document.close();
  };




  /////////////////////////////////////////////////////////////////////////////////////////////////////////////

  // Fetch AI online/offline status
  const fetchAIStatus = async () => {
    try {
      const res = await axios.get(`${API}/ai/status`);
      setAiStatus(res.data);
    } catch (err) {
      setAiStatus({
        status: 'offline',
        provider: 'ollama'
      });
    }
  };


  ////////////////////////////////////////////////////////////////////////////////////////////////////////////

  const extractCodeBlocks = (text) => {
    const codeBlockRegex = /```(\w+)?\s*([\s\S]*?)```/g;
    let match;
    const codes = {};
    let cleanText = text;

    while ((match = codeBlockRegex.exec(text)) !== null) {
      const language = match[1] ? match[1].toLowerCase() : '';
      let codeContent = match[2].trim();

      // FIX: Handle cases where model outputs literal "\n" strings instead of actual newlines
      codeContent = codeContent.replace(/\\n/g, '\n').replace(/\\"/g, '"');

      if (language === 'html') codes['html'] = codeContent;
      if (language === 'css') codes['css'] = codeContent;
      if (language === 'javascript' || language === 'js') codes['js'] = codeContent;
      if (language === 'python' || language === 'py') codes['py'] = codeContent;

      // Remove the code block from the text
      cleanText = cleanText.replace(match[0], '');
    }

    return { cleanText: cleanText.trim(), codes };
  };

  const sendChatMessage = async (taskType = 'chat', includeCode = false) => {
    if (!chatInput.trim()) return;

    const payload = {
      session_id: sessionId,
      task_type: taskType,
      messages: [{ role: 'user', content: chatInput }],
      code_context: includeCode ? code : undefined
    };

    if (includeCode) {
      payload.code_context = code;
    }

    // 1. Add User Message
    setChatMessages(prev => [
      ...prev,
      {
        id: `msg-${Date.now()}`,
        session_id: sessionId,
        role: 'user',
        content: chatInput,
        timestamp: new Date().toISOString()
      }
    ]);

    setChatInput('');
    setIsChatLoading(true);

    // 2. Add Placeholder Assistant Message
    const assistantMsgId = `msg-${Date.now()}-ai`;
    setChatMessages(prev => [
      ...prev,
      {
        id: assistantMsgId,
        session_id: sessionId,
        role: 'assistant',
        content: '...', // Initial placeholder
        timestamp: new Date().toISOString()
      }
    ]);

    try {
      // 3. Start Streaming Request
      const response = await fetch(`${API}/chat/message`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      let fullText = '';

      // Check content type to handle both Standard JSON (Gemini) and Stream (Ollama)
      const contentType = response.headers.get('content-type');

      if (contentType && contentType.includes('application/json')) {
        // Handle standard JSON response (Gemini)
        const data = await response.json();
        fullText = data.response || '';
        if (data.detail) fullText = `Error: ${data.detail}`;

        // Update UI immediately since it's not a stream
        setChatMessages(prev =>
          prev.map(msg =>
            msg.id === assistantMsgId
              ? { ...msg, content: fullText }
              : msg
          )
        );

      } else {
        // Handle Streaming response (Ollama / Event Stream)
        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });
          fullText += chunk;

          // Update the UI with the new chunk
          setChatMessages(prev =>
            prev.map(msg =>
              msg.id === assistantMsgId
                ? { ...msg, content: fullText }
                : msg
            )
          );
        }
      }

      // 4. Final processing (extract code)
      const { cleanText, codes } = extractCodeBlocks(fullText);

      // Auto-update files if code is present
      if (Object.keys(codes).length > 0) {
        setFiles(prev => prev.map(f => {
          if (codes[f.id]) {
            return { ...f, content: codes[f.id] };
          }
          return f;
        }));
        toast.success("Code updated in editor! 🚀");
      }

      // Update final message content (optional: add status marker)
      setChatMessages(prev =>
        prev.map(msg =>
          msg.id === assistantMsgId
            ? { ...msg, content: Object.keys(codes).length > 0 ? cleanText + "\n\n**[Code automatically applied]**" : fullText }
            : msg
        )
      );

    } catch (error) {
      console.error("Streaming error:", error);
      toast.error('AI Request failed');
      setChatMessages(prev =>
        prev.map(msg =>
          msg.id === assistantMsgId
            ? { ...msg, content: `Error: ${error.message}` }
            : msg
        )
      );
    } finally {
      setIsChatLoading(false);
    }
  };

  //////////////////////////////////////////////////////////////////////////////////////////////////////////

  const injectCodeAndSend = (prompt, taskType) => {
    const messageWithCode =
      `${prompt}

──────── CODE ────────
\`\`\`${language}
${code}
\`\`\`
`;

    setChatInput(messageWithCode);
    setTimeout(() => sendChatMessage(taskType, true), 50);
  };

  const handleDebug = () =>
    injectCodeAndSend(
      'Please debug this code and explain any issues you find.',
      'debug'
    );

  const handleOptimize = () =>
    injectCodeAndSend(
      'Please optimize this code for better performance.',
      'optimize'
    );

  const handleDocument = () =>
    injectCodeAndSend(
      'Please generate documentation for this code with docstrings.',
      'document'
    );
  ///////////////////////////////////////////////////////////////////////////////////////////////////////////


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
      <div data-testid="toolbar" className="h-16 border-b-2 border-primary/20 flex items-center justify-between px-6 bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 shadow-lg">
        <div className="flex items-center gap-3">
          <div className="bg-gradient-to-br from-blue-500 to-purple-600 p-2 rounded-lg">
            <h1 className="text-lg font-mono font-bold tracking-tight text-white">⚡ Gen-AI IDE</h1>
          </div>
          <span className="text-xs text-blue-400 font-mono font-semibold bg-blue-500/10 px-2 py-1 rounded">v1.0</span>
        </div>

        <div className="flex items-center gap-2">
          {/* AI Status Indicator */}
          <div className="flex items-center gap-2 mr-4 bg-slate-700/50 px-3 py-1.5 rounded-lg border border-slate-600">
            <span
              className={`h-2.5 w-2.5 rounded-full animate-pulse ${aiStatus.status === 'online'
                ? 'bg-emerald-500'
                : 'bg-orange-500'
                }`}
            />
            <span className="text-xs font-mono font-semibold text-slate-200">
              {aiStatus.status === 'online'
                ? '✨ Gemini'
                : '📡 Ollama (Offline)'}
            </span>
          </div>

          <Button
            data-testid="run-code-button"
            onClick={executeCode}
            disabled={isExecuting}
            className="bg-gradient-to-r from-green-500 to-emerald-600 hover:from-green-600 hover:to-emerald-700 text-white font-semibold shadow-lg hover:shadow-xl transition-all duration-200 transform hover:scale-105"
            size="sm"
          >
            {isExecuting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            <span className="ml-2">Run</span>
          </Button>

          <Button
            data-testid="debug-button"
            onClick={handleDebug}
            className="bg-red-500/20 hover:bg-red-500/30 text-red-300 border border-red-500/40 font-semibold transition-all duration-200 hover:border-red-500/60"
            size="sm"
          >
            <Bug className="h-4 w-4" />
            <span className="ml-2">Debug</span>
          </Button>

          <Button
            data-testid="optimize-button"
            onClick={handleOptimize}
            className="bg-yellow-500/20 hover:bg-yellow-500/30 text-yellow-300 border border-yellow-500/40 font-semibold transition-all duration-200 hover:border-yellow-500/60"
            size="sm"
          >
            <Zap className="h-4 w-4" />
            <span className="ml-2">Optimize</span>
          </Button>

          <Button
            data-testid="document-button"
            onClick={handleDocument}
            className="bg-blue-500/20 hover:bg-blue-500/30 text-blue-300 border border-blue-500/40 font-semibold transition-all duration-200 hover:border-blue-500/60"
            size="sm"
          >
            <FileText className="h-4 w-4" />
            <span className="ml-2">Document</span>
          </Button>

          <div className="w-px h-8 bg-slate-600 mx-3" />

          <Button
            data-testid="save-project-button"
            onClick={saveProject}
            className="bg-purple-500/20 hover:bg-purple-500/30 text-purple-300 border border-purple-500/40 transition-all duration-200 hover:border-purple-500/60"
            size="sm"
          >
            <Save className="h-4 w-4" />
          </Button>

          <Button
            data-testid="github-button"
            onClick={() => setShowGitHub(true)}
            className="bg-slate-600/50 hover:bg-slate-600 text-white border border-slate-500 transition-all duration-200 hover:border-slate-400"
            size="sm"
          >
            <Github className="h-4 w-4" />
          </Button>

          <Button
            data-testid="settings-button"
            onClick={() => setShowSettings(true)}
            className="bg-slate-600/50 hover:bg-slate-600 text-white border border-slate-500 transition-all duration-200 hover:border-slate-400"
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
          {/* 🧠 TAB BAR — PLACE IT HERE */}
          <div className="h-12 border-b-2 border-slate-700 flex items-center bg-gradient-to-r from-slate-900 to-slate-800 px-3 gap-1">
            {files.map(file => (
              <button
                key={file.id}
                onClick={() => {
                  setActiveFileId(file.id);

                  if (file.language === 'python' || file.language === 'javascript') {
                    setLanguage(file.language);
                  } else {
                    setLanguage(activeFile.language);
                  }
                }}
                className={`px-4 py-2 mr-0.5 text-sm font-mono font-semibold rounded-t-lg transition-all duration-200 ${file.id === activeFileId
                  ? 'bg-gradient-to-b from-blue-500 to-blue-600 text-white shadow-lg border-b-2 border-blue-400'
                  : 'bg-slate-700/40 text-slate-400 hover:bg-slate-700/60 hover:text-slate-300'
                  }`}
              >
                {file.name}
              </button>
            ))}
          </div>

          {/* 🧠 MONACO EDITOR — BELOW THE TAB BAR */}
          <div className="flex-1">
            <Editor
              height="100%"
              language={activeFile?.language}
              value={activeFile?.content}
              onChange={(value) =>
                setFiles(prev =>
                  prev.map(file =>
                    file.id === activeFileId
                      ? { ...file, content: value || '' }
                      : file
                  )
                )
              }
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

            <ScrollArea className="flex-1 overflow-hidden bg-gradient-to-b from-slate-950 to-slate-900">
              <div className="space-y-4 pr-4 p-4">
                {chatMessages.map((msg) => (
                  <div
                    key={msg.id}
                    data-testid={`chat-message-${msg.role}`}
                    className={`p-4 rounded-lg text-sm transition-all duration-200 ${msg.role === 'user'
                      ? 'bg-gradient-to-r from-blue-600/30 to-blue-500/20 border border-blue-500/60 ml-8 shadow-lg'
                      : 'bg-gradient-to-r from-slate-800 to-slate-700 border border-slate-600 mr-8 shadow-lg'
                      }`}
                  >
                    <div className={`font-mono text-xs font-bold mb-2 ${msg.role === 'user' ? 'text-blue-300' : 'text-emerald-300'
                      }`}>
                      {msg.role === 'user' ? '👤 You' : '🤖 AI Assistant'}
                    </div>
                    <div className="whitespace-pre-wrap break-words font-mono text-sm text-slate-100 leading-relaxed">
                      {msg.content}
                    </div>

                  </div>
                ))}
                {isChatLoading && (
                  <div data-testid="chat-loading" className="flex items-center gap-3 text-blue-400 ml-8">
                    <Loader2 className="h-5 w-5 animate-spin" />
                    <span className="text-sm font-semibold">✨ AI is thinking...</span>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>
            </ScrollArea>

            <div className="border-t-2 border-slate-700 bg-gradient-to-r from-slate-900 to-slate-800 p-4">
              <div className="flex gap-2 items-end">
                <textarea
                  data-testid="chat-input"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && sendChatMessage()}
                  placeholder="Ask AI to generate, debug, or optimize..."
                  className="flex-1 bg-slate-800 border-2 border-slate-600 hover:border-slate-500 focus:border-blue-500 focus:bg-slate-750 text-white rounded-lg px-3 py-2 font-mono text-sm resize-none transition-all duration-200 placeholder-slate-500"
                  rows="3"
                />
                <Button
                  data-testid="send-chat-button"
                  onClick={() => sendChatMessage()}
                  disabled={isChatLoading || !chatInput.trim()}
                  size="sm"
                  className="bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white font-semibold shadow-lg hover:shadow-xl transition-all duration-200 transform hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
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

      {/* Chat and Terminal panels always visible */}

      <SettingsDialog open={showSettings} onClose={() => setShowSettings(false)} />
      <GitHubDialog
        open={showGitHub}
        onClose={() => setShowGitHub(false)}
        code={code}
        language={language}
        files={
          activeFile.language === 'python'
            ? [activeFile]
            : files
        }
      />
    </div>
  );
};

export default MainIDE;
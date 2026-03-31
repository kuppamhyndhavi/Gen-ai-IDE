import { useState } from 'react';
import axios from 'axios';
import { Github, AlertCircle, CheckCircle, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const GitHubDialog = ({ open, onClose, code, language }) => {
  const [step, setStep] = useState('form'); // 'form', 'processing', 'result'
  const [formData, setFormData] = useState({
    repoUrl: '',
    token: '',
    message: 'Initial commit'
  });
  const [result, setResult] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [repoPath] = useState(`repo-${Date.now()}`);

  if (!open) return null;

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handlePush = async () => {
    if (!formData.repoUrl || !formData.token) {
      toast.error('Please fill in all fields');
      return;
    }

    setIsLoading(true);
    setStep('processing');

    try {
      // Step 1: Initialize repository
      const initRes = await axios.post(`${API}/github/action`, {
        action: 'init',
        repo_path: repoPath
      });

      if (!initRes.data.success) {
        throw new Error(initRes.data.message);
      }

      toast.success('Repository initialized');

      // Step 2: Commit code
      const commitRes = await axios.post(`${API}/github/action`, {
        action: 'commit',
        repo_path: repoPath,
        commit_message: formData.message,
        code,
        language
      });

      if (!commitRes.data.success) {
        throw new Error(commitRes.data.message);
      }

      toast.success('Code committed');

      // Step 3: Push to GitHub
      const pushRes = await axios.post(`${API}/github/action`, {
        action: 'push',
        repo_path: repoPath,
        repo_url: formData.repoUrl,
        token: formData.token
      });

      if (pushRes.data.success) {
        setResult({
          success: true,
          message: 'Successfully pushed to GitHub! 🎉',
          details: pushRes.data.message
        });
        toast.success('Pushed to GitHub!');
      } else {
        setResult({
          success: false,
          message: 'Push failed',
          details: pushRes.data.message,
          troubleshooting: [
            '✓ Check the repository URL - ensure it matches YOUR GitHub username',
            '✓ Verify the token belongs to the account that owns/has access to the repo',
            '✓ If using another user\'s repo, you need to be added as a collaborator',
            '✓ Ensure token has "repo" scope permission',
            '✓ Token should not be expired',
            '✓ For a fresh start, create a new repo under your own account'
          ]
        });
        toast.error('Push failed - see details below');
      }
    } catch (error) {
      const errorMsg = error.response?.data?.detail || error.message;
      setResult({
        success: false,
        message: 'Error during GitHub operation',
        details: errorMsg,
        troubleshooting: [
          '✓ Check your internet connection',
          '✓ Verify backend is running',
          '✓ Check GitHub token validity',
          '✓ Ensure repository URL is correct'
        ]
      });
      toast.error('GitHub operation failed');
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setStep('form');
    setResult(null);
    setFormData({
      repoUrl: '',
      token: '',
      message: 'Initial commit'
    });
  };

  const handleClose = () => {
    handleReset();
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center">
      <div className="bg-card border border-border rounded-lg p-6 w-full max-w-md shadow-lg">
        {/* Header */}
        <div className="flex items-center gap-2 mb-6">
          <Github className="h-5 w-5 text-primary" />
          <h2 className="text-lg font-semibold">Push to GitHub</h2>
        </div>

        {/* Form Step */}
        {step === 'form' && (
          <div className="space-y-4">
            <div className="bg-blue-500/10 border border-blue-500/50 p-3 rounded-md text-xs text-blue-400 mb-4">
              <p className="font-semibold mb-2">📝 Setup Instructions:</p>
              <ol className="space-y-1 list-decimal list-inside">
                <li>Create empty repo on GitHub: github.com/new</li>
                <li>Generate token: github.com/settings/tokens (select 'repo')</li>
                <li>Enter URL: https://github.com/username/repo.git</li>
                <li>Paste token below and click Push</li>
              </ol>
            </div>

            <div>
              <label className="text-sm font-mono text-muted-foreground">
                Repository URL
              </label>
              <Input
                name="repoUrl"
                value={formData.repoUrl}
                onChange={handleInputChange}
                placeholder="https://github.com/username/repo.git"
                className="mt-1 font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground mt-1">
                Format: https://github.com/username/repo.git (repository must exist and be empty)
              </p>
            </div>

            <div>
              <label className="text-sm font-mono text-muted-foreground">
                GitHub Personal Access Token
              </label>
              <Input
                name="token"
                type="password"
                value={formData.token}
                onChange={handleInputChange}
                placeholder="ghp_xxxxxxxxxxxxxxxx"
                className="mt-1 font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground mt-1">
                Create at: github.com/settings/tokens (select 'repo' scope)
              </p>
            </div>

            <div>
              <label className="text-sm font-mono text-muted-foreground">
                Commit Message
              </label>
              <Input
                name="message"
                value={formData.message}
                onChange={handleInputChange}
                placeholder="Initial commit"
                className="mt-1 font-mono text-sm"
              />
            </div>

            <div className="flex gap-2 pt-4">
              <Button
                onClick={handlePush}
                disabled={isLoading}
                className="flex-1 bg-primary hover:bg-primary/90"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    Pushing...
                  </>
                ) : (
                  <>
                    <Github className="h-4 w-4 mr-2" />
                    Push to GitHub
                  </>
                )}
              </Button>
              <Button
                onClick={handleClose}
                variant="outline"
              >
                Cancel
              </Button>
            </div>
          </div>
        )}

        {/* Processing Step */}
        {step === 'processing' && (
          <div className="flex flex-col items-center justify-center py-8">
            <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
            <p className="text-sm text-muted-foreground text-center">
              Pushing your code to GitHub...
            </p>
          </div>
        )}

        {/* Result Step */}
        {step === 'result' && result && (
          <div className="space-y-4">
            <div className="flex items-start gap-3">
              {result.success ? (
                <CheckCircle className="h-5 w-5 text-green-500 mt-0.5 flex-shrink-0" />
              ) : (
                <AlertCircle className="h-5 w-5 text-red-500 mt-0.5 flex-shrink-0" />
              )}
              <div className="flex-1">
                <h3 className={`font-semibold ${
                  result.success ? 'text-green-500' : 'text-red-500'
                }`}>
                  {result.message}
                </h3>
                <p className="text-sm text-muted-foreground mt-1">
                  {result.details}
                </p>
              </div>
            </div>

            {result.troubleshooting && (
              <div className="bg-secondary p-3 rounded-md">
                <p className="text-xs font-semibold text-muted-foreground mb-2">
                  Troubleshooting tips:
                </p>
                <ul className="space-y-1">
                  {result.troubleshooting.map((tip, idx) => (
                    <li key={idx} className="text-xs text-muted-foreground font-mono">
                      {tip}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="flex gap-2 pt-4">
              <Button
                onClick={handleReset}
                className="flex-1 bg-primary hover:bg-primary/90"
              >
                Try Again
              </Button>
              <Button
                onClick={handleClose}
                variant="outline"
              >
                Close
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default GitHubDialog;

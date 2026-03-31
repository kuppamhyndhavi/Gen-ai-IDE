import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import axios from 'axios';
import { Github, GitBranch, Upload, AlertCircle, CheckCircle, Loader2 } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export const GitHubDialog = ({ open, onClose, code, language, files }) => {
  const [repoPath, setRepoPath] = useState('my-code-project');
  const [repoUrl, setRepoUrl] = useState('');
  const [token, setToken] = useState('');
  const [commitMessage, setCommitMessage] = useState('Update code from Gen-AI IDE');
  const [loading, setLoading] = useState(false);
  const [steps, setSteps] = useState({
    init: null,
    commit: null,
    push: null
  });

  const updateStep = (step, status) => {
    setSteps(prev => ({
      ...prev,
      [step]: status
    }));
  };

  const resetSteps = () => {
    setSteps({
      init: null,
      commit: null,
      push: null
    });
  };

  const handlePushWorkflow = async () => {
    if (!repoPath) {
      toast.error('Repository name is required');
      return;
    }
    if (!repoUrl) {
      toast.error('Repository URL is required');
      return;
    }
    if (!token) {
      toast.error('GitHub token is required');
      return;
    }

    setLoading(true);
    resetSteps();

    try {
      // Step 1: Initialize
      updateStep('init', 'loading');
      try {
        const initRes = await axios.post(`${API}/github/action`, {
          action: 'init',
          repo_path: repoPath
        });
        if (!initRes.data.success) throw new Error(initRes.data.message);
        updateStep('init', 'success');
      } catch (error) {
        updateStep('init', 'error');
        throw new Error(`Init failed: ${error.response?.data?.message || error.message}`);
      }

      // Step 2: Commit
      updateStep('commit', 'loading');
      try {
        const payload = {
          action: 'commit',
          repo_path: repoPath,
          commit_message: commitMessage
        };

        if (files && files.length > 0) {
          payload.files = files.map(f => ({ name: f.name, content: f.content }));
        } else {
          payload.code = code;
          payload.language = language;
        }

        const commitRes = await axios.post(`${API}/github/action`, payload);
        if (!commitRes.data.success) throw new Error(commitRes.data.message);
        updateStep('commit', 'success');
      } catch (error) {
        updateStep('commit', 'error');
        throw new Error(`Commit failed: ${error.response?.data?.message || error.message}`);
      }

      // Step 3: Push
      updateStep('push', 'loading');
      try {
        const pushRes = await axios.post(`${API}/github/action`, {
          action: 'push',
          repo_path: repoPath,
          repo_url: repoUrl,
          token: token
        });
        if (!pushRes.data.success) {
          updateStep('push', 'error');
          throw new Error(pushRes.data.message);
        }
        updateStep('push', 'success');
        toast.success('✅ Successfully pushed to GitHub!');
      } catch (error) {
        updateStep('push', 'error');
        throw error;
      }
    } catch (error) {
      const errorMsg = error.response?.data?.message || error.message;
      toast.error(`Failed: ${errorMsg}`);
      console.error('Push workflow error:', error);
    } finally {
      setLoading(false);
    }
  };

  const getStepIcon = (status) => {
    if (status === 'loading') return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />;
    if (status === 'success') return <CheckCircle className="h-4 w-4 text-green-500" />;
    if (status === 'error') return <AlertCircle className="h-4 w-4 text-red-500" />;
    return <div className="h-4 w-4 rounded-full border-2 border-gray-400" />;
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent data-testid="github-dialog" className="bg-card border-border max-w-md">
        <DialogHeader>
          <DialogTitle className="font-mono text-primary flex items-center gap-2">
            <Github className="h-5 w-5" />
            Push to GitHub
          </DialogTitle>
          <DialogDescription className="text-muted-foreground">
            Commit and push your code to a GitHub repository
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div>
            <Label className="text-sm font-mono mb-2 block">Repository Name</Label>
            <Input
              data-testid="repo-path-input"
              value={repoPath}
              onChange={(e) => setRepoPath(e.target.value)}
              placeholder="my-code-project"
              className="bg-background border-border font-mono"
              disabled={loading}
            />
          </div>

          <div>
            <Label className="text-sm font-mono mb-2 block">Repository URL</Label>
            <Input
              data-testid="repo-url-input"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              placeholder="https://github.com/username/repo.git"
              className="bg-background border-border font-mono text-sm"
              disabled={loading}
            />
            <p className="text-xs text-muted-foreground mt-1">
              Format: https://github.com/username/repo.git
            </p>
          </div>

          <div>
            <Label className="text-sm font-mono mb-2 block">GitHub Personal Access Token</Label>
            <Input
              data-testid="github-token-input"
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="ghp_xxxxxxxxxxxx"
              className="bg-background border-border font-mono text-sm"
              disabled={loading}
            />
            <p className="text-xs text-muted-foreground mt-1">
              Create at: github.com/settings/tokens (select 'repo' scope)
            </p>
          </div>

          <div>
            <Label className="text-sm font-mono mb-2 block">Commit Message</Label>
            <Input
              data-testid="commit-message-input"
              value={commitMessage}
              onChange={(e) => setCommitMessage(e.target.value)}
              placeholder="Update code from Gen-AI IDE"
              className="bg-background border-border font-mono"
              disabled={loading}
            />
          </div>

          {/* Progress Steps */}
          {loading && (
            <div className="bg-secondary p-3 rounded-md space-y-2 border border-border">
              <div className="flex items-center gap-2">
                {getStepIcon(steps.init)}
                <span className="text-sm font-mono">Initialize Repository</span>
              </div>
              <div className="flex items-center gap-2">
                {getStepIcon(steps.commit)}
                <span className="text-sm font-mono">Commit Code</span>
              </div>
              <div className="flex items-center gap-2">
                {getStepIcon(steps.push)}
                <span className="text-sm font-mono">Push to GitHub</span>
              </div>
            </div>
          )}

          <div className="flex gap-2 pt-2">
            <Button
              data-testid="push-button"
              onClick={handlePushWorkflow}
              disabled={loading}
              className="flex-1 bg-primary hover:bg-primary/90"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Pushing...
                </>
              ) : (
                <>
                  <Upload className="h-4 w-4 mr-2" />
                  Push to GitHub
                </>
              )}
            </Button>

            <Button
              data-testid="cancel-button"
              onClick={onClose}
              disabled={loading}
              variant="outline"
            >
              Cancel
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default GitHubDialog;
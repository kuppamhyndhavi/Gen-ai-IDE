# 🚀 Deployment Guide: AI Code Editor

Deploying an AI application requires special consideration. While **Vercel** is incredible for React frontends, it places a strict **10-second timeout** on its free-tier Serverless backends. Since AI generation (Gemini/Ollama) often takes 10-30 seconds, Vercel would kill your AI requests halfway through.

To fix this, the industry standard is a **Split Deployment**:
1.  **Frontend (React)** -> Deploy to Vercel.
2.  **Backend (FastAPI)** -> Deploy to Render (or Railway/Heroku).

Here is exactly how to deploy your project:

---

## Part 1: Deploying the Backend (Render)

Render allows long-running Python processes perfect for our AI streaming.

1.  **Create a GitHub Repo**: Push your entire `app` folder to a new GitHub repository.
2.  **Sign up for [Render.com](https://render.com/)**: It has a great free tier.
3.  **Create a "New Web Service"**:
    *   Connect your GitHub account and select your repository.
    *   **Root Directory**: Set this to `backend`
    *   **Build Command**: `pip install -r requirements.txt`
    *   **Start Command**: `uvicorn server:app --host 0.0.0.0 --port 10000`
4.  **Environment Variables**: In the Render dashboard, add:
    *   `GEMINI_API_KEY`: `AIzaSy...`
    *   `AI_PROVIDER`: `gemini`
    *   `USE_OFFLINE_AI`: `false` (Since Ollama won't be on the cloud server)
5.  **Deploy**: Click "Create Web Service". Once it finishes, Render will give you a URL like `https://ai-ide-backend.onrender.com`. Save this!

---

## Part 2: Deploying the Frontend (Vercel)

Now we point your React frontend to your new live backend.

1.  **Sign up for [Vercel.com](https://vercel.com/)** and click **"Add New Project"**.
2.  **Import your GitHub Repo**.
3.  **Configure the Build**:
    *   **Root Directory**: Click "Edit" and select the `frontend` folder.
    *   Framework Preset should auto-detect as **Create React App**.
4.  **Environment Variables**:
    *   Add `REACT_APP_BACKEND_URL` and set the value to your new Render URL (e.g., `https://ai-ide-backend.onrender.com`).
5.  **Deploy**: Click deploy!

---

## Part 3: Fixing CORS (Crucial!)

Once Vercel gives you your frontend URL (e.g., `https://my-ai-editor.vercel.app`), your backend will block requests from it for security reasons until you whitelist it.

1.  Go back to your `.env` file or Render Environment Variables for the backend.
2.  Update your `CORS_ORIGINS` variable:
    *   `CORS_ORIGINS="https://my-ai-editor.vercel.app"`
3.  Redeploy/Restart your Render backend.

🎉 **Done!** Your app is now live on the internet!

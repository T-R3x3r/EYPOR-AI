# EYProject Setup Guide (2024)

This guide will help you set up the EYProject platform from scratch on a new PC. It covers all steps for Windows, with notes for Mac/Linux users. The guide assumes you have **no Python, Node.js, or dependencies installed**.

---

## What You Get from the Repo
- **All source code** (backend, frontend, docs)
- **Batch scripts** for easy setup and launch (Windows)
- **EY.env.example**: Template for required API keys
- **No API keys or secret credentials** (you must provide these)

---

## Prerequisites

### 1. Install Python (3.8+ recommended)
- Download from: https://www.python.org/downloads/
- During install, check **"Add Python to PATH"**
- Verify:
  ```bash
  python --version
  pip --version
  ```

### 2. Install Node.js (16+ recommended)
- Download from: https://nodejs.org/
- This includes npm (Node Package Manager)
- Verify:
  ```bash
  node --version
  npm --version
  ```

### 3. (Windows only) Install Git Bash or use PowerShell/Command Prompt
- Download Git Bash: https://gitforwindows.org/
- Mac/Linux: Use Terminal

---

## Clone the Repository

```bash
git clone <your-repo-url>
cd EYProjectGit
```

---

## Environment Variables

1. **Copy the example file:**
   ```bash
   cp EY.env.example EY.env
   # On Windows (cmd): copy EY.env.example EY.env
   ```
2. **Open `EY.env` in a text editor.**
   - Add your API keys (e.g., OpenAI, Gemini)
   - Example:
     ```
     OPENAI_API_KEY="sk-..."
     GEMINI_API_KEY="..."
     ```
3. **Never commit your real keys to git!**

---

## Install Backend Dependencies

1. **Create a virtual environment (recommended):**
   ```bash
   python -m venv .venv
   # Activate (Windows): .venv\Scripts\activate
   # Activate (Mac/Linux): source .venv/bin/activate
   ```
2. **Install Python packages:**
   ```bash
   cd backend
   pip install -r requirements.txt
   cd ..
   ```
- Or run the batch file (Windows):
  ```
  install_backend.bat
  ```

---

## Install Frontend Dependencies

1. **Navigate to the frontend directory:**
   ```bash
   cd frontend-new/eypor-electron
   npm install
   cd ../..
   ```
- Or run the batch file (Windows):
  ```
  install_frontend.bat
  ```

---

## Launch the Application (Recommended: Windows)

- **Use the unified launcher:**
  ```
  launch.bat
  ```
  - This will:
    - Stop any old servers
    - Start backend (FastAPI)
    - Start frontend (Angular)
    - Open your browser to http://localhost:4200

- **Manual launch (Mac/Linux or advanced users):**
  1. **Backend:**
     ```bash
     # (Activate your venv if used)
     cd backend
     python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
     ```
  2. **Frontend:**
     ```bash
     cd frontend-new/eypor-electron
     npm start
     ```
  3. **Access:**
     - Frontend: http://localhost:4200
     - Backend API: http://localhost:8001
     - API Docs: http://localhost:8001/docs

---

## Testing Your Setup

1. **Backend:** Visit http://localhost:8001/docs (should load FastAPI docs)
2. **Frontend:** Visit http://localhost:4200 (should load EYProject UI)
3. **Integration:**
   - Upload a file, run a query, use chat, test scenario switching

---

## Troubleshooting

- **Python/Node not found:**
  - Ensure both are installed and added to PATH
- **Port already in use:**
  - Backend: 8001, Frontend: 4200
  - Kill processes or change ports in scripts
- **Dependency errors:**
  - Backend: `pip install -r requirements.txt --force-reinstall`
  - Frontend: `rm -rf node_modules package-lock.json && npm install`
- **CORS errors:**
  - Ensure both servers are running and on correct ports
- **API key errors:**
  - Double-check `EY.env` and restart backend
- **Permissions:**
  - Run terminal as administrator if needed (Windows)
- **Mac/Linux:**
  - Use Terminal, adjust paths and activation commands as needed

---

## Development Workflow

- **Backend:** Edit files in `backend/`, server auto-reloads with `--reload`
- **Frontend:** Edit files in `frontend-new/eypor-electron/src/app/`, Angular auto-reloads
- **Add new features:**
  - Backend: Add endpoints in `backend/main.py`
  - Frontend: Add components/services in `frontend-new/eypor-electron/src/app/`

---

## Production Deployment

- **Backend:** Use a production ASGI server (e.g., Gunicorn)
- **Frontend:** Build with `npm run build` and serve static files
- **Set environment variables securely**
- **Configure CORS, HTTPS, and security headers**

---

## Support

- Check this guide and troubleshooting section
- Review error messages in terminal and browser console
- Ensure all dependencies are installed and servers are running
- If stuck, search for error messages or ask for help

---

The EYProject platform should now be fully functional with scenario management, file editing, chat, and advanced data analysis features. 
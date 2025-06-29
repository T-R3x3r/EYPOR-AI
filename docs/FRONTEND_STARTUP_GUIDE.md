# Frontend Startup Guide

This document explains how to install dependencies and launch the Angular single-page application that powers EYPOR-AI's user interface.

---

## Prerequisites
• Node.js 16 or newer (LTS recommended)  
• npm 8 or newer  
• Windows 10 / macOS / Linux  

> Tip: If you already use `nvm`, set the project to Node 16 with `nvm use 16`.

---

## One-Command Quick Start
Open a terminal at the project root:
```bash
# install dependencies & start the dev server
cd frontend && npm install && npm run start
```
When the compilation completes the app is served at <http://localhost:4200> and will hot-reload as you edit source files.

---

## Alternative Scripts (Windows)
The repository includes helper scripts that wrap the commands above:

| Script | Purpose |
|--------|---------|
| `install_frontend.bat` | Installs all npm dependencies. |
| `start_angular.bat` | Runs `ng serve` on port 4200. |

Double-click either file from Explorer or execute it in `PowerShell / CMD`.

---

## Common Options
```
ng serve --open           # automatically launch default browser
ng serve --port 4201      # run on a different port
ng serve --host 0.0.0.0   # expose to LAN / Docker
```

---

## Development Workflow
1. **Start backend** in a separate terminal: `cd backend && python main.py`  
2. **Start frontend** (instructions above).  
3. The app will reload when you modify any file under `frontend/src/`.

---

## Project Structure (Frontend)
```
frontend/
├── src/app/
│   ├── components/    # Angular components
│   ├── services/      # API client services
│   └── pipes/         # Custom pipes
├── angular.json       # Angular workspace config
├── package.json       # npm scripts & dependencies
└── tsconfig.json      # TypeScript compiler options
```

---

## Troubleshooting Cheatsheet
• **Port already in use** – run `ng serve --port 4201` or kill the blocking process.  
• **Out-of-date packages** – delete `node_modules` and run `npm install` again.  
• **Slow build** – ensure you're on Node 16+ and a fast disk (SSD).  

For further help consult the [Angular CLI docs](https://angular.io/cli) or open a GitHub issue.

---

_Last updated 2025-06-29_

@echo off
setlocal enabledelayedexpansion

echo.
echo ========================================
echo  EY Project - Complete Website Launcher
echo ========================================
echo.

:: Check if we're in the right directory
if not exist "backend" (
    echo ERROR: backend directory not found!
    echo Please run this script from the EY Project root directory
    pause
    exit /b 1
)

if not exist "frontend" (
    echo ERROR: frontend directory not found!
    echo Please run this script from the EY Project root directory
    pause
    exit /b 1
)

:: Check virtual environment
if not exist ".venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found!
    echo Please run install_backend.bat first
    pause
    exit /b 1
)

echo [1/4] Stopping any existing instances...

:: Kill any existing backend processes (port 8001)
for /f "tokens=5" %%i in ('netstat -ano 2^>nul ^| findstr ":8001"') do (
    echo Stopping backend process %%i
    taskkill /pid %%i /f >nul 2>&1
)

:: Kill any existing frontend processes (port 4200)
for /f "tokens=5" %%i in ('netstat -ano 2^>nul ^| findstr ":4200"') do (
    echo Stopping frontend process %%i
    taskkill /pid %%i /f >nul 2>&1
)

:: Kill any lingering Node.js and Python processes related to our app
taskkill /f /im "node.exe" >nul 2>&1
taskkill /f /im "python.exe" >nul 2>&1

echo Waiting for cleanup...
timeout /t 3 /nobreak >nul

echo [2/4] Starting backend server...

:: Activate virtual environment and start backend
call .venv\Scripts\activate.bat
start "EY Backend" cmd /k "cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8001"

echo Waiting for backend to initialize...
timeout /t 8 /nobreak >nul

:: Verify backend is running
netstat -ano | findstr ":8001" >nul
if !errorlevel! neq 0 (
    echo WARNING: Backend may not have started properly
    echo Check the backend window for errors
) else (
    echo OK - Backend is running on port 8001
)

echo [3/4] Starting frontend server...

:: Set Node.js options for compatibility
set NODE_OPTIONS=--openssl-legacy-provider --no-deprecation

:: Start frontend
start "EY Frontend" cmd /k "cd frontend && ng serve --host 0.0.0.0 --port 4200 --open"

echo Waiting for frontend to initialize...
timeout /t 10 /nobreak >nul

:: Verify frontend is running
netstat -ano | findstr ":4200" >nul
if !errorlevel! neq 0 (
    echo WARNING: Frontend may not have started properly
) else (
    echo OK - Frontend is running on port 4200
)

echo [4/4] Opening application...

:: Wait a bit more then open browser if it hasn't opened automatically
timeout /t 3 /nobreak >nul
start http://localhost:4200

echo.
echo ========================================
echo  EY Project Successfully Launched!
echo ========================================
echo.
echo Frontend: http://localhost:4200
echo Backend:  http://localhost:8001
echo API Docs: http://localhost:8001/docs
echo.
echo Both servers are running in separate windows.
echo To stop everything, simply close both server windows
echo or run this script again (it will restart everything).
echo.
echo Press any key to close this launcher window...
pause >nul 
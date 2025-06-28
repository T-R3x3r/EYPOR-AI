@echo off
echo ============================================
echo  Starting Angular Frontend with Node 22.x
echo ============================================
echo.

:: Kill any existing processes on port 4200
echo Clearing port 4200...
for /f "tokens=5" %%i in ('netstat -ano ^| findstr ":4200"') do (
    taskkill /pid %%i /f >nul 2>&1
)

:: Set multiple compatibility options for Node.js 22.x with Angular 16
echo Setting Node.js compatibility options for Angular 16...
set NODE_OPTIONS=--openssl-legacy-provider --no-deprecation --no-warnings
set NODE_NO_WARNINGS=1

:: Additional environment variables that may help
set FORCE_COLOR=0
set NO_UPDATE_NOTIFIER=1

echo Current Node.js version:
node --version

echo Current directory:
cd

:: Try multiple startup methods in order of preference

echo.
echo Attempting Method 1: Standard ng serve with compatibility...
ng serve --port 4200 --host 0.0.0.0 --disable-host-check --verbose >nul 2>&1 &
timeout /t 10 >nul

:: Check if it worked
netstat -ano | findstr ":4200" >nul
if %errorlevel% equ 0 (
    echo SUCCESS: Angular dev server is running on port 4200!
    echo Open http://localhost:4200 in your browser
    goto :end
)

echo Method 1 failed, trying Method 2: npm start...
taskkill /f /im node.exe >nul 2>&1
npm start >nul 2>&1 &
timeout /t 15 >nul

netstat -ano | findstr ":4200" >nul
if %errorlevel% equ 0 (
    echo SUCCESS: Angular dev server is running via npm start!
    echo Open http://localhost:4200 in your browser
    goto :end
)

echo Method 2 failed, trying Method 3: npx with explicit options...
taskkill /f /im node.exe >nul 2>&1
npx ng serve --port 4200 --host 0.0.0.0 --disable-host-check --poll=2000 >nul 2>&1 &
timeout /t 15 >nul

netstat -ano | findstr ":4200" >nul
if %errorlevel% equ 0 (
    echo SUCCESS: Angular dev server is running via npx!
    echo Open http://localhost:4200 in your browser
    goto :end
)

echo.
echo ============================================
echo  All automatic methods failed
echo ============================================
echo.
echo This is likely due to Node.js 22.x compatibility issues with Angular 16.
echo.
echo MANUAL SOLUTIONS:
echo.
echo Option 1 - Update Angular (Recommended):
echo   npm install -g @angular/cli@latest
echo   ng update @angular/core @angular/cli
echo.
echo Option 2 - Use compatible Node.js version:
echo   Install Node.js 18.x from https://nodejs.org/
echo.
echo Option 3 - Force start with warnings (may work):
echo   set NODE_OPTIONS=--openssl-legacy-provider --no-deprecation
echo   ng serve --port 4200 --host 0.0.0.0 --disable-host-check
echo.
echo Option 4 - Try development build:
echo   npm run build
echo   npx http-server dist/ -p 4200 -c-1
echo.

:end
pause 
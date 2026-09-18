@echo off
setlocal EnableExtensions

REM Unified Voice Assistant launcher
REM Starts FastAPI on http://localhost:8000 and Angular on http://localhost:4200

set "PROJECT_ROOT=%~dp0"
set "BACKEND_DIR=%PROJECT_ROOT%backend"
set "FRONTEND_DIR=%PROJECT_ROOT%frontend"
set "VENV_DIR=%BACKEND_DIR%\.venv"

 title Unified Voice Assistant Launcher
 echo.
 echo ================================================
 echo       Unified Voice Assistant Launcher
 echo ================================================
 echo.

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python was not found on PATH.
    echo Install Python 3.11 or newer and try again.
    pause
    exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
    echo ERROR: npm was not found on PATH.
    echo Install Node.js 20 or newer and try again.
    pause
    exit /b 1
)

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo Creating backend virtual environment...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo ERROR: Could not create the Python virtual environment.
        pause
        exit /b 1
    )
)

echo Checking backend dependencies...
"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip
"%VENV_DIR%\Scripts\python.exe" -m pip install -r "%BACKEND_DIR%\requirements.txt"
if errorlevel 1 (
    echo ERROR: Backend dependency installation failed.
    pause
    exit /b 1
)

echo Validating backend dependencies...
pushd "%BACKEND_DIR%"
"%VENV_DIR%\Scripts\python.exe" -m pip check
if errorlevel 1 (
    echo ERROR: Backend dependency validation failed.
    popd
    pause
    exit /b 1
)
"%VENV_DIR%\Scripts\python.exe" -c "import msal, fastapi, uvicorn; import app.main; print('Backend dependencies: OK')"
if errorlevel 1 (
    echo ERROR: Backend imports failed. Ensure requirements.txt installed successfully.
    popd
    pause
    exit /b 1
)
popd

if not exist "%FRONTEND_DIR%\node_modules" (
    echo Installing frontend dependencies...
    pushd "%FRONTEND_DIR%"
    call npm install
    if errorlevel 1 (
        popd
        echo ERROR: Frontend dependency installation failed.
        pause
        exit /b 1
    )
    popd
)

echo Starting FastAPI backend...
start "Unified Assistant - Backend" cmd /k "cd /d "%BACKEND_DIR%" && "%VENV_DIR%\Scripts\python.exe" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

 timeout /t 2 /nobreak >nul

echo Starting Angular frontend...
start "Unified Assistant - Frontend" cmd /k "cd /d "%FRONTEND_DIR%" && call npm start"

echo.
echo Application started.
echo Backend:  http://localhost:8000
 echo API docs: http://localhost:8000/docs
 echo Frontend: http://localhost:4200
 echo.
echo Close the two opened terminal windows to stop the application.
 timeout /t 5 /nobreak >nul
endlocal

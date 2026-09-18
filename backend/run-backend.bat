@echo off
setlocal EnableExtensions

REM Always run the backend with this project's virtual environment.
set "BACKEND_DIR=%~dp0"
set "PYTHON_EXE=%BACKEND_DIR%.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo ERROR: The backend virtual environment was not found:
    echo        %PYTHON_EXE%
    echo Create it with: python -m venv .venv
    pause
    exit /b 1
)

pushd "%BACKEND_DIR%"
echo Installing and validating backend dependencies...
"%PYTHON_EXE%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Backend dependency installation failed.
    popd
    pause
    exit /b 1
)

"%PYTHON_EXE%" -m pip check
if errorlevel 1 (
    echo ERROR: Backend dependency validation failed.
    popd
    pause
    exit /b 1
)

"%PYTHON_EXE%" -c "import msal, fastapi, uvicorn; import app.main; print('Backend dependencies: OK')"
if errorlevel 1 (
    echo ERROR: Backend imports failed.
    popd
    pause
    exit /b 1
)

echo Starting FastAPI backend with the project virtual environment...
"%PYTHON_EXE%" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
set "EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %EXIT_CODE%
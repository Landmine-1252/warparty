@echo off
setlocal
cd /d "%~dp0.."

if not exist data mkdir data
set UV_PROJECT_ENVIRONMENT=.venv-win
if not exist "%UV_PROJECT_ENVIRONMENT%\Scripts\python.exe" (
  uv venv "%UV_PROJECT_ENVIRONMENT%" --python 3.12
  if errorlevel 1 exit /b %errorlevel%
) else (
  echo Reusing existing %UV_PROJECT_ENVIRONMENT%.
)
uv sync --extra dev
if errorlevel 1 exit /b %errorlevel%

if not defined WARPARTY_PUBLIC_BASE_URL set WARPARTY_PUBLIC_BASE_URL=http://localhost:8080
if not defined WARPARTY_PORT set WARPARTY_PORT=8080

echo Starting Warparty dev server at http://localhost:%WARPARTY_PORT%
echo Press Ctrl+C to stop.
uv run --extra dev uvicorn app.main:app --host 127.0.0.1 --port %WARPARTY_PORT% --reload
endlocal

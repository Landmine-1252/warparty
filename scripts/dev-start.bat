@echo off
setlocal
cd /d "%~dp0.."

if not exist App_Data mkdir App_Data
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
if not defined WARPARTY_DATA_DIR set WARPARTY_DATA_DIR=.\App_Data
if not defined WARPARTY_DATABASE_PATH set WARPARTY_DATABASE_PATH=.\App_Data\warparty.db
if not defined WARPARTY_SECRET_KEY set WARPARTY_SECRET_KEY=local-dev-secret
if not defined WARPARTY_PORT set WARPARTY_PORT=8080

echo Starting Warparty dev server at http://localhost:%WARPARTY_PORT%
echo Press Ctrl+C to stop.
uv run --extra dev uvicorn app.main:app --host 127.0.0.1 --port %WARPARTY_PORT% --reload
endlocal

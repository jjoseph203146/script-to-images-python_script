@echo off
rem One-click launcher for the script_to_images web UI.
rem Double-click this file (or a shortcut to it) instead of typing cmd commands.

cd /d "%~dp0"

if not exist .env (
    echo No .env file found yet -- creating one from .env.example.
    copy .env.example .env >nul
    echo.
    echo Opening .env in Notepad. Paste your GEMINI_API_KEY in, save, and close it.
    echo Then re-run this file.
    notepad .env
    exit /b
)

echo Starting script_to_images web UI...
start "script_to_images" cmd /k python app.py
timeout /t 3 /nobreak >nul
start "" http://127.0.0.1:5000

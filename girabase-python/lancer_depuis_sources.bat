@echo off
rem Lance Girabase sans construire l'executable (necessite Python et les dependances).
cd /d "%~dp0"
if exist .venv\Scripts\pythonw.exe (
    start "" .venv\Scripts\pythonw.exe lancer_girabase.py %*
) else (
    python -m pip install -r requirements.txt
    start "" pythonw lancer_girabase.py %*
)

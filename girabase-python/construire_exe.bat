@echo off
rem ===========================================================================
rem  Construction de Girabase.exe (Windows 10/11, Python 3.12 requis)
rem  Python peut etre installe sans droits administrateur depuis python.org
rem  (cocher "Add python.exe to PATH", installation "pour l'utilisateur").
rem  Resultat : dist\Girabase.exe, dist\girabase-mcp.exe, dist\girabase.mcpb,
rem             dist\Girabase\Girabase.exe et dist\Girabase-Windows.zip
rem ===========================================================================
setlocal
cd /d "%~dp0"

set PY=python
where py >nul 2>nul
if %errorlevel%==0 (
    py -3.12 -c "pass" >nul 2>nul && set "PY=py -3.12"
)

echo [1/4] Creation de l'environnement Python local (.venv)...
if not exist .venv (
    %PY% -m venv .venv || goto :erreur
)
call .venv\Scripts\activate.bat || goto :erreur

echo [2/4] Installation des dependances...
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt -r requirements-dev.txt || goto :erreur

echo [3/4] Verification du moteur de calcul (tests)...
python -m pytest -q || goto :erreur

echo [4/4] Construction de l'executable (version dossier puis fichier unique)...
pyinstaller --noconfirm --clean girabase.spec || goto :erreur
pyinstaller --noconfirm girabase_fichier_unique.spec || goto :erreur
pyinstaller --noconfirm girabase_mcp.spec || goto :erreur
python outils\creer_mcpb.py dist\girabase-mcp.exe dist\girabase.mcpb || goto :erreur

powershell -NoProfile -Command "Compress-Archive -Path 'dist\Girabase' -DestinationPath 'dist\Girabase-Windows.zip' -Force"

echo.
echo Termine :
echo   dist\Girabase.exe              (fichier unique)
echo   dist\girabase-mcp.exe          (serveur MCP pour les assistants d'IA)
echo   dist\girabase.mcpb             (extension Claude Desktop, double-clic)
echo   dist\Girabase\Girabase.exe     (version dossier, demarrage plus rapide)
echo   dist\Girabase-Windows.zip      (version dossier compressee)
pause
exit /b 0

:erreur
echo.
echo *** La construction a echoue. Voir les messages ci-dessus. ***
pause
exit /b 1

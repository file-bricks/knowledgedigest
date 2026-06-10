@echo off
cd /d "%~dp0"

:: Ordnerstruktur sicherstellen
if not exist "data" mkdir data
if not exist "data\inbox" mkdir data\inbox
if not exist "data\archive" mkdir data\archive

:: Python pruefen
python --version >nul 2>&1
if errorlevel 1 (
    echo [FEHLER] Python nicht gefunden!
    echo Bitte Python 3.10+ installieren: https://python.org
    pause
    exit /b 1
)

:: GUI starten
cd ..
echo Starte KnowledgeDigest GUI...
python -m KnowledgeDigest --gui
if errorlevel 1 pause

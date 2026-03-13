@echo off
echo ============================================
echo  WhisperLiveKit + LLM Translation Setup
echo ============================================
echo.

:: Check Python exists
python --version 2>nul
if errorlevel 1 (
    echo [FAIL] Python not found. Install Python 3.11+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Run pre-install system check
echo Running system check...
echo.
python precheck.py
if errorlevel 1 (
    echo.
    echo Setup aborted due to system check failure.
    echo Fix the issues above and run this script again.
    pause
    exit /b 1
)

:: Ask user to continue
echo.
set /p CONTINUE="System check passed. Continue with installation? (Y/n): "
if /i "%CONTINUE%"=="n" (
    echo Setup cancelled.
    pause
    exit /b 0
)

:: Create virtual environment if not exists
if not exist "venv" (
    echo.
    echo Creating virtual environment...
    python -m venv venv
)

:: Activate venv
call venv\Scripts\activate.bat

:: Install dependencies
echo.
echo [1/4] Installing WhisperLiveKit (CPU mode)...
pip install -e ".[cpu]"
if errorlevel 1 (
    echo [FAIL] WhisperLiveKit installation failed.
    pause
    exit /b 1
)

echo.
echo [2/4] Installing OpenAI SDK (for ProxyPal)...
pip install openai
if errorlevel 1 (
    echo [FAIL] OpenAI SDK installation failed.
    pause
    exit /b 1
)

echo.
echo [3/4] Installing Anthropic SDK (optional, for Claude translation)...
pip install anthropic 2>nul || echo [WARN] Skipped (optional)

echo.
echo [4/4] Installing Google GenAI SDK (optional, for Gemini translation)...
pip install google-generativeai 2>nul || echo [WARN] Skipped (optional)

:: Post-install verification
echo.
echo ============================================
echo  Verifying installation...
echo ============================================
echo.
call venv\Scripts\python precheck.py --pre-run
if errorlevel 1 (
    echo.
    echo [WARN] Some post-install checks failed. See above.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Setup complete!
echo ============================================
echo.
echo To start the server, run:
echo   run_translate.bat
echo.
pause

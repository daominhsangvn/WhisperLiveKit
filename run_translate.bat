@echo off
echo ============================================
echo  WhisperLiveKit + Live Translation
echo  English -> Vietnamese
echo ============================================
echo.

:: Check venv exists
if not exist "venv\Scripts\activate.bat" (
    echo [FAIL] Virtual environment not found. Run setup_and_run.bat first.
    pause
    exit /b 1
)

:: Activate venv
call venv\Scripts\activate.bat

:: Run pre-run check
echo Running pre-run check...
echo.
python precheck.py --pre-run
if errorlevel 1 (
    echo.
    echo Cannot start server. Fix the issues above first.
    pause
    exit /b 1
)

echo.
echo Starting server... Open http://localhost:8000 in your browser
echo.

python translate_server.py ^
    --model small ^
    --language en ^
    --pcm-input ^
    --min-chunk-size 1 ^
    --translator openai ^
    --llm-base-url http://localhost:8317/v1 ^
    --llm-api-key proxypal-local ^
    --llm-model gemini-2.5-flash ^
    --source-lang English ^
    --target-lang Vietnamese

pause

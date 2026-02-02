@echo off
title Chronex
color 0B

echo.
echo ========================================
echo       CHRONEX - Productivity App
echo ========================================
echo.

:: Check Python
echo Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo Python not found!
    echo.
    echo Download from: https://www.python.org/downloads/
    echo Make sure to tick "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo Found %%i

:: Check dependencies
echo.
echo Checking dependencies...
python -c "import flask" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing required packages...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo.
        echo Install failed. Try: pip install -r requirements.txt
        pause
        exit /b 1
    )
    echo Done.
) else (
    echo All good.
)

:: Run app
echo.
echo Starting server...
echo.
echo ----------------------------------------
echo  Demo login:  artur / 123
echo  Open:        http://localhost:5000
echo ----------------------------------------
echo.

python app.py

echo.
pause

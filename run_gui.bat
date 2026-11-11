@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "EXE_FILE=%~dp0图书整理工具.exe"
if exist "%EXE_FILE%" (
    start "" "%EXE_FILE%"
    exit /b 0
)

set "PYTHON_EXE=C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%PYTHON_EXE%" (
    start "" "%PYTHON_EXE%" "%~dp0gui.py"
    exit /b 0
)

where python >nul 2>nul
if %errorlevel% equ 0 (
    start "" python "%~dp0gui.py"
    exit /b 0
)

echo [错误] 未找到可执行程序或 Python 环境！
pause

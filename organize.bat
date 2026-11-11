@echo off
chcp 65001 >nul
title 智能图书整理工具 (双轨元数据引擎增强版)

cd /d "%~dp0"

set "PYTHON_EXE=C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
set "EXE_FILE=%~dp0图书整理工具.exe"

if exist "%PYTHON_EXE%" (
    set "RUNNER=%PYTHON_EXE% "%~dp0book_organizer.py""
    set "GUI_RUNNER=start \"\" \"%PYTHON_EXE%\" \"%~dp0gui.py\""
) else if exist "%EXE_FILE%" (
    set "RUNNER=%EXE_FILE%"
    set "GUI_RUNNER=start \"\" \"%EXE_FILE%\""
) else (
    where python >nul 2>nul
    if %errorlevel% equ 0 (
        set "RUNNER=python "%~dp0book_organizer.py""
        set "GUI_RUNNER=start \"\" python "%~dp0gui.py""
    ) else (
        echo [错误] 未找到可执行程序或 Python 执行环境！
        pause
        exit /b 1
    )
)

echo =================================================================
echo        智能图书整理工具 (双轨元数据引擎: 内置多源 + Calibre插件)
echo =================================================================
echo [1] 默认整理 (复制模式: G:\123 -^> 魏总的书库(已整理)(1))
echo [2] 预演分析 (Dry-Run: 仅扫描分析并输出报告，不写入或移动文件)
echo [3] 移动整理 (移动模式: 整理后移除源文件)
echo [4] 自定义参数运行
echo [5] 启动现代化桌面图形界面 (GUI 书架与可视化整理)
echo [0] 退出
echo =================================================================
set /p opt="请选择运行模式 [0-5] (默认 1): "

if "%opt%"=="" set opt=1

if "%opt%"=="0" exit /b 0

if "%opt%"=="5" (
    %GUI_RUNNER%
    exit /b 0
)

if "%opt%"=="1" (
    %RUNNER% --action copy
) else if "%opt%"=="2" (
    %RUNNER% --dry-run
) else if "%opt%"=="3" (
    echo.
    echo [警告] 移动模式将移动源文件，建议首次先使用复制模式。
    set /p confirm="确认使用移动模式吗？(Y/N): "
    if /i "%confirm%"=="Y" (
        %RUNNER% --action move
    ) else (
        echo 已取消。
    )
) else if "%opt%"=="4" (
    echo.
    set /p custom_src="请输入源文件夹路径 (直接回车使用 G:\123): "
    set /p custom_dst="请输入目标书库路径 (直接回车使用默认目标): "
    set "EXTRA_ARGS="
    if not "%custom_src%"=="" set EXTRA_ARGS=%EXTRA_ARGS% --src "%custom_src%"
    if not "%custom_dst%"=="" set EXTRA_ARGS=%EXTRA_ARGS% --dst "%custom_dst%"
    %RUNNER% %EXTRA_ARGS%
)

echo.
echo 整理程序执行完毕。
pause

@echo off
chcp 65001 >nul
title 发布镜像到 Docker Hub

echo ============================================================
echo        📚 智能图书整理系统 - Docker Hub 镜像构建与发布
echo ============================================================
echo.

where docker >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 本地未检测到 Docker 环境！
    echo 请先安装并启动 Docker Desktop (https://www.docker.com/products/docker-desktop/)，
    echo 或者将本工程上传到已安装 Docker 的服务器/NAS 上执行 push_to_dockerhub.sh。
    echo.
    pause
    exit /b 1
)

echo 当前 Docker 运行正常。
echo.
set /p DOCKER_USER="请输入您的 Docker Hub 用户名 (Username): "
if "%DOCKER_USER%"=="" (
    echo [错误] 用户名不能为空！
    pause
    exit /b 1
)

set "IMAGE_NAME=%DOCKER_USER%/book-organizer"
set "TAG=latest"

echo.
echo 即将发布的镜像名称: %IMAGE_NAME%:%TAG%
echo.

echo [1/3] 正在登录 Docker Hub...
docker login
if %errorlevel% neq 0 (
    echo [错误] 登录失败，请检查账号密码或 Access Token！
    pause
    exit /b 1
)

echo.
echo [2/3] 正在构建 Docker 镜像 (%IMAGE_NAME%:%TAG%)...
docker build -t %IMAGE_NAME%:%TAG% -t %IMAGE_NAME%:v1.0.0 .
if %errorlevel% neq 0 (
    echo [错误] 镜像构建失败！
    pause
    exit /b 1
)

echo.
echo [3/3] 正在推送镜像到 Docker Hub (这可能需要几分钟)...
docker push %IMAGE_NAME%:%TAG%
docker push %IMAGE_NAME%:v1.0.0
if %errorlevel% neq 0 (
    echo [错误] 推送失败！
    pause
    exit /b 1
)

echo.
echo ============================================================
echo [成功] 镜像已成功发布至 Docker Hub！
echo 镜像拉取地址: %IMAGE_NAME%:latest
echo 任何人现在都可以通过以下命令直接运行:
echo.
echo docker run -d -p 14808:14808 -v /path/to/books:/source -v /path/to/library:/library %IMAGE_NAME%:latest
echo ============================================================
echo.
pause

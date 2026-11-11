#!/bin/bash
set -e

echo "============================================================"
echo "       📚 智能图书整理系统 - Docker Hub 镜像发布脚本"
echo "============================================================"
echo ""

if ! command -v docker &> /dev/null; then
    echo "[错误] 未检测到 docker 命令，请先安装 Docker！"
    exit 1
fi

read -p "请输入您的 Docker Hub 用户名 (Username): " DOCKER_USER
if [ -z "$DOCKER_USER" ]; then
    echo "[错误] 用户名不能为空！"
    exit 1
fi

IMAGE_NAME="${DOCKER_USER}/book-organizer"
TAG="latest"

echo ""
echo "即将发布的镜像名称: ${IMAGE_NAME}:${TAG}"
echo ""

echo "[1/3] 正在登录 Docker Hub..."
docker login

echo ""
read -p "是否启用多架构构建 (支持 amd64 + arm64，兼容NAS与树莓派)? (y/n, 默认 y): " MULTI_ARCH
MULTI_ARCH=${MULTI_ARCH:-y}

if [ "$MULTI_ARCH" = "y" ] || [ "$MULTI_ARCH" = "Y" ]; then
    echo "[2/3] 使用 Docker Buildx 构建并推送多架构镜像 (linux/amd64, linux/arm64)..."
    docker buildx create --name mybuilder --use 2>/dev/null || docker buildx use mybuilder
    docker buildx build --platform linux/amd64,linux/arm64         -t ${IMAGE_NAME}:${TAG}         -t ${IMAGE_NAME}:v1.0.0         --push .
else
    echo "[2/3] 构建本地架构镜像..."
    docker build -t ${IMAGE_NAME}:${TAG} -t ${IMAGE_NAME}:v1.0.0 .
    echo "[3/3] 推送镜像到 Docker Hub..."
    docker push ${IMAGE_NAME}:${TAG}
    docker push ${IMAGE_NAME}:v1.0.0
fi

echo ""
echo "============================================================"
echo "[成功] 镜像已成功发布至 Docker Hub: ${IMAGE_NAME}:${TAG}"
echo "任何人均可通过以下命令一键运行:"
echo ""
echo "docker run -d -p 14808:14808 -v /path/to/books:/source -v /path/to/library:/library ${IMAGE_NAME}:${TAG}"
echo "============================================================"

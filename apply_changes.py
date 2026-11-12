#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import re

print("🚀 正在修复 Dockerfile 与自包含 All-in-One 架构...")

# -------------------------------------------------------------
# 1. 修复 Dockerfile (彻底移除不存在的 ghcr.io 外部镜像)
# -------------------------------------------------------------
dockerfile_content = """# -------------------------------------------------------------
# Dockerfile for Book Organizer All-in-One (内置 PostgreSQL + 规范化书库与阅读器)
# -------------------------------------------------------------
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \\
    PYTHONDONTWRITEBYTECODE=1 \\
    LANG=C.UTF-8 \\
    LC_ALL=C.UTF-8 \\
    PORT=14808 \\
    PGHOST=127.0.0.1 \\
    PGPORT=5432 \\
    PGUSER=bookuser \\
    PGPASSWORD=bookpass123 \\
    PGDATABASE=book_library

# 安装系统运行依赖、中文字体、curl 以及内置 PostgreSQL
RUN apt-get update && apt-get install -y --no-install-recommends \\
    fonts-wqy-microhei \\
    fonts-wqy-zenhei \\
    libxml2 \\
    libxslt1.1 \\
    tzdata \\
    ca-certificates \\
    curl \\
    procps \\
    postgresql \\
    postgresql-contrib \\
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制全部应用源码与静态资源
COPY . /app/

RUN chmod +x /app/entrypoint.sh

VOLUME ["/source", "/library", "/config"]
EXPOSE 14808

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["web"]
"""
with open("Dockerfile", "w", encoding="utf-8") as f:
    f.write(dockerfile_content)
print("  [1/4] ✅ Dockerfile 修复完成 (移除失效外部镜像依赖)")

# -------------------------------------------------------------
# 2. 确保 requirements.txt 正确
# -------------------------------------------------------------
req_content = """lxml>=4.9.0
pillow>=9.0.0
flask>=2.3.0
psycopg2-binary>=2.9.9
"""
with open("requirements.txt", "w", encoding="utf-8") as f:
    f.write(req_content)
print("  [2/4] ✅ requirements.txt 配置完成")

# -------------------------------------------------------------
# 3. 确保 entrypoint.sh 为 Linux LF 换行格式
# -------------------------------------------------------------
entrypoint_content = """#!/bin/bash
set -e

CONFIG_DIR="/config"
mkdir -p "$CONFIG_DIR"
SETTINGS_FILE="$CONFIG_DIR/settings.json"

if [ ! -f "$SETTINGS_FILE" ]; then
    cat <<EOF > "$SETTINGS_FILE"
{
  "src": "/source",
  "dst": "/library",
  "bookshelf_dir": "/library",
  "active_tab": 0,
  "action": "copy",
  "skip_collections": true,
  "limit": "",
  "delay": "1.2",
  "google_key": "",
  "threads": "4"
}
EOF
fi

ln -sf "$SETTINGS_FILE" /app/settings.json 2>/dev/null || true

# 初始化并启动内置 PostgreSQL
PGDATA="/config/pgdata"
mkdir -p "$PGDATA"
chown -R postgres:postgres "$PGDATA"
chmod 700 "$PGDATA"

PG_BIN=$(ls -d /usr/lib/postgresql/*/bin 2>/dev/null | head -n 1)

if [ ! -s "$PGDATA/PG_VERSION" ]; then
    echo "📦 [PostgreSQL] 首次启动，正在 /config/pgdata 中初始化数据库集群..."
    su - postgres -c "$PG_BIN/initdb -D '$PGDATA' --encoding=UTF8 --locale=C.UTF-8"
fi

echo "🚀 [PostgreSQL] 启动内置数据库服务..."
su - postgres -c "$PG_BIN/pg_ctl -D '$PGDATA' -l /config/postgres.log -w start"

su - postgres -c "psql -tc \\"SELECT 1 FROM pg_database WHERE datname = 'book_library'\\" | grep -q 1 || psql -c \\"CREATE USER bookuser WITH PASSWORD 'bookpass123'; CREATE DATABASE book_library OWNER bookuser;\\""

cleanup() {
    echo "🛑 [PostgreSQL] 优雅关闭内置数据库..."
    su - postgres -c "$PG_BIN/pg_ctl -D '$PGDATA' -m fast stop" || true
    exit 0
}
trap cleanup SIGTERM SIGINT

if [ "$1" = "web" ] || [ -z "$1" ]; then
    echo "=========================================================="
    echo "  📚 智能图书整理系统 All-in-One (内置PG + 现代书架启动)"
    echo "  Web 地址:    http://0.0.0.0:${PORT:-14808}"
    echo "  数据持久化:  /config/pgdata"
    echo "=========================================================="
    exec python /app/web_app.py
elif [ "$1" = "organize" ]; then
    shift
    exec python /app/book_organizer.py --src /source --dst /library "$@"
elif [ "$1" = "dry-run" ]; then
    shift
    exec python /app/book_organizer.py --src /source --dst /library --dry-run "$@"
else
    exec "$@"
fi
"""
with open("entrypoint.sh", "w", encoding="utf-8", newline="\n") as f:
    f.write(entrypoint_content)
print("  [3/4] ✅ entrypoint.sh 换行与权限格式优化完成")

# -------------------------------------------------------------
# 4. 确保 docker-compose.yml 极简单容器
# -------------------------------------------------------------
compose_content = """version: '3.8'

services:
  book-organizer:
    image: arros/book-organizer:latest
    container_name: book-organizer
    restart: unless-stopped
    ports:
      - "14808:14808"
    volumes:
      - /path/to/source:/source
      - /path/to/library:/library
      - ./config:/config
"""
with open("docker-compose.yml", "w", encoding="utf-8") as f:
    f.write(compose_content)
print("  [4/4] ✅ docker-compose.yml 单容器配置完成")

print("\\n🎉 修复完成！现在可以重新推送并构建镜像！")
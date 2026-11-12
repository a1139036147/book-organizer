#!/bin/bash
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

su - postgres -c "psql -tc \"SELECT 1 FROM pg_database WHERE datname = 'book_library'\" | grep -q 1 || psql -c \"CREATE USER bookuser WITH PASSWORD 'bookpass123'; CREATE DATABASE book_library OWNER bookuser;\""

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

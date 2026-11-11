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
  "google_key": ""
}
EOF
fi

ln -sf "$SETTINGS_FILE" /app/settings.json 2>/dev/null || true

if [ "$1" = "web" ] || [ -z "$1" ]; then
    echo "=========================================================="
    echo "  📚 智能图书整理与现代视觉书架系统 (Docker Web版启动)"
    echo "  Web 访问地址: http://0.0.0.0:${PORT:-14808}"
    echo "  待整理目录:   /source"
    echo "  已整理书库:   /library"
    echo "  配置存储:     /config"
    echo "=========================================================="
    exec python /app/web_app.py
elif [ "$1" = "organize" ]; then
    shift
    echo "=========================================================="
    echo "  ⚙️ 执行命令行批量图书整理..."
    echo "=========================================================="
    exec python /app/book_organizer.py --src /source --dst /library "$@"
elif [ "$1" = "dry-run" ]; then
    shift
    echo "=========================================================="
    echo "  🔍 执行命令行预演测试 (Dry-Run)..."
    echo "=========================================================="
    exec python /app/book_organizer.py --src /source --dst /library --dry-run "$@"
else
    exec "$@"
fi

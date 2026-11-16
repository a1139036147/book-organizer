from plugins_manager import SOURCES, plugin_manager

from version import APP_VERSION, BUILD_DATE, FEATURES
# -*- coding: utf-8 -*-
"""
Book Organizer & Bookshelf - Web Application for Docker & Browser
提供：
1. RESTful API 服务 (书架扫描、封面生成、正文阅读试读、下载、元数据编辑与删除)
2. 异步后台整理任务引擎 (日志流、实时进度、5维统计卡片、自动同步)
3. 现代化 Z-Library 风格单页应用 (海报流画廊、在线阅读器、响应式设计)
"""
import os
import sys
import json
import time
import queue
import threading
import mimetypes
import math
from hashlib import sha256
import urllib.parse
from io import BytesIO
from flask import Flask, abort, request, jsonify, send_file, send_from_directory, Response, render_template, render_template_string, url_for

# 确保项目根目录在模块搜索路径中
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import config
import bookshelf_manager
import book_organizer
import hot_update

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

# 默认设置文件路径（支持 Docker /config 挂载）
def get_settings_path():
    if os.path.isdir('/config'):
        return '/config/settings.json'
    return os.path.join(APP_DIR, 'settings.json')

def load_settings():
    p = get_settings_path()
    if os.path.exists(p):
        try:
            with open(p, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "src": "/source" if os.path.exists("/source") else config.DEFAULT_SRC_DIR,
        "dst": "/library" if os.path.exists("/library") else config.DEFAULT_DST_DIR,
        "bookshelf_dir": "/library" if os.path.exists("/library") else config.DEFAULT_DST_DIR,
        "active_tab": 0,
        "action": "copy",
        "skip_collections": True,
        "limit": "",
        "delay": "1.2",
        "google_key": "",
        "threads": 4
    }

def save_settings(data):
    p = get_settings_path()
    try:
        os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

# 全局任务状态管理
class TaskManager:
    def __init__(self):
        self.is_running = False
        self.start_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.worker = None
        self.msg_queue = queue.Queue()
        self.logs = []
        self.max_logs = 1000
        self.progress = {"current": 0, "total": 0, "percent": 0, "filename": ""}
        self.stats = {"total": 0, "organized": 0, "col_skip": 0, "no_isbn": 0, "error": 0}
        self.status_text = "就绪状态：等待开始"
        self.last_summary = ""
        self.finished = False

    def clear(self):
        self.logs.clear()
        self.progress = {"current": 0, "total": 0, "percent": 0, "filename": ""}
        self.stats = {"total": 0, "organized": 0, "col_skip": 0, "no_isbn": 0, "error": 0}
        self.status_text = "就绪状态：等待开始"
        self.last_summary = ""
        self.finished = False

    def add_log(self, text, tag='info'):
        entry = {"text": text, "tag": tag, "time": time.strftime("%H:%M:%S")}
        self.logs.append(entry)
        if len(self.logs) > self.max_logs:
            self.logs.pop(0)

task_manager = TaskManager()
update_status = {"state": "idle"}

def background_worker(src, dst, action, skip_col, limit, delay, key, dry_run, threads=4, sources=None):
    task_manager.is_running = True
    task_manager.finished = False
    task_manager.status_text = "正在执行整理任务..."

    class WebReporter:
        def log(self, message, level='info'):
            task_manager.add_log(message, level)

        def progress(self, current, total, filename=''):
            pct = round((current / total) * 100, 1) if total > 0 else 0
            task_manager.progress = {
                "current": current,
                "total": total,
                "percent": pct,
                "filename": filename
            }
            task_manager.status_text = f"正在处理 [{current}/{total}] ({pct}%)"

        def stats(self, s_dict):
            task_manager.stats = {
                'total': s_dict.get('total_scanned', 0),
                'organized': len(s_dict.get('organized', [])),
                'col_skip': len(s_dict.get('skipped_collections', [])),
                'no_isbn': len(s_dict.get('skipped_no_isbn', [])),
                'error': len(s_dict.get('errors', []))
            }

    try:
        reporter = WebReporter()
        organizer = book_organizer.BookOrganizer(
            src_dir=src,
            dst_dir=dst,
            action=action,
            skip_collections=skip_col,
            request_delay=delay,
            google_api_key=key,
            dry_run=dry_run,
            threads=threads,
            sources=sources,
            reporter=reporter,
            stop_event=task_manager.stop_event
        )
        success = organizer.run(dry_run=dry_run, limit=limit)
        task_manager.last_summary = organizer.get_summary_text()
        task_manager.status_text = "整理任务完成！" if success else "任务已停止"
        task_manager.add_log(task_manager.last_summary, "success" if success else "warning")
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        task_manager.add_log(f"[严重异常] 运行崩溃: {e}\n{tb}", "error")
        task_manager.status_text = f"运行异常中止: {e}"
    finally:
        task_manager.is_running = False
        task_manager.finished = True

# ----------------- RESTful API 路由 -----------------

@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    if request.method == 'POST':
        data = request.json or {}
        save_settings(data)
        return jsonify({"success": True, "settings": data})
    settings = load_settings()
    settings.pop("google_key", None)
    return jsonify(settings)

@app.route('/api/shelf', methods=['GET'])
def api_shelf():
    settings = load_settings()
    lib_dir = request.args.get('dir') or settings.get('bookshelf_dir') or settings.get('dst')
    if not lib_dir or not os.path.exists(lib_dir):
        return jsonify({"success": False, "message": f"书库目录不存在: {lib_dir}", "books": []})

    books = bookshelf_manager.scan_library(lib_dir)

    # 过滤与搜索
    q = request.args.get('q', '').strip().lower()
    fmt = request.args.get('format', '全部').strip().upper()

    filtered = []
    for idx, b in enumerate(books):
        b_dict = b.to_dict()
        b_dict['id'] = str(idx)
        b_dict['reader_key'] = reader_key(b) if b.file_path else None
        # 格式过滤
        if fmt != '全部':
            if fmt == '其他':
                if b.format in ['EPUB', 'PDF', 'MOBI', 'AZW3', 'TXT']:
                    continue
            elif b.format != fmt:
                continue
        # 搜索过滤
        if q:
            combo = f"{b.title} {b.author} {b.publisher} {b.isbn}".lower()
            if q not in combo:
                continue
        filtered.append(b_dict)

    total_bytes = sum(b.file_size for b in books)
    return jsonify({
        "success": True,
        "library_dir": lib_dir,
        "total_count": len(books),
        "filtered_count": len(filtered),
        "total_size": bookshelf_manager.format_file_size(total_bytes),
        "books": filtered
    })

@app.route('/api/cover/<int:book_idx>')
def api_cover(book_idx):
    settings = load_settings()
    lib_dir = request.args.get('dir') or settings.get('bookshelf_dir') or settings.get('dst')
    books = bookshelf_manager.scan_library(lib_dir)
    if 0 <= book_idx < len(books):
        b = books[book_idx]
        badge = b.format if b.format else "阅读"
        pil_thumb = bookshelf_manager.make_zlib_thumbnail(
            b.cover_path,
            b.title,
            b.author,
            badge_text=badge,
            target_size=(150, 218)
        )
        bio = BytesIO()
        pil_thumb.save(bio, format='JPEG', quality=90)
        bio.seek(0)
        return send_file(bio, mimetype='image/jpeg')
    return send_file(BytesIO(), mimetype='image/jpeg'), 404

@app.route('/api/download/<int:book_idx>')
def api_download(book_idx):
    settings = load_settings()
    lib_dir = request.args.get('dir') or settings.get('bookshelf_dir') or settings.get('dst')
    books = bookshelf_manager.scan_library(lib_dir)
    if 0 <= book_idx < len(books):
        b = books[book_idx]
        if b.file_path and os.path.exists(b.file_path):
            mt, _ = mimetypes.guess_type(b.file_path)
            return send_file(
                b.file_path,
                mimetype=mt or 'application/octet-stream',
                as_attachment=True,
                download_name=os.path.basename(b.file_path)
            )
    return jsonify({"error": "File not found"}), 404

@app.route('/api/preview/<int:book_idx>')
def api_preview(book_idx):
    settings = load_settings()
    lib_dir = request.args.get('dir') or settings.get('bookshelf_dir') or settings.get('dst')
    books = bookshelf_manager.scan_library(lib_dir)
    if 0 <= book_idx < len(books):
        b = books[book_idx]
        chaps = bookshelf_manager.extract_book_preview(b.file_path)
        return jsonify({
            "success": True,
            "title": b.title,
            "author": b.author,
            "format": b.format,
            "chapters": [{"title": c[0], "content": c[1]} for c in chaps]
        })
    return jsonify({"success": False, "error": "Book not found"}), 404

@app.route('/api/metadata/<int:book_idx>', methods=['POST'])
def api_edit_metadata(book_idx):
    settings = load_settings()
    lib_dir = request.args.get('dir') or settings.get('bookshelf_dir') or settings.get('dst')
    books = bookshelf_manager.scan_library(lib_dir)
    if 0 <= book_idx < len(books):
        b = books[book_idx]
        new_meta = request.json or {}
        succ, msg = bookshelf_manager.update_book_metadata(b, new_meta)
        return jsonify({"success": succ, "message": msg})
    return jsonify({"success": False, "message": "图书不存在"}), 404

@app.route('/api/book/<int:book_idx>', methods=['DELETE'])
def api_delete_book(book_idx):
    settings = load_settings()
    lib_dir = request.args.get('dir') or settings.get('bookshelf_dir') or settings.get('dst')
    books = bookshelf_manager.scan_library(lib_dir)
    if 0 <= book_idx < len(books):
        b = books[book_idx]
        succ, msg = bookshelf_manager.delete_book_item(b)
        return jsonify({"success": succ, "message": msg})
    return jsonify({"success": False, "message": "图书不存在"}), 404

@app.route("/plugins", methods=["GET", "POST"])
def manage_plugins():
    status = ""
    error = False
    if request.method == "POST":
        source_id = request.form.get("source")
        if source_id not in SOURCES:
            abort(400, "未知数据源")
        try:
            priority = int(request.form.get("priority", ""))
            if not 1 <= priority <= 999:
                raise ValueError()
            fields = {}
            for key in SOURCES[source_id][1]:
                value = request.form.get(key, "").strip()
                if "\r" in value or "\n" in value:
                    raise ValueError()
                if value or key == "user_agent":
                    fields[key] = value
                elif request.form.get("clear_" + key):
                    fields[key] = ""
            plugin_manager.update(source_id, "enabled" in request.form, priority, fields)
            if source_id == "google_books" and "api_key" in fields:
                settings = load_settings()
                settings.pop("google_key", None)
                save_settings(settings)
            status = f"{SOURCES[source_id][0]} 已保存"
        except ValueError:
            status, error = "优先级须为 1–999 的整数。凭证与 User-Agent 须为单行。", True
        except OSError:
            status, error = "无法写入插件配置，请检查配置目录权限。", True
    sources = plugin_manager.list()
    if load_settings().get("google_key"):
        google = next(source for source in sources if source["id"] == "google_books")
        google["fields"][0]["configured"] = True
    return render_template("scraper_plugins.html", sources=sources, status=status, error=error), (400 if error else 200)


@app.route('/api/organize/start', methods=['POST'])
def api_organize_start():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(success=False, message="请求格式无效。"), 400

    src = data.get("src", "")
    dst = data.get("dst", "")
    if not isinstance(src, str) or not isinstance(dst, str):
        return jsonify(success=False, message="目录必须是有效路径。"), 400
    src, dst = src.strip(), dst.strip()
    action = data.get("action", "copy")
    skip_col = bool(data.get("skip_collections", True))
    dry_run = bool(data.get("dry_run", False))
    sources = data.get("sources")
    try:
        limit = int(data["limit"]) if data.get("limit") else None
        delay = float(data.get("delay", 1.2))
        threads = int(data.get("threads", 4))
        if not 2 <= threads <= 20 or not math.isfinite(delay) or delay < 0 or (limit is not None and limit < 1):
            raise ValueError()
    except (TypeError, ValueError, OverflowError):
        return jsonify(success=False, message="线程数须为 2–20，延时不能为负，数量限制须为正整数。"), 400

    if sources is not None and (
        not isinstance(sources, list) or
        any(not isinstance(source, str) or source not in SOURCES for source in sources)
    ):
        return jsonify(success=False, message="刮削源选择无效。"), 400
    if not plugin_manager.enabled_sources(sources):
        return jsonify(success=False, message="请至少选择一个已启用的刮削源。"), 400
    if not src or not os.path.isdir(src):
        return jsonify(success=False, message=f"待整理源目录不存在: {src}"), 400
    if not dst or action not in ("copy", "move"):
        return jsonify(success=False, message="请检查目标书库目录和整理方式。"), 400

    with task_manager.start_lock:
        if update_status["state"] == "installing":
            return jsonify(success=False, message="系统正在热更新，请稍后再启动整理。"), 409
        if task_manager.is_running:
            return jsonify(success=False, message="已有任务正在执行中！"), 409
        settings = load_settings()
        legacy_key = data.get("google_key", settings.get("google_key")) or None
        settings.update(src=src, dst=dst, action=action, skip_collections=skip_col,
                        delay=str(delay), limit=str(limit or ""), threads=threads, sources=sources)
        if "google_key" in data:
            settings["google_key"] = legacy_key or ""
        if not save_settings(settings):
            return jsonify(success=False, message="保存整理设置失败，请检查配置目录权限。"), 500

        task_manager.clear()
        task_manager.stop_event.clear()
        task_manager.is_running = True
        description = "预演测试" if dry_run else f"正式入库 ({action}模式)"
        task_manager.add_log(f"任务启动: {description} | 源目录: {src} -> 目标库: {dst}", "heading")
        task_manager.worker = threading.Thread(
            target=background_worker,
            args=(src, dst, action, skip_col, limit, delay, legacy_key, dry_run, threads, sources),
            daemon=True,
        )
        try:
            task_manager.worker.start()
        except RuntimeError:
            task_manager.is_running = False
            return jsonify(success=False, message="无法启动整理任务，请重试。"), 500

    return jsonify(success=True, message="任务已启动")

@app.route('/api/organize/stop', methods=['POST'])
def api_organize_stop():
    if task_manager.is_running:
        task_manager.stop_event.set()
        task_manager.add_log("[提示] 用户已发起终止任务请求...", "warning")
        return jsonify({"success": True, "message": "正在安全终止任务..."})
    return jsonify({"success": False, "message": "当前没有正在执行的任务"})

@app.route('/api/organize/status')
def api_organize_status():
    return jsonify({
        "is_running": task_manager.is_running,
        "finished": task_manager.finished,
        "status_text": task_manager.status_text,
        "progress": task_manager.progress,
        "stats": task_manager.stats,
        "logs": task_manager.logs[-200:],
        "summary": task_manager.last_summary
    })

@app.route('/api/organize/clear_log', methods=['POST'])
def api_clear_log():
    task_manager.logs.clear()
    return jsonify({"success": True})


INDEX_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>📚 智能图书整理与现代视觉书架系统</title>
<style>
:root {
  --bg-app: #131722;
  --bg-header: #10141d;
  --bg-panel: #181d28;
  --bg-card: #1e2433;
  --bg-card-hover: #252e42;
  --bg-input: #11151f;
  --border: #293245;
  --border-hover: #38bdf8;
  --accent-cyan: #38bdf8;
  --accent-teal: #0891b2;
  --accent-green: #10b981;
  --text-primary: #f8fafc;
  --text-secondary: #94a3b8;
  --text-muted: #64748b;
  --danger: #ef4444;
  --warning: #f59e0b;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
html { scrollbar-gutter: stable; }
html:has(.modal-overlay.open, #systemUpdate[open]) { overflow: hidden; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
  background-color: var(--bg-app);
  color: var(--text-primary);
  line-height: 1.5;
  overflow-x: hidden;
}
header {
  background: var(--bg-header);
  border-bottom: 1px solid var(--border);
  padding: 12px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  position: sticky;
  top: 0;
  z-index: 100;
}
.logo-box { display: flex; flex-direction: column; }
.logo-title { font-size: 1.15rem; font-weight: 700; color: var(--accent-cyan); letter-spacing: 0.5px; }
.logo-sub { font-size: 0.78rem; color: var(--text-secondary); }
.organize-fields {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(165px, 1fr)); gap: 12px;
}
.organize-fields[hidden] { display: none; }
.organize-fields .form-input { display: block; width: 100%; margin-top: 5px; }
.nav-tabs a { text-decoration: none; }
.nav-tabs { display: flex; gap: 8px; }
.nav-tab {
  padding: 8px 18px;
  border-radius: 6px;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  background: #232a3b;
  color: var(--text-secondary);
  border: none;
  transition: all 0.2s;
}
.nav-tab.active { background: var(--accent-teal); color: #fff; }
.nav-tab:hover:not(.active) { background: #2f384d; color: #fff; }

.container { max-width: 1400px; margin: 0 auto; padding: 18px 20px 40px; }
.tab-content { display: none; }
.tab-content.active { display: block; }

/* 搜索与工具栏 */
.toolbar {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}
.fmt-pills { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
.fmt-pill {
  padding: 5px 14px;
  font-size: 0.85rem;
  font-weight: 600;
  border-radius: 4px;
  cursor: pointer;
  background: #232a3b;
  color: var(--text-secondary);
  border: none;
  transition: 0.2s;
}
.fmt-pill.active { background: var(--accent-teal); color: #fff; }
.fmt-pill:hover:not(.active) { color: #fff; background: #2f384d; }

.search-row { display: flex; gap: 10px; align-items: center; }
.search-wrapper {
  flex: 1;
  display: flex;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 6px;
  align-items: center;
  padding: 2px 10px;
}
.search-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-primary);
  font-size: 0.95rem;
  padding: 8px 6px;
}
.clear-btn { background: transparent; border: none; color: var(--text-muted); cursor: pointer; font-size: 0.9rem; padding: 4px; }
.search-btn {
  background: var(--accent-teal);
  color: #fff;
  border: none;
  padding: 9px 20px;
  font-size: 0.9rem;
  font-weight: 600;
  border-radius: 6px;
  cursor: pointer;
  transition: 0.2s;
}
.search-btn:hover { background: #0e7490; }

.section-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
  padding: 0 4px;
}
.section-title { font-size: 1.15rem; font-weight: 700; color: var(--accent-cyan); display: flex; align-items: center; gap: 8px; }
.section-stats { font-size: 0.85rem; color: var(--text-secondary); }

/* 书架网格 */
.book-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(154px, 1fr));
  gap: 16px;
}
.book-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 7px;
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
  display: flex;
  flex-direction: column;
}
.book-card:hover {
  transform: translateY(-3px);
  border-color: var(--border-hover);
  background: var(--bg-card-hover);
  box-shadow: 0 6px 16px rgba(0,0,0,0.4);
}
.card-cover-box {
  width: 100%;
  aspect-ratio: 150 / 218;
  border-radius: 4px;
  overflow: hidden;
  position: relative;
  background: #11151f;
}
.card-cover { width: 100%; height: 100%; object-fit: cover; display: block; }
.card-badge {
  position: absolute;
  right: 6px;
  bottom: 6px;
  background: rgba(8, 145, 178, 0.92);
  color: #fff;
  font-size: 0.72rem;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 4px;
  letter-spacing: 0.5px;
}
.card-title {
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--text-primary);
  margin-top: 8px;
  margin-bottom: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.book-card:hover .card-title { color: var(--accent-cyan); }
.card-author {
  font-size: 0.78rem;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 模态弹窗 */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.75);
  backdrop-filter: blur(4px);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.2s ease;
}
.modal-overlay.open { opacity: 1; pointer-events: auto; }
.modal-card {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 10px;
  max-width: 720px;
  width: 90%;
  max-height: 85vh;
  overflow-y: auto;
  overscroll-behavior-y: contain;
  box-shadow: 0 10px 30px rgba(0,0,0,0.6);
  padding: 24px;
  position: relative;
}
.close-modal-btn {
  position: absolute;
  top: 14px;
  right: 18px;
  background: transparent;
  border: none;
  color: var(--text-muted);
  font-size: 1.4rem;
  cursor: pointer;
}
.close-modal-btn:hover { color: #fff; }

.modal-content-grid { display: flex; gap: 24px; }
.modal-left { width: 170px; flex-shrink: 0; }
.modal-cover { width: 100%; aspect-ratio: 150 / 218; border-radius: 6px; object-fit: cover; border: 1px solid var(--border); }
.modal-right { flex: 1; display: flex; flex-direction: column; }
.modal-book-title { font-size: 1.3rem; font-weight: 700; color: #fff; margin-bottom: 4px; }
.modal-book-author { font-size: 0.95rem; font-weight: 600; color: var(--accent-cyan); margin-bottom: 12px; }
.modal-meta-list { font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 14px; line-height: 1.7; }
.modal-desc-box {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 10px 12px;
  font-size: 0.84rem;
  color: #cbd5e1;
  max-height: 150px;
  overflow-y: auto;
  margin-bottom: 16px;
}
.modal-btn-row { display: flex; gap: 8px; flex-wrap: wrap; margin-top: auto; }
.btn-action {
  padding: 8px 16px;
  border-radius: 5px;
  font-size: 0.88rem;
  font-weight: 600;
  border: none;
  cursor: pointer;
  transition: 0.2s;
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.btn-green { background: var(--accent-green); color: #fff; }
.btn-green:hover { background: #059669; }
.btn-blue { background: #2563eb; color: #fff; }
.btn-blue:hover { background: #1d4ed8; }
.btn-dark { background: #232a3b; color: #fff; }
.btn-dark:hover { background: #2f384d; }
.btn-red { background: var(--danger); color: #fff; }
.btn-red:hover { background: #dc2626; }

/* 整理页面 */
.card-section {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 18px 20px;
  margin-bottom: 16px;
}
.card-sec-title { font-size: 0.95rem; font-weight: 700; color: var(--accent-cyan); margin-bottom: 12px; }
.form-row { display: flex; gap: 14px; align-items: center; margin-bottom: 10px; flex-wrap: wrap; }
.form-label { width: 140px; font-size: 0.88rem; color: var(--text-secondary); flex-shrink: 0; }
.form-input {
  flex: 1;
  background: var(--bg-input);
  border: 1px solid var(--border);
  color: #fff;
  padding: 8px 12px;
  border-radius: 5px;
  font-size: 0.9rem;
  outline: none;
}
.form-input:focus { border-color: var(--accent-cyan); }
.stats-cards { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin-bottom: 14px; }
.stat-box {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 10px 8px;
  text-align: center;
}
.stat-val { font-size: 1.25rem; font-weight: 700; margin-bottom: 2px; }
.stat-lbl { font-size: 0.76rem; color: var(--text-secondary); }

.progress-bar-wrapper { width: 100%; height: 8px; background: var(--bg-input); border-radius: 4px; overflow: hidden; margin-bottom: 6px; }
.progress-fill { height: 100%; width: 0%; background: var(--accent-cyan); transition: width 0.3s; }
.console-box {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 12px;
  font-family: Consolas, monospace;
  font-size: 0.82rem;
  height: 280px;
  overflow-y: auto;
  line-height: 1.6;
}
.log-heading { color: var(--accent-cyan); font-weight: bold; }
.log-success { color: var(--accent-green); font-weight: bold; }
.log-skip { color: var(--warning); }
.log-error { color: var(--danger); font-weight: bold; }
.log-info { color: #cbd5e1; }

@media (max-width: 768px) {
  .modal-content-grid { flex-direction: column; align-items: center; }
  .modal-left { width: 140px; }
  .stats-cards { grid-template-columns: repeat(2, 1fr); }
}
</style>
</head>

<body>
<header>
  <div class="logo-box">
    <div class="logo-title">📚 MY BOOKSHELF</div>
    <div class="logo-sub">您通往知识和文化的书架 · 随时随地 尽享阅读</div>
  </div>
  <div class="nav-tabs">
    <button class="nav-tab active" onclick="switchMainTab('shelf')">🖼️ 我的书架</button>
    <button class="nav-tab" onclick="switchMainTab('organize')">⚙️ 图书整理</button>
    <a class="nav-tab" href="{{ url_for('manage_plugins') }}">数据源插件</a>
  </div>
</header>

<div class="container">
  <!-- TAB 1: 书架画廊 -->
  <div id="tab-shelf" class="tab-content active">
    <div class="toolbar">
      <div class="fmt-pills" id="fmtPills">
        <button class="fmt-pill active" onclick="setFormat('全部')">全部图书</button>
        <button class="fmt-pill" onclick="setFormat('EPUB')">EPUB</button>
        <button class="fmt-pill" onclick="setFormat('PDF')">PDF</button>
        <button class="fmt-pill" onclick="setFormat('MOBI')">MOBI</button>
        <button class="fmt-pill" onclick="setFormat('AZW3')">AZW3</button>
        <button class="fmt-pill" onclick="setFormat('TXT')">TXT</button>
      </div>
      <div class="search-row">
        <div class="search-wrapper">
          <input type="text" id="searchInput" class="search-input" placeholder="按书名、作者、ISBN、出版社检索..." oninput="onSearchInput()">
          <button class="clear-btn" onclick="clearSearch()">✖</button>
        </div>
        <button class="search-btn" onclick="loadBooks()">🔍 搜索</button>
        <button class="btn-action btn-dark" onclick="loadBooks()">🔄 刷新</button>
      </div>
    </div>

    <div class="section-head">
      <div class="section-title">
        <span>为您收藏的图书</span>
      </div>
      <div class="section-stats" id="shelfStats">正在读取藏书...</div>
    </div>

    <div class="book-grid" id="bookGrid"></div>
  </div>

  <!-- TAB 2: 图书整理 -->
  <div id="tab-organize" class="tab-content">
    <div class="card-section">
      <div class="card-sec-title">📁 路径与目录配置</div>
      <div class="form-row">
        <div class="form-label">待整理图书源目录:</div>
        <input type="text" id="orgSrc" class="form-input" value="/source">
      </div>
      <div class="form-row">
        <div class="form-label">目标已整理书库目录:</div>
        <input type="text" id="orgDst" class="form-input" value="/library">
      </div>
    </div>

    <div class="card-section">
      <div class="card-sec-title">⚙️ 整理规则与参数</div>
      <div class="form-row">
        <div class="form-label">整理方式:</div>
        <label style="margin-right: 18px; cursor: pointer;"><input type="radio" name="orgAction" value="copy" checked> 复制模式 (保留源文件, 安全推荐)</label>
        <label style="cursor: pointer;"><input type="radio" name="orgAction" value="move"> 移动模式 (移动源文件)</label>
      </div>
      <div class="form-row">
        <div class="form-label">合集过滤规则:</div>
        <label style="color: var(--accent-cyan); cursor: pointer;"><input type="checkbox" id="orgSkipCol" checked> 遇到多本拼凑合集，若无出版ISBN则自动跳过不整理</label>
      </div>
      <div class="organize-fields">
        <label>请求间隔（秒）<input type="number" id="orgDelay" class="form-input" value="1.2" min="0" step="0.1"></label>
        <label>数量限制<input type="number" id="orgLimit" class="form-input" min="1" placeholder="不限"></label>
        <label>并发线程（2–20）<input type="number" id="orgThreads" class="form-input" value="4" min="2" max="20"></label>
      </div>
    </div>

    <div class="card-section">
      <div class="card-sec-title">刮削数据源</div>
      <div class="form-row">
        <label><input type="checkbox" id="orgAllSources" checked onchange="updateSourceSelection()"> 使用全部已启用数据源</label>
        <a href="{{ url_for('manage_plugins') }}" style="color: var(--accent-cyan);">管理数据源插件</a>
      </div>
      <div id="orgSourceOptions" class="organize-fields" hidden>
        {% for source in sources %}
        <label><input type="checkbox" name="orgSource" value="{{ source.id }}" {% if not source.enabled %}disabled{% endif %}>
          {{ source.name }}{% if not source.enabled %}（已停用）{% endif %}
        </label>
        {% endfor %}
      </div>
    </div>

    <div style="display: flex; gap: 10px; margin-bottom: 14px;">
      <button class="btn-action btn-blue" id="btnDryRun" onclick="startOrganize(true)">🔍 预演测试 (Dry-Run)</button>
      <button class="btn-action btn-green" id="btnStart" onclick="startOrganize(false)">🚀 开始整理入库</button>
      <button class="btn-action btn-red" id="btnStop" onclick="stopOrganize()" disabled>⏹ 停止任务</button>
      <button class="btn-action btn-dark" style="margin-left: auto;" onclick="clearLogs()">🧹 清空日志</button>
    </div>

    <p id="orgError" role="alert" style="color: var(--danger);"></p>
    <div class="card-section">
      <div class="progress-bar-wrapper">
        <div class="progress-fill" id="progressFill"></div>
      </div>
      <div style="display: flex; justify-content: space-between; font-size: 0.84rem; color: var(--text-secondary); margin-bottom: 12px;">
        <span id="statusText">就绪状态：等待开始</span>
        <span id="progressPct">0%</span>
      </div>

      <div class="stats-cards">
        <div class="stat-box"><div class="stat-val" style="color: #fff;" id="statTotal">0</div><div class="stat-lbl">待处理扫描</div></div>
        <div class="stat-box"><div class="stat-val" style="color: var(--accent-green);" id="statOrganized">0</div><div class="stat-lbl">成功整理入库</div></div>
        <div class="stat-box"><div class="stat-val" style="color: var(--warning);" id="statColSkip">0</div><div class="stat-lbl">无ISBN合集跳过</div></div>
        <div class="stat-box"><div class="stat-val" style="color: var(--text-secondary);" id="statNoIsbn">0</div><div class="stat-lbl">无出版ISBN跳过</div></div>
        <div class="stat-box"><div class="stat-val" style="color: var(--danger);" id="statError">0</div><div class="stat-lbl">发生处理异常</div></div>
      </div>

      <div class="console-box" id="consoleBox"></div>
    </div>
  </div>
</div>

<!-- 图书详情弹窗 -->
<div class="modal-overlay" id="bookModal">
  <div class="modal-card">
    <button class="close-modal-btn" onclick="closeModal('bookModal')">×</button>
    <div class="modal-content-grid">
      <div class="modal-left">
        <img src="" id="modalCover" class="modal-cover" alt="封面">
      </div>
      <div class="modal-right">
        <div class="modal-book-title" id="modalTitle">书名</div>
        <div class="modal-book-author" id="modalAuthor">作者</div>
        <div class="modal-meta-list" id="modalMeta"></div>
        <div class="modal-desc-box" id="modalDesc">暂无简介</div>
        <div class="modal-btn-row">
          <button class="btn-action btn-green" id="modalBtnRead" onclick="onModalRead()">📖 在线阅读</button>
          <button class="btn-action btn-blue" id="modalBtnDownload" onclick="onModalDownload()">⬇️ 下载图书</button>
          <button class="btn-action btn-dark" id="modalBtnEdit" onclick="onModalEdit()">✏️ 编辑信息</button>
          <button class="btn-action btn-dark" id="modalBtnDouban" onclick="onModalDouban()">🔍 豆瓣检索</button>
          <button class="btn-action btn-red" id="modalBtnDelete" onclick="onModalDelete()">🗑️ 删除图书</button>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- 编辑元数据弹窗 -->
<div class="modal-overlay" id="editModal">
  <div class="modal-card" style="max-width: 540px;">
    <button class="close-modal-btn" onclick="closeModal('editModal')">×</button>
    <div style="font-size: 1.1rem; font-weight: 700; color: var(--accent-cyan); margin-bottom: 14px;">✏️ 编辑图书元数据</div>
    <div class="form-row"><div class="form-label">书名:</div><input type="text" id="editTitle" class="form-input"></div>
    <div class="form-row"><div class="form-label">作者:</div><input type="text" id="editAuthor" class="form-input"></div>
    <div class="form-row"><div class="form-label">出版社:</div><input type="text" id="editPublisher" class="form-input"></div>
    <div class="form-row"><div class="form-label">出版日期:</div><input type="text" id="editPubdate" class="form-input"></div>
    <div class="form-row"><div class="form-label">ISBN:</div><input type="text" id="editIsbn" class="form-input"></div>
    <div class="form-row"><div class="form-label">内容简介:</div><textarea id="editDesc" class="form-input" rows="5"></textarea></div>
    <div style="display: flex; gap: 10px; justify-content: flex-end; margin-top: 14px;">
      <button class="btn-action btn-dark" onclick="closeModal('editModal')">取消</button>
      <button class="btn-action btn-green" onclick="saveMetadata()">💾 保存修改</button>
    </div>
  </div>
</div>

<script>
let currentFormat = "全部";
let allBooks = [];
let activeBook = null;
let pollTimer = null;

function switchMainTab(tab) {
  document.querySelectorAll('.nav-tab').forEach((el, idx) => {
    el.classList.toggle('active', (tab === 'shelf' && idx === 0) || (tab === 'organize' && idx === 1));
  });
  document.getElementById('tab-shelf').classList.toggle('active', tab === 'shelf');
  document.getElementById('tab-organize').classList.toggle('active', tab === 'organize');
  if (tab === 'shelf') loadBooks();
}

function setFormat(fmt) {
  currentFormat = fmt;
  document.querySelectorAll('.fmt-pill').forEach(btn => {
    btn.classList.toggle('active', btn.textContent.trim() === fmt || (fmt === '全部' && btn.textContent.trim() === '全部图书'));
  });
  loadBooks();
}

function onSearchInput() {
  clearTimeout(window._searchTimer);
  window._searchTimer = setTimeout(loadBooks, 250);
}

function clearSearch() {
  document.getElementById('searchInput').value = '';
  loadBooks();
}

async function loadBooks() {
  const q = document.getElementById('searchInput').value.trim();
  const url = `/api/shelf?format=${encodeURIComponent(currentFormat)}&q=${encodeURIComponent(q)}`;
  try {
    const res = await fetch(url);
    const data = await res.json();
    if (data.success) {
      allBooks = data.books;
      renderGrid(allBooks);
      document.getElementById('shelfStats').textContent = `共 ${data.total_count} 本藏书 · 筛选出 ${data.filtered_count} 本 · 总大小: ${data.total_size}`;
    } else {
      document.getElementById('bookGrid').innerHTML = `<div style="grid-column: 1/-1; text-align: center; padding: 60px 0; color: var(--text-muted);">${data.message}</div>`;
    }
  } catch (err) {
    console.error(err);
  }
}

function renderGrid(books) {
  const container = document.getElementById('bookGrid');
  if (!books || books.length === 0) {
    container.innerHTML = `
      <div style="grid-column: 1/-1; text-align: center; padding: 60px 0;">
        <div style="font-size: 3rem; margin-bottom: 10px;">📭</div>
        <div style="font-size: 1.1rem; font-weight: bold; margin-bottom: 6px;">书架暂无符合条件的图书</div>
        <div style="color: var(--text-secondary); font-size: 0.85rem; margin-bottom: 16px;">请切换格式筛选，或前往【图书整理】导入新书！</div>
        <button class="btn-action btn-blue" onclick="switchMainTab('organize')">🚀 前往整理图书</button>
      </div>`;
    return;
  }

  container.innerHTML = books.map((b, idx) => `
    <div class="book-card" onclick="openBookModal(${idx})">
      <div class="card-cover-box">
        <img class="card-cover" src="/api/cover/${b.id}" loading="lazy" alt="${b.title}">
        <span class="card-badge">${b.format || '阅读'}</span>
      </div>
      <div class="card-title" title="${b.title}">${b.title}</div>
      <div class="card-author" title="${b.author}">${b.author || '未知作者'}</div>
    </div>
  `).join('');
}

function openBookModal(idx) {
  activeBook = allBooks[idx];
  if (!activeBook) return;

  document.getElementById('modalCover').src = `/api/cover/${activeBook.id}`;
  document.getElementById('modalTitle').textContent = `《${activeBook.title}》`;
  document.getElementById('modalAuthor').textContent = `作者: ${activeBook.author || '未知'}`;

  const metaHtml = `
    出版社: ${activeBook.publisher || '未知'}<br>
    出版日期: ${activeBook.pubdate || '未知'}<br>
    ISBN: ${activeBook.isbn || '无'}<br>
    文件格式: ${activeBook.format}  |  文件大小: ${activeBook.file_size_str}<br>
    目录: ${activeBook.folder_path ? activeBook.folder_path.split('/').pop().split('\\\\').pop() : ''}
  `;
  document.getElementById('modalMeta').innerHTML = metaHtml;
  document.getElementById('modalDesc').textContent = activeBook.description || '暂无内容简介。';

  openModal('bookModal');
}

function closeModal(id) {
  document.getElementById(id).classList.remove('open');
}
function openModal(id) {
  document.getElementById(id).classList.add('open');
}

function onModalDownload() {
  if (activeBook) window.open(`/api/download/${activeBook.id}`, '_blank');
}

function onModalRead() {
  if (!activeBook?.reader_key) return;
  window.open(`/read/${activeBook.id}?key=${activeBook.reader_key}`, '_blank', 'noopener');
}

function onModalEdit() {
  if (!activeBook) return;
  document.getElementById('editTitle').value = activeBook.title;
  document.getElementById('editAuthor').value = activeBook.author;
  document.getElementById('editPublisher').value = activeBook.publisher;
  document.getElementById('editPubdate').value = activeBook.pubdate;
  document.getElementById('editIsbn').value = activeBook.isbn;
  document.getElementById('editDesc').value = activeBook.description;
  openModal('editModal');
}

async function saveMetadata() {
  if (!activeBook) return;
  const body = {
    title: document.getElementById('editTitle').value.trim(),
    author: document.getElementById('editAuthor').value.trim(),
    publisher: document.getElementById('editPublisher').value.trim(),
    pubdate: document.getElementById('editPubdate').value.trim(),
    isbn: document.getElementById('editIsbn').value.trim(),
    description: document.getElementById('editDesc').value.trim()
  };
  const res = await fetch(`/api/metadata/${activeBook.id}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  const data = await res.json();
  if (data.success) {
    closeModal('editModal');
    closeModal('bookModal');
    loadBooks();
  } else {
    alert(data.message || '保存失败');
  }
}

async function onModalDelete() {
  if (!activeBook) return;
  if (!confirm(`确定要从书架彻底删除图书《${activeBook.title}》吗？此操作将从磁盘移除该文件！`)) return;
  const res = await fetch(`/api/book/${activeBook.id}`, { method: 'DELETE' });
  const data = await res.json();
  if (data.success) {
    closeModal('bookModal');
    loadBooks();
  } else {
    alert(data.message || '删除失败');
  }
}

function onModalDouban() {
  if (activeBook) {
    const q = activeBook.isbn || activeBook.title;
    window.open(`https://search.douban.com/book/subject_search?search_text=${encodeURIComponent(q)}`, '_blank');
  }
}

// 整理任务相关交互
function updateSourceSelection() {
  document.getElementById('orgSourceOptions').hidden = document.getElementById('orgAllSources').checked;
}

async function startOrganize(dryRun) {
  const body = {
    src: document.getElementById('orgSrc').value.trim(),
    dst: document.getElementById('orgDst').value.trim(),
    action: document.querySelector('input[name="orgAction"]:checked').value,
    skip_collections: document.getElementById('orgSkipCol').checked,
    delay: document.getElementById('orgDelay').value,
    limit: document.getElementById('orgLimit').value,
    sources: document.getElementById('orgAllSources').checked ? null :
      Array.from(document.querySelectorAll('input[name="orgSource"]:checked:not(:disabled)'), input => input.value),
    threads: document.getElementById('orgThreads').value,
    dry_run: dryRun
  };
  const status = document.getElementById('statusText');
  const buttons = ['btnStart', 'btnDryRun'].map(id => document.getElementById(id));
  buttons.forEach(button => button.disabled = true);
  document.getElementById('orgError').textContent = '';
  status.textContent = '正在启动任务…';
  try {
    const res = await fetch('/api/organize/start', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body)
    });
    const data = await res.json();
    if (!data.success) throw new Error(data.message);
    document.getElementById('btnStop').disabled = false;
    startPolling();
  } catch (error) {
    status.textContent = '启动失败';
    document.getElementById('orgError').textContent = error.message;
    buttons.forEach(button => button.disabled = false);
  }
}

async function stopOrganize() {
  await fetch('/api/organize/stop', { method: 'POST' });
  document.getElementById('btnStop').disabled = true;
}

async function clearLogs() {
  await fetch('/api/organize/clear_log', { method: 'POST' });
  document.getElementById('consoleBox').innerHTML = '';
}

function startPolling() {
  clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    try {
      const res = await fetch('/api/organize/status');
      const data = await res.json();

      document.getElementById('statusText').textContent = data.status_text;
      document.getElementById('progressFill').style.width = `${data.progress.percent}%`;
      document.getElementById('progressPct').textContent = `${data.progress.percent}%`;

      document.getElementById('statTotal').textContent = data.stats.total;
      document.getElementById('statOrganized').textContent = data.stats.organized;
      document.getElementById('statColSkip').textContent = data.stats.col_skip;
      document.getElementById('statNoIsbn').textContent = data.stats.no_isbn;
      document.getElementById('statError').textContent = data.stats.error;

      // 日志渲染
      const box = document.getElementById('consoleBox');
      box.replaceChildren(...data.logs.map(l => {
        let cls = 'log-info';
        if (l.tag === 'heading') cls = 'log-heading';
        else if (l.tag === 'success') cls = 'log-success';
        else if (l.tag === 'skip' || l.tag === 'warning') cls = 'log-skip';
        else if (l.tag === 'error') cls = 'log-error';
        const line = document.createElement('div');
        line.className = cls;
        line.textContent = `[${l.time}] ${l.text}`;
        return line;
      }));
      box.scrollTop = box.scrollHeight;

      if (!data.is_running) {
        clearInterval(pollTimer);
        document.getElementById('btnStart').disabled = false;
        document.getElementById('btnDryRun').disabled = false;
        document.getElementById('btnStop').disabled = true;
        if (data.finished && data.stats.organized > 0) {
          loadBooks();
        }
      }
    } catch (err) {
      console.error(err);
    }
  }, 1000);
}

// 初始化
document.addEventListener('DOMContentLoaded', async () => {
  if (location.hash === '#organize') switchMainTab('organize');
  try {
    const sRes = await fetch('/api/settings');
    const settings = await sRes.json();
    if (settings.src) document.getElementById('orgSrc').value = settings.src;
    if (settings.dst) document.getElementById('orgDst').value = settings.dst;
    if (settings.delay) document.getElementById('orgDelay').value = settings.delay;
    document.getElementById('orgSkipCol').checked = settings.skip_collections !== false;
    document.querySelectorAll('input[name="orgAction"]').forEach(input => {
      input.checked = input.value === (settings.action === 'move' ? 'move' : 'copy');
    });
    if (Array.isArray(settings.sources)) {
      document.getElementById('orgAllSources').checked = false;
      document.querySelectorAll('input[name="orgSource"]').forEach(input => {
        input.checked = settings.sources.includes(input.value);
      });
      updateSourceSelection();
    }
    if (settings.threads) document.getElementById('orgThreads').value = settings.threads;
    if (settings.limit) document.getElementById('orgLimit').value = settings.limit;
  } catch (e) {}
  loadBooks();
});
</script>

<!-- 屏幕左下角常驻固定版本号徽章 -->
<button type="button" id="appVersionBadge" style="position: fixed; bottom: 14px; left: 16px; z-index: 99999; display: flex; align-items: center; gap: 6px; background: rgba(15, 23, 42, 0.88); backdrop-filter: blur(8px); border: 1px solid rgba(14, 165, 233, 0.35); padding: 5px 12px; border-radius: 20px; box-shadow: 0 4px 16px rgba(0,0,0,0.5); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', monospace; cursor: pointer; transition: all 0.2s ease;" title="检查热更新" onclick="showVersionInfo()">
  <span style="display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: #10b981; box-shadow: 0 0 8px #10b981;"></span>
  <span style="color: #94a3b8; font-size: 0.75rem; font-weight: 500;">版本:</span>
  <span style="color: #38bdf8; font-size: 0.8rem; font-weight: 700; letter-spacing: 0.5px;">v{{ app_version }}</span>
</button>

<dialog id="systemUpdate" style="margin: auto; width: min(92vw, 420px); padding: 20px; border: 1px solid var(--border); border-radius: 12px; background: var(--bg-app); color: var(--text-primary);">
  <h2 style="font-size: 1.15rem;">系统更新</h2>
  <p id="systemUpdateStatus" role="status" style="margin: 14px 0;">当前版本 v{{ app_version }}</p>
  <form method="dialog" style="display: flex; flex-wrap: wrap; gap: 8px;">
    <button type="button" class="btn-action btn-blue" id="checkUpdate">检查更新</button>
    <button type="button" class="btn-action btn-green" id="applyUpdate" hidden>立即热更新</button>
    <button class="btn-action btn-dark">关闭</button>
  </form>
</dialog>

<script>
const updateDialog = document.getElementById('systemUpdate');
const updateMessage = document.getElementById('systemUpdateStatus');
const checkUpdateButton = document.getElementById('checkUpdate');
const applyUpdateButton = document.getElementById('applyUpdate');
let selectedRelease;

function showVersionInfo() {
  if (!updateDialog.open) updateDialog.showModal();
  if (!checkUpdateButton.disabled) checkUpdateButton.click();
}

checkUpdateButton.onclick = async () => {
  checkUpdateButton.disabled = true;
  applyUpdateButton.hidden = true;
  updateMessage.textContent = '正在检查已发布版本…';
  try {
    const data = await (await fetch('/api/system/check_update', {cache: 'no-store'})).json();
    if (data.error) throw new Error(data.error);
    selectedRelease = data.has_update ? data.release : null;
    applyUpdateButton.hidden = !selectedRelease;
    updateMessage.textContent = selectedRelease
      ? `当前 v${data.current_version}，可升级至 v${selectedRelease.version}。`
      : `当前 v${data.current_version}，已是最新版本。`;
  } catch (error) {
    updateMessage.textContent = error.message;
  } finally {
    checkUpdateButton.disabled = false;
  }
};

applyUpdateButton.onclick = async () => {
  if (!selectedRelease) return;
  applyUpdateButton.hidden = true;
  checkUpdateButton.disabled = true;
  updateMessage.textContent = '正在下载并验证更新，完成后页面会自动刷新…';
  try {
    const response = await fetch('/api/system/hot_update', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({commit: selectedRelease.commit})
    });
    const result = await response.json();
    if (!result.success) throw new Error(result.error);
    for (let i = 0; i < 90; i++) {
      await new Promise(resolve => setTimeout(resolve, 2000));
      const data = await fetch('/api/system/hot_update', {cache: 'no-store'})
        .then(response => response.json()).catch(() => null);
      if (!data) continue;
      if (data.git_commit === selectedRelease.commit) {
        location.reload();
        return;
      }
      if (data.state === 'failed') throw new Error(data.error);
      if (data.state === 'idle') throw new Error('新版启动失败，已恢复镜像自带版本。');
    }
    throw new Error('更新等待超时，请再次检查版本。');
  } catch (error) {
    updateMessage.textContent = error.message;
  } finally {
    checkUpdateButton.disabled = false;
  }
};
</script>

</body>
</html>
"""



@app.route('/api/book/<int:book_idx>/toc')
def api_book_toc(book_idx):
    """只读取章节目录大纲 (0.02秒瞬开，不解压正文)"""
    lib_dir = get_library_dir()
    books = bookshelf_manager.scan_library(lib_dir)
    book = next((b for b in books if b.id == book_idx), None)
    if not book:
        return jsonify({"success": False, "error": "书籍未找到"}), 404
    
    # 提取章节信息 (带性能保护)
    chaps = bookshelf_manager.extract_book_preview(book.file_path)
    toc_list = [{"title": t, "index": i} for i, (t, c) in enumerate(chaps)]
    return jsonify({
        "success": True,
        "book": book.to_dict(),
        "total_chapters": len(toc_list),
        "toc": toc_list
    })

@app.route('/api/book/<int:book_idx>/chapter/<int:chap_idx>')
def api_book_chapter(book_idx, chap_idx):
    """按需只解压并读取当前一章正文 (0.01秒呈现，彻底不卡)"""
    lib_dir = get_library_dir()
    books = bookshelf_manager.scan_library(lib_dir)
    book = next((b for b in books if b.id == book_idx), None)
    if not book:
        return jsonify({"success": False, "error": "书籍未找到"}), 404
    
    chaps = bookshelf_manager.extract_book_preview(book.file_path)
    if 0 <= chap_idx < len(chaps):
        title, content = chaps[chap_idx]
        return jsonify({
            "success": True,
            "title": title,
            "content": content,
            "index": chap_idx,
            "total": len(chaps)
        })
    return jsonify({"success": False, "error": "章节超出范围"}), 404


# ---- Koodo Reader ----
KOODO_DIR = os.path.join(hot_update.IMAGE_DIR, "koodo_reader")


def reader_key(book):
    return sha256(os.fsencode(os.path.normcase(os.path.abspath(book.file_path)))).hexdigest()


def find_reader_book(book_idx, key=None):
    settings = load_settings()
    books = bookshelf_manager.scan_library(settings.get("bookshelf_dir") or settings.get("dst"))
    if 0 <= book_idx < len(books):
        book = books[book_idx]
        if book.file_path and (key is None or reader_key(book) == key):
            return book_idx, book
    if key:
        for idx, book in enumerate(books):
            if book.file_path and reader_key(book) == key:
                return idx, book
    abort(404, "书籍已移除或文件不可用。")


def require_koodo():
    if not os.path.isfile(os.path.join(KOODO_DIR, "index.html")):
        abort(503, "Koodo Reader 静态资源缺失，请使用包含 Koodo Reader 的构建。")


@app.route("/koodo/")
def koodo_index():
    require_koodo()
    return send_from_directory(KOODO_DIR, "index.html", max_age=0)


@app.route("/koodo/<path:filename>")
def koodo_static(filename):
    return send_from_directory(KOODO_DIR, filename)


@app.route("/api/reader-file/<int:book_idx>/<key>/<filename>")
def reader_file(book_idx, key, filename):
    _, book = find_reader_book(book_idx, key)
    if filename != os.path.basename(book.file_path) or not os.path.isfile(book.file_path):
        abort(404)
    return send_file(book.file_path, mimetype="application/octet-stream", as_attachment=True)


# ---- Version and Hot-Update APIs ----
@app.route('/api/version')
def api_version():
    return jsonify({
        "version": APP_VERSION,
        "build_date": BUILD_DATE,
        "git_commit": os.getenv('GIT_COMMIT', ''),
        "features": FEATURES
    })

@app.route('/api/system/check_update')
def api_check_update():
    if not hot_update.supported():
        return jsonify(error="当前部署缺少热更新支持，请先拉取新版 Docker 镜像。"), 503
    try:
        release = hot_update.latest_release()
        return jsonify(
            has_update=hot_update.has_update(release, os.getenv("GIT_COMMIT", ""), APP_VERSION),
            release=release, current_version=APP_VERSION,
        )
    except Exception:
        app.logger.exception("Unable to check for published updates")
        return jsonify(error="无法检查更新，请确认容器能够访问 GitHub 后重试。"), 502


@app.route('/api/system/hot_update', methods=['GET', 'POST'])
def api_hot_update():
    commit = os.getenv("GIT_COMMIT", "")
    if request.method == "GET":
        return jsonify(**update_status, git_commit=commit)
    if not hot_update.supported():
        return jsonify(success=False, error="请先拉取新版 Docker 镜像。"), 503
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("commit"), str):
        return jsonify(success=False, error="请先检查更新。"), 400

    def update_worker():
        try:
            release = hot_update.latest_release()
            if data["commit"] != release["commit"] or not hot_update.has_update(release, commit, APP_VERSION):
                raise hot_update.UpdateError("可用版本已变化，请重新检查更新。")
            hot_update.install(release)
        except hot_update.UpdateError as error:
            update_status.update(state="failed", error=str(error))
            return
        except Exception:
            app.logger.exception("Hot update failed")
            update_status.update(state="failed", error="下载或验证更新失败，请检查容器日志后重试。")
            return
        os._exit(hot_update.RESTART)

    with task_manager.start_lock:
        if task_manager.is_running or update_status["state"] == "installing":
            return jsonify(success=False, error="请等当前整理或更新任务结束后重试。"), 409
        update_status.update(state="installing", error="")
        try:
            threading.Thread(target=update_worker, daemon=True).start()
        except RuntimeError:
            update_status.update(state="failed", error="无法启动更新任务，请重试。")
            return jsonify(success=False, error=update_status["error"]), 500
    return jsonify(success=True), 202

@app.route('/read/<int:book_idx>')
def read_book_page(book_idx):
    book_idx, book = find_reader_book(book_idx, request.args.get("key"))
    if not os.path.isfile(book.file_path):
        abort(404, "书籍文件不可用。")
    require_koodo()
    file_url = url_for(
        "reader_file", book_idx=book_idx, key=reader_key(book),
        filename=os.path.basename(book.file_path),
    )
    reader_url = url_for("koodo_index") + "#/manager/home?" + urllib.parse.urlencode({
        "bookshelfFile": file_url,
    })
    return render_template(
        "koodo_book.html", book=book, book_idx=book_idx,
        file_url=file_url, reader_url=reader_url,
    )

@app.route('/')
def index():
    return render_template_string(INDEX_HTML, app_version=os.getenv('APP_VERSION', APP_VERSION), sources=plugin_manager.list())

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 14808))
    print(f"Starting Book Organizer Web Server on http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)

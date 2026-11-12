from plugins_manager import plugin_manager

STANDALONE_READER_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>沉浸阅读器 - 智能图书管理系统</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    :root {
      --bg-base: #0f1117;
      --bg-side: #181b22;
      --bg-card: #20242e;
      --border: #2c3240;
      --text-main: #f1f5f9;
      --text-muted: #94a3b8;
      --accent: #0ea5e9;
      --reader-bg: #14161d;
      --reader-text: #e2e8f0;
      --reader-font-size: 1.15rem;
      --reader-line-height: 1.9;
    }
    body.theme-sepia {
      --bg-base: #f4ecd8;
      --bg-side: #e9dec4;
      --bg-card: #ded0b4;
      --border: #cdbe9f;
      --text-main: #433422;
      --text-muted: #79664f;
      --accent: #b45309;
      --reader-bg: #f9f4e8;
      --reader-text: #2d241e;
    }
    body.theme-light {
      --bg-base: #f8fafc;
      --bg-side: #ffffff;
      --bg-card: #f1f5f9;
      --border: #e2e8f0;
      --text-main: #0f172a;
      --text-muted: #64748b;
      --accent: #0284c7;
      --reader-bg: #ffffff;
      --reader-text: #1e293b;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif; background: var(--bg-base); color: var(--text-main); height: 100vh; display: flex; flex-direction: column; overflow: hidden; }
    
    .topbar { height: 52px; background: var(--bg-side); border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; padding: 0 20px; flex-shrink: 0; z-index: 10; }
    .top-left { display: flex; align-items: center; gap: 12px; }
    .btn-nav-back { color: var(--text-muted); text-decoration: none; font-size: 0.88rem; font-weight: 600; padding: 6px 12px; background: var(--bg-card); border: 1px solid var(--border); border-radius: 6px; }
    .btn-nav-back:hover { color: var(--accent); border-color: var(--accent); }
    .book-title { font-size: 1.05rem; font-weight: 700; color: var(--accent); max-width: 450px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .top-right { display: flex; align-items: center; gap: 8px; }
    .ctrl-btn { background: var(--bg-card); border: 1px solid var(--border); color: var(--text-main); border-radius: 6px; padding: 6px 12px; cursor: pointer; font-size: 0.85rem; font-weight: 500; }
    .ctrl-btn:hover { border-color: var(--accent); color: var(--accent); }

    .main-body { flex: 1; display: flex; overflow: hidden; position: relative; }
    .sidebar { width: 360px; background: var(--bg-side); border-right: 1px solid var(--border); display: flex; flex-direction: column; transition: all 0.25s ease; flex-shrink: 0; }
    .sidebar.collapsed { margin-left: -360px; }
    .side-tabs { display: flex; border-bottom: 1px solid var(--border); background: var(--bg-base); }
    .side-tab { flex: 1; text-align: center; padding: 12px 0; font-size: 0.9rem; font-weight: 600; cursor: pointer; color: var(--text-muted); border-bottom: 2px solid transparent; }
    .side-tab.active { color: var(--accent); border-bottom-color: var(--accent); background: var(--bg-side); }
    .tab-content { flex: 1; overflow-y: auto; padding: 18px; display: none; }
    .tab-content.active { display: block; }

    .cover-box { text-align: center; margin-bottom: 18px; }
    .cover-box img { max-width: 170px; max-height: 240px; border-radius: 8px; box-shadow: 0 10px 25px rgba(0,0,0,0.4); border: 1px solid var(--border); }
    .detail-item { font-size: 0.88rem; margin-bottom: 10px; display: flex; gap: 8px; }
    .detail-label { color: var(--text-muted); width: 68px; flex-shrink: 0; }
    .detail-val { color: var(--text-main); font-weight: 500; word-break: break-all; }
    .detail-desc { margin-top: 14px; background: var(--bg-card); padding: 14px; border-radius: 8px; font-size: 0.88rem; line-height: 1.65; color: var(--text-muted); max-height: 220px; overflow-y: auto; border: 1px solid var(--border); }
    .action-down-btn { display: block; text-align: center; margin-top: 16px; background: #0284c7; color: #fff; padding: 10px; border-radius: 6px; text-decoration: none; font-size: 0.9rem; font-weight: 600; }

    .chap-item { padding: 10px 14px; font-size: 0.88rem; border-radius: 6px; cursor: pointer; margin-bottom: 4px; color: var(--text-muted); display: flex; align-items: center; justify-content: space-between; }
    .chap-item:hover { background: var(--bg-card); color: var(--text-main); }
    .chap-item.active { background: var(--accent); color: #fff; font-weight: 600; }

    .reader-stage { flex: 1; background: var(--reader-bg); display: flex; flex-direction: column; overflow: hidden; position: relative; }
    .reader-scroll { flex: 1; overflow-y: auto; padding: 40px 60px; display: flex; justify-content: center; }
    .article-container { width: 100%; max-width: 860px; font-size: var(--reader-font-size); line-height: var(--reader-line-height); color: var(--reader-text); }
    .article-title { font-size: 1.7rem; font-weight: 800; margin-bottom: 24px; padding-bottom: 12px; border-bottom: 1px solid var(--border); color: var(--accent); }
    .article-container p { margin-bottom: 1.3em; text-indent: 2em; letter-spacing: 0.5px; }

    .footer-bar { height: 52px; background: var(--bg-side); border-top: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; padding: 0 28px; flex-shrink: 0; }
    .page-btn { background: var(--bg-card); border: 1px solid var(--border); color: var(--text-main); border-radius: 6px; padding: 7px 16px; cursor: pointer; font-size: 0.88rem; font-weight: 600; }
    .page-btn:disabled { opacity: 0.4; cursor: not-allowed; }
    .page-info { font-size: 0.88rem; color: var(--text-muted); font-weight: 500; }
  </style>
</head>
<body class="theme-dark" id="appBody">

  <div class="topbar">
    <div class="top-left">
      <a href="/" class="btn-nav-back">← 返回书架</a>
      <button class="ctrl-btn" onclick="toggleSidebar()">
        <span>☰</span> <span id="toggleText">折叠详情</span>
      </button>
      <div class="book-title" id="bookTitle">正在加载图书...</div>
      <span style="background:rgba(14,165,233,0.15); color:var(--accent); border:1px solid rgba(14,165,233,0.3); padding:2px 8px; border-radius:10px; font-size:0.75rem; font-weight:600;">v2.5.0</span>
    </div>
    <div class="top-right">
      <button class="ctrl-btn" onclick="changeFontSize(-1)">A- 字号</button>
      <button class="ctrl-btn" onclick="changeFontSize(1)">A+ 字号</button>
      <button class="ctrl-btn" onclick="setTheme('theme-dark')">🌙 黑金</button>
      <button class="ctrl-btn" onclick="setTheme('theme-sepia')">📜 羊皮纸</button>
      <button class="ctrl-btn" onclick="setTheme('theme-light')">☀️ 浅色</button>
      <button class="ctrl-btn" onclick="toggleFullScreen()">⛶ 全屏</button>
      <a id="btnDownloadTop" href="#" class="ctrl-btn" style="text-decoration:none;" target="_blank">⬇️ 导出EPUB</a>
    </div>
  </div>

  <div class="main-body">
    <div class="sidebar" id="sidebar">
      <div class="side-tabs">
        <div class="side-tab active" onclick="switchSideTab(0)">📖 章节大纲</div>
        <div class="side-tab" onclick="switchSideTab(1)">ℹ️ 书籍详情</div>
      </div>
      
      <div class="tab-content active" id="tabChapters">
        <div style="padding:20px; color:var(--text-muted); text-align:center;">正在解析 Spine 目录大纲...</div>
      </div>

      <div class="tab-content" id="tabDetail">
        <div class="cover-box">
          <img id="detailCover" src="" alt="封面" style="display:none;">
          <div id="detailFallbackCover" style="width:140px; height:200px; background:var(--bg-card); display:inline-flex; align-items:center; justify-content:center; border-radius:6px; font-size:2rem;">📚</div>
        </div>
        <div class="detail-item"><span class="detail-label">书名:</span><span class="detail-val" id="detTitle">-</span></div>
        <div class="detail-item"><span class="detail-label">作者:</span><span class="detail-val" id="detAuthor">-</span></div>
        <div class="detail-item"><span class="detail-label">ISBN:</span><span class="detail-val" id="detIsbn">-</span></div>
        <div class="detail-item"><span class="detail-label">出版社:</span><span class="detail-val" id="detPublisher">-</span></div>
        <div class="detail-item"><span class="detail-label">出版年:</span><span class="detail-val" id="detYear">-</span></div>
        <div class="detail-desc">
          <strong>简介说明：</strong><br>
          <span id="detDesc">暂无内容简介。</span>
        </div>
        <a id="btnDownloadSide" href="#" class="action-down-btn" target="_blank">⬇️ 下载原书到本地</a>
      </div>
    </div>

    <div class="reader-stage">
      <div class="reader-scroll" id="scrollContainer">
        <div class="article-container">
          <h1 class="article-title" id="chapterHeading">正在加载正文...</h1>
          <div id="chapterBody" style="color:var(--text-muted); line-height:2;">请稍候，正在安全解压并按权威 Spine 顺序读取图书章节...</div>
        </div>
      </div>

      <div class="footer-bar">
        <button class="page-btn" id="btnPrev" onclick="prevChapter()" disabled>← 上一章节</button>
        <div class="page-info" id="pageInfo">正在加载...</div>
        <button class="page-btn" id="btnNext" onclick="nextChapter()" disabled>下一章节 →</button>
      </div>
    </div>
  </div>

  <script>
    const bookId = {{ book_id }};
    let chaptersData = [];
    let currentIdx = 0;
    let fontSize = 1.15;

    async function initReader() {
      document.getElementById('btnDownloadTop').href = `/api/download/${bookId}`;
      document.getElementById('btnDownloadSide').href = `/api/download/${bookId}`;

      // 1. 获取书籍详情信息
      try {
        const bRes = await fetch('/api/books');
        const bData = await bRes.json();
        const book = bData.books.find(b => b.id === bookId);
        if (book) {
          document.title = `《${book.title}》 - 沉浸阅读`;
          document.getElementById('bookTitle').textContent = `《${book.title}》 - ${book.author || '未知作者'}`;
          document.getElementById('detTitle').textContent = book.title;
          document.getElementById('detAuthor').textContent = book.author || '未知作者';
          document.getElementById('detIsbn').textContent = book.isbn || '无';
          document.getElementById('detPublisher').textContent = book.publisher || '未知出版社';
          document.getElementById('detYear').textContent = book.pub_year || '未知年份';
          document.getElementById('detDesc').textContent = book.description || '暂无内容简介。';
          if (book.cover_path) {
            const img = document.getElementById('detailCover');
            img.src = `/api/cover/${book.id}`;
            img.style.display = 'inline-block';
            document.getElementById('detailFallbackCover').style.display = 'none';
          }
        }
      } catch(e) {}

      // 2. 获取严格 Spine 排序的章节与正文
      try {
        const pRes = await fetch(`/api/preview/${bookId}`);
        const pData = await pRes.json();
        if (pData.success && pData.chapters && pData.chapters.length > 0) {
          chaptersData = pData.chapters;
          renderTOC();
          renderChapter(0);
        } else {
          document.getElementById('chapterHeading').textContent = '未提取到正文文本';
          document.getElementById('chapterBody').innerHTML = '<div style="color:#ef4444;">本书未提取到有效章节文本，请点击顶栏【⬇️ 导出EPUB】在本地阅读器中打开。</div>';
        }
      } catch(err) {
        document.getElementById('chapterHeading').textContent = '加载失败';
        document.getElementById('chapterBody').innerHTML = `<div style="color:#ef4444;">无法读取图书: ${err}</div>`;
      }
    }

    function renderTOC() {
      const tab = document.getElementById('tabChapters');
      tab.innerHTML = chaptersData.map((c, i) => `
        <div class="chap-item ${i===0?'active':''}" onclick="selectChapter(${i})" id="chapItem_${i}">
          <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:240px;">${c.title}</span>
          <span style="font-size:0.75rem; opacity:0.6;">第 ${i+1} 节</span>
        </div>
      `).join('');
    }

    function renderChapter(idx) {
      if (idx < 0 || idx >= chaptersData.length) return;
      currentIdx = idx;
      const ch = chaptersData[idx];
      document.getElementById('chapterHeading').textContent = ch.title;
      
      const paragraphs = ch.content.split(/
+/).filter(p => p.trim());
      document.getElementById('chapterBody').innerHTML = paragraphs.map(p => `<p>${p.trim()}</p>`).join('');
      
      document.querySelectorAll('.chap-item').forEach((el, i) => {
        el.classList.toggle('active', i === idx);
      });
      const activeEl = document.getElementById(`chapItem_${idx}`);
      if (activeEl) activeEl.scrollIntoView({ block: 'nearest', behavior: 'smooth' });

      document.getElementById('pageInfo').textContent = `第 ${idx + 1} / ${chaptersData.length} 节 · ${Math.round((idx + 1)/chaptersData.length*100)}%`;
      document.getElementById('btnPrev').disabled = (idx === 0);
      document.getElementById('btnNext').disabled = (idx === chaptersData.length - 1);
      document.getElementById('scrollContainer').scrollTop = 0;
    }

    function prevChapter() { if (currentIdx > 0) renderChapter(currentIdx - 1); }
    function nextChapter() { if (currentIdx < chaptersData.length - 1) renderChapter(currentIdx + 1); }
    function selectChapter(idx) { renderChapter(idx); }

    function switchSideTab(idx) {
      document.querySelectorAll('.side-tab').forEach((el, i) => el.classList.toggle('active', i === idx));
      document.getElementById('tabChapters').classList.toggle('active', idx === 0);
      document.getElementById('tabDetail').classList.toggle('active', idx === 1);
    }

    function toggleSidebar() {
      const side = document.getElementById('sidebar');
      const collapsed = side.classList.toggle('collapsed');
      document.getElementById('toggleText').textContent = collapsed ? '展开详情' : '折叠详情';
    }

    function changeFontSize(delta) {
      fontSize = Math.max(0.85, Math.min(2.2, fontSize + delta * 0.1));
      document.documentElement.style.setProperty('--reader-font-size', fontSize + 'rem');
    }

    function setTheme(theme) { document.getElementById('appBody').className = theme; }

    function toggleFullScreen() {
      if (!document.fullscreenElement) document.documentElement.requestFullscreen();
      else if (document.exitFullscreen) document.exitFullscreen();
    }

    document.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowLeft') prevChapter();
      if (e.key === 'ArrowRight') nextChapter();
      if (e.key === 'f' || e.key === 'F') toggleFullScreen();
    });

    initReader();
  </script>
</body>
</html>
"""

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
import urllib.parse
from io import BytesIO
from flask import Flask, request, jsonify, send_file, Response, render_template_string

# 确保项目根目录在模块搜索路径中
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import config
import bookshelf_manager
import book_organizer

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

def background_worker(src, dst, action, skip_col, limit, delay, key, dry_run, threads=4):
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
    return jsonify(load_settings())

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

@app.route('/api/organize/start', methods=['POST'])
def api_organize_start():
    if task_manager.is_running:
        return jsonify({"success": False, "message": "已有任务正在执行中！"})

    data = request.json or {}
    src = data.get('src', '').strip()
    dst = data.get('dst', '').strip()
    action = data.get('action', 'copy')
    skip_col = bool(data.get('skip_collections', True))
    dry_run = bool(data.get('dry_run', False))
    limit_val = int(data.get('limit')) if data.get('limit') else None
    delay_val = float(data.get('delay', 1.2))
    key_val = data.get('google_key', '').strip() or None
    threads_val = max(2, min(20, int(data.get('threads', 4))))

    if not src or not os.path.exists(src):
        return jsonify({"success": False, "message": f"待整理源目录不存在: {src}"})
    if not dst:
        return jsonify({"success": False, "message": "未指定目标书库目录！"})

    task_manager.clear()
    task_manager.stop_event.clear()

    # 保存配置
    settings = load_settings()
    settings.update({
        "src": src, "dst": dst, "action": action,
        "skip_collections": skip_col, "delay": str(delay_val),
        "google_key": key_val or "", "limit": str(limit_val or "")
    })
    save_settings(settings)

    desc = "预演测试 (Dry-Run)" if dry_run else f"正式入库 ({action}模式)"
    task_manager.add_log(f"任务启动: {desc} | 源目录: {src} -> 目标库: {dst}", "heading")

    task_manager.worker = threading.Thread(
        target=background_worker,
        args=(src, dst, action, skip_col, limit_val, delay_val, key_val, dry_run, threads_val),
        daemon=True
    )
    task_manager.worker.start()

    return jsonify({"success": True, "message": "任务已启动"})

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
      <div class="form-row">
        <div class="form-label">请求延时与密钥:</div>
        <span style="font-size:0.85rem; color:var(--text-secondary);">延时(秒):</span>
        <input type="number" id="orgDelay" class="form-input" value="1.2" style="max-width: 80px;" step="0.1">
        <span style="font-size:0.85rem; color:var(--text-secondary); margin-left:14px;">数量限制:</span>
        <input type="number" id="orgLimit" class="form-input" placeholder="不限" style="max-width: 90px;">
        <span style="font-size:0.85rem; color:var(--text-secondary); margin-left:14px;">Google Key:</span>
        <input type="text" id="orgGoogleKey" class="form-input" placeholder="选填 (国内当当/豆瓣免Key全覆盖)">
        <span style="font-size:0.85rem; color:var(--text-secondary); margin-left:14px;">并发线程(2-20):</span>
        <input type="number" id="orgThreads" class="form-input" value="4" min="2" max="20" style="max-width: 70px;">
      </div>
    </div>

    <div style="display: flex; gap: 10px; margin-bottom: 14px;">
      <button class="btn-action btn-blue" id="btnDryRun" onclick="startOrganize(true)">🔍 预演测试 (Dry-Run)</button>
      <button class="btn-action btn-green" id="btnStart" onclick="startOrganize(false)">🚀 开始整理入库</button>
      <button class="btn-action btn-red" id="btnStop" onclick="stopOrganize()" disabled>⏹ 停止任务</button>
      <button class="btn-action btn-dark" style="margin-left: auto;" onclick="clearLogs()">🧹 清空日志</button>
    </div>

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
          <button class="btn-action btn-green" id="modalBtnRead" onclick="window.open('/read/' + activeBook.id, '_blank')">📖 在线阅读</button>
          <button class="btn-action btn-blue" id="modalBtnDownload" onclick="onModalDownload()">⬇️ 下载图书</button>
          <button class="btn-action btn-dark" id="modalBtnEdit" onclick="onModalEdit()">✏️ 编辑信息</button>
          <button class="btn-action btn-dark" id="modalBtnDouban" onclick="onModalDouban()">🔍 豆瓣检索</button>
          <button class="btn-action btn-red" id="modalBtnDelete" onclick="onModalDelete()">🗑️ 删除图书</button>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- 在线阅读器弹窗 -->
<div class="modal-overlay" id="readerModal">
  <div class="modal-card" style="max-width: 960px; height: 85vh; display: flex; flex-direction: column;">
    <button class="close-modal-btn" onclick="closeModal('readerModal')">×</button>
    <div style="font-size: 1.1rem; font-weight: 700; color: var(--accent-cyan); margin-bottom: 12px;" id="readerTitle">《书名》 - 在线阅读</div>
    <div style="display: flex; gap: 14px; flex: 1; overflow: hidden;">
      <div style="width: 220px; background: var(--bg-card); border: 1px solid var(--border); border-radius: 6px; overflow-y: auto; padding: 8px;" id="readerChapters"></div>
      <div style="flex: 1; background: var(--bg-card); border: 1px solid var(--border); border-radius: 6px; overflow-y: auto; padding: 20px; font-size: 1rem; line-height: 1.8; color: #e2e8f0;" id="readerContent"></div>
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

async function onModalRead() {
  if (!activeBook) return;
  closeModal('bookModal');
  document.getElementById('readerTitle').textContent = `《${activeBook.title}》 - 在线阅读`;
  openModal('readerModal');

  document.getElementById('readerChapters').innerHTML = '<div style="color:var(--text-muted); padding:10px;">正在加载正文...</div>';
  document.getElementById('readerContent').innerHTML = '<div style="color:var(--text-muted);">正在解析图书章节内容...</div>';

  try {
    const res = await fetch(`/api/preview/${activeBook.id}`);
    const data = await res.json();
    if (data.success && data.chapters.length > 0) {
      window._currentChapters = data.chapters;
      document.getElementById('readerChapters').innerHTML = data.chapters.map((c, i) => `
        <div style="padding: 6px 8px; border-radius: 4px; font-size: 0.82rem; cursor: pointer; margin-bottom: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;"
             class="reader-ch-item ${i===0?'active':''}" onclick="selectChapter(${i})">
          ${c.title}
        </div>
      `).join('');
      selectChapter(0);
    } else {
      document.getElementById('readerContent').innerHTML = '<div style="color:var(--danger);">未能提取到图书文本，请点击【下载图书】使用本地阅读器打开。</div>';
    }
  } catch (err) {
    document.getElementById('readerContent').innerHTML = `<div style="color:var(--danger);">加载失败: ${err}</div>`;
  }
}

function selectChapter(idx) {
  if (!window._currentChapters || !window._currentChapters[idx]) return;
  document.querySelectorAll('.reader-ch-item').forEach((el, i) => {
    el.style.background = (i === idx) ? 'var(--accent-teal)' : 'transparent';
    el.style.color = (i === idx) ? '#fff' : 'var(--text-primary)';
  });
  const ch = window._currentChapters[idx];
  document.getElementById('readerContent').innerHTML = `
    <h3 style="color:var(--accent-cyan); margin-bottom: 16px;">${ch.title}</h3>
    <div style="white-space: pre-wrap;">${ch.content}</div>
  `;
  document.getElementById('readerContent').scrollTop = 0;
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
async function startOrganize(dryRun) {
  const body = {
    src: document.getElementById('orgSrc').value.trim(),
    dst: document.getElementById('orgDst').value.trim(),
    action: document.querySelector('input[name="orgAction"]:checked').value,
    skip_collections: document.getElementById('orgSkipCol').checked,
    delay: document.getElementById('orgDelay').value,
    limit: document.getElementById('orgLimit').value,
    google_key: document.getElementById('orgGoogleKey').value.trim(),
    threads: document.getElementById('orgThreads').value,
    dry_run: dryRun
  };
  const res = await fetch('/api/organize/start', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body)
  });
  const data = await res.json();
  if (data.success) {
    document.getElementById('btnStart').disabled = true;
    document.getElementById('btnDryRun').disabled = true;
    document.getElementById('btnStop').disabled = false;
    startPolling();
  } else {
    alert(data.message);
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
      box.innerHTML = data.logs.map(l => {
        let cls = 'log-info';
        if (l.tag === 'heading') cls = 'log-heading';
        else if (l.tag === 'success') cls = 'log-success';
        else if (l.tag === 'skip' || l.tag === 'warning') cls = 'log-skip';
        else if (l.tag === 'error') cls = 'log-error';
        return `<div class="${cls}">[${l.time}] ${l.text}</div>`;
      }).join('');
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
  try {
    const sRes = await fetch('/api/settings');
    const settings = await sRes.json();
    if (settings.src) document.getElementById('orgSrc').value = settings.src;
    if (settings.dst) document.getElementById('orgDst').value = settings.dst;
    if (settings.delay) document.getElementById('orgDelay').value = settings.delay;
    if (settings.google_key) document.getElementById('orgGoogleKey').value = settings.google_key;
    if (settings.threads) document.getElementById('orgThreads').value = settings.threads;
    if (settings.limit) document.getElementById('orgLimit').value = settings.limit;
  } catch (e) {}
  loadBooks();
});
</script>
</body>
</html>
"""


@app.route('/read/<int:book_idx>')
def read_book_page(book_idx):
    return render_template_string(STANDALONE_READER_HTML, book_id=book_idx)
    )

@app.route('/')
def index():
    return render_template_string(INDEX_HTML)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 14808))
    print(f"Starting Book Organizer Web Server on http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)

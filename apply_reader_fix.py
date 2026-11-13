# -*- coding: utf-8 -*-
"""一键将独立阅读器无缝集成到图书系统，移除外链 CDN，Spine 正序极速秒开"""
import os
import re

WEB_APP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web_app.py")

NEW_READER_HTML = r'''STANDALONE_READER_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>沉浸阅读 - 智能图书管理系统</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    :root {
      --bg-base: #0f172a;
      --bg-side: #1e293b;
      --bg-card: #334155;
      --border: #475569;
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --accent: #38bdf8;
      --reader-bg: #0b0f19;
      --reader-text: #e2e8f0;
      --reader-font-size: 18px;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif; background: var(--bg-base); color: var(--text-main); height: 100vh; display: flex; flex-direction: column; overflow: hidden; }
    
    .topbar { height: 52px; background: var(--bg-side); border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; padding: 0 16px; flex-shrink: 0; z-index: 10; }
    .top-left { display: flex; align-items: center; gap: 12px; }
    .btn-back { color: var(--text-muted); text-decoration: none; font-size: 0.85rem; font-weight: 600; padding: 6px 12px; background: var(--bg-card); border: 1px solid var(--border); border-radius: 6px; transition: 0.2s; }
    .btn-back:hover { color: var(--accent); border-color: var(--accent); }
    .book-title { font-size: 1rem; font-weight: 700; color: var(--accent); max-width: 380px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .top-right { display: flex; align-items: center; gap: 8px; }
    .ctrl-btn { background: var(--bg-card); border: 1px solid var(--border); color: var(--text-main); border-radius: 6px; padding: 6px 12px; cursor: pointer; font-size: 0.85rem; transition: 0.2s; display: inline-flex; align-items: center; gap: 4px; }
    .ctrl-btn:hover { border-color: var(--accent); color: var(--accent); }
    .ctrl-btn.btn-koodo { background: rgba(56, 189, 248, 0.15); border-color: var(--accent); color: var(--accent); font-weight: 600; }

    .main-body { flex: 1; display: flex; overflow: hidden; position: relative; }
    
    .sidebar { width: 360px; background: var(--bg-side); border-right: 1px solid var(--border); display: flex; flex-direction: column; transition: margin-left 0.25s ease; flex-shrink: 0; }
    .sidebar.collapsed { margin-left: -360px; }
    .side-tabs { display: flex; border-bottom: 1px solid var(--border); background: var(--bg-base); }
    .side-tab { flex: 1; text-align: center; padding: 12px 0; font-size: 0.9rem; font-weight: 600; cursor: pointer; color: var(--text-muted); border-bottom: 2px solid transparent; }
    .side-tab.active { color: var(--accent); border-bottom-color: var(--accent); background: var(--bg-side); }
    .tab-content { flex: 1; overflow-y: auto; padding: 16px; display: none; }
    .tab-content.active { display: block; }

    .cover-box { text-align: center; margin-bottom: 14px; }
    .cover-box img { max-width: 140px; max-height: 200px; border-radius: 6px; box-shadow: 0 8px 24px rgba(0,0,0,0.5); }
    .detail-item { font-size: 0.85rem; margin-bottom: 8px; display: flex; gap: 6px; }
    .detail-label { color: var(--text-muted); width: 64px; flex-shrink: 0; }
    .detail-val { color: var(--text-main); font-weight: 500; word-break: break-all; }
    .detail-desc { margin-top: 12px; background: var(--bg-base); padding: 12px; border-radius: 6px; font-size: 0.85rem; line-height: 1.6; color: var(--text-muted); max-height: 220px; overflow-y: auto; border: 1px solid var(--border); }

    .toc-item { padding: 10px 12px; font-size: 0.88rem; border-radius: 6px; cursor: pointer; margin-bottom: 4px; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; border: 1px solid transparent; }
    .toc-item:hover { background: var(--bg-card); color: var(--text-main); }
    .toc-item.active { background: rgba(56, 189, 248, 0.15); border-color: var(--accent); color: var(--accent); font-weight: 600; }

    #viewerContainer { flex: 1; height: 100%; position: relative; background: var(--reader-bg); display: flex; flex-direction: column; overflow: hidden; }
    #readerContent { flex: 1; overflow-y: auto; padding: 40px 15% 60px; font-size: var(--reader-font-size); line-height: 2; color: var(--reader-text); }
    #readerContent p { margin-bottom: 1.4em; text-indent: 2em; }
    #readerContent img { max-width: 100%; height: auto; display: block; margin: 16px auto; border-radius: 4px; }

    .nav-arrow { position: absolute; top: 50%; transform: translateY(-50%); width: 44px; height: 80px; background: rgba(0,0,0,0.4); border: none; color: #fff; font-size: 1.8rem; cursor: pointer; display: flex; align-items: center; justify-content: center; border-radius: 6px; z-index: 5; opacity: 0; transition: opacity 0.2s, background 0.2s; }
    #viewerContainer:hover .nav-arrow { opacity: 0.7; }
    .nav-arrow:hover { opacity: 1 !important; background: var(--accent) !important; color: #000; }
    .arrow-left { left: 16px; }
    .arrow-right { right: 16px; }

    .footer-bar { height: 42px; background: var(--bg-side); border-top: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; padding: 0 20px; flex-shrink: 0; font-size: 0.82rem; color: var(--text-muted); }
  </style>
</head>
<body>

  <div class="topbar">
    <div class="top-left">
      <a href="/" class="btn-back">← 返回书库</a>
      <button class="ctrl-btn" onclick="toggleSidebar()">
        <span id="toggleText">折叠详情</span>
      </button>
      <div class="book-title" id="bookTitle">正在加载图书...</div>
      <span style="background:rgba(56,189,248,0.15); color:var(--accent); border:1px solid rgba(56,189,248,0.3); padding:2px 8px; border-radius:10px; font-size:0.75rem; font-weight:600;">v2.6.0</span>
    </div>
    <div class="top-right">
      <button class="ctrl-btn" onclick="changeFontSize(-2)">A-</button>
      <button class="ctrl-btn" onclick="changeFontSize(2)">A+</button>
      <button class="ctrl-btn" onclick="setTheme('dark')">🌙 暗黑</button>
      <button class="ctrl-btn" onclick="setTheme('sepia')">📜 羊皮纸</button>
      <button class="ctrl-btn" onclick="setTheme('light')">☀️ 浅色</button>
      <button class="ctrl-btn" onclick="toggleFullScreen()">⛶ 全屏</button>
      <a id="btnKoodo" href="/koodo/" target="_blank" class="ctrl-btn btn-koodo">📖 Koodo 阅读器</a>
      <a id="btnDownload" href="#" class="ctrl-btn" style="text-decoration:none;" target="_blank">📥 导出</a>
    </div>
  </div>

  <div class="main-body">
    <div class="sidebar" id="sidebar">
      <div class="side-tabs">
        <div class="side-tab active" onclick="switchSideTab(0)">📑 目录大纲</div>
        <div class="side-tab" onclick="switchSideTab(1)">ℹ️ 书籍详情</div>
      </div>
      
      <div class="tab-content active" id="tabToc">
        <div style="padding:20px; color:var(--text-muted); text-align:center;">正在提取原书目录...</div>
      </div>

      <div class="tab-content" id="tabDetail">
        <div class="cover-box">
          <img id="detCover" src="" alt="封面" style="display:none;">
          <div id="detFallbackCover" style="width:130px; height:180px; background:var(--bg-card); display:inline-flex; align-items:center; justify-content:center; border-radius:6px; font-size:2.2rem;">📖</div>
        </div>
        <div class="detail-item"><span class="detail-label">书名:</span><span class="detail-val" id="detTitle">-</span></div>
        <div class="detail-item"><span class="detail-label">作者:</span><span class="detail-val" id="detAuthor">-</span></div>
        <div class="detail-item"><span class="detail-label">ISBN:</span><span class="detail-val" id="detIsbn">-</span></div>
        <div class="detail-item"><span class="detail-label">出版社:</span><span class="detail-val" id="detPublisher">-</span></div>
        <div class="detail-item"><span class="detail-label">出版年:</span><span class="detail-val" id="detYear">-</span></div>
        <div class="detail-desc" id="detDesc">暂无图书简介。</div>
      </div>
    </div>

    <div id="viewerContainer">
      <button class="nav-arrow arrow-left" onclick="prevChapter()" title="上一章">‹</button>
      <div id="readerContent">正在加载正文...</div>
      <button class="nav-arrow arrow-right" onclick="nextChapter()" title="下一章">›</button>
    </div>
  </div>

  <div class="footer-bar">
    <div id="statusChapter">正在载入...</div>
    <div id="statusProgress">进度计算中...</div>
    <div>提示：按键盘 ← / → 方向键切换章节，F 键进入全屏</div>
  </div>

  <script>
    const bookId = {{ book_id }};
    let currentChapter = 0;
    let totalChapters = 0;
    let chaptersData = [];
    let currentFontSize = 18;

    async function init() {
      document.getElementById('btnDownload').href = `/api/download/${bookId}`;
      document.getElementById('btnKoodo').href = `/koodo/index.html#/manager/empty?file=${encodeURIComponent(window.location.origin + '/api/download/' + bookId)}`;

      try {
        const tocRes = await fetch(`/api/book/${bookId}/toc`);
        const tocJson = await tocRes.json();
        if (tocJson.success) {
          const b = tocJson.book;
          document.title = `《${b.title}》- 沉浸阅读`;
          document.getElementById('bookTitle').textContent = `《${b.title}》 - ${b.author || '未知作者'}`;
          document.getElementById('detTitle').textContent = b.title;
          document.getElementById('detAuthor').textContent = b.author || '未知作者';
          document.getElementById('detIsbn').textContent = b.isbn || '无';
          document.getElementById('detPublisher').textContent = b.publisher || '未知出版社';
          document.getElementById('detYear').textContent = b.pub_year || '未知年份';
          if (b.description) document.getElementById('detDesc').textContent = b.description;
          if (b.cover_path) {
            const img = document.getElementById('detCover');
            img.src = `/api/cover/${b.id}`;
            img.style.display = 'inline-block';
            document.getElementById('detFallbackCover').style.display = 'none';
          }

          chaptersData = tocJson.toc || [];
          totalChapters = chaptersData.length;
          renderToc();
          loadChapter(0);
        } else {
          document.getElementById('readerContent').innerHTML = `<div style="color:#ef4444; padding:30px;">加载书籍失败: ${tocJson.error || '未知错误'}</div>`;
        }
      } catch (e) {
        document.getElementById('readerContent').innerHTML = `<div style="color:#ef4444; padding:30px;">无法连接服务器读取书籍大纲</div>`;
      }
    }

    function renderToc() {
      const tab = document.getElementById('tabToc');
      if (chaptersData.length === 0) {
        tab.innerHTML = '<div style="padding:20px; color:var(--text-muted); text-align:center;">原书未内置目录大纲</div>';
        return;
      }
      tab.innerHTML = chaptersData.map((item, idx) => `
        <div class="toc-item ${idx === currentChapter ? 'active' : ''}" id="tocItem_${idx}" onclick="loadChapter(${idx})" title="${item.title}">
          ${idx + 1}. ${item.title}
        </div>
      `).join('');
    }

    async function loadChapter(idx) {
      if (idx < 0 || (totalChapters > 0 && idx >= totalChapters)) return;
      currentChapter = idx;
      
      document.querySelectorAll('.toc-item').forEach((el, i) => {
        el.classList.toggle('active', i === currentChapter);
      });
      const activeEl = document.getElementById(`tocItem_${currentChapter}`);
      if (activeEl) activeEl.scrollIntoView({ block: 'nearest', behavior: 'smooth' });

      const title = chaptersData[idx] ? chaptersData[idx].title : `第 ${idx + 1} 节`;
      document.getElementById('statusChapter').textContent = `当前章节：${title}`;
      const pct = totalChapters > 0 ? Math.round(((idx + 1) / totalChapters) * 100) : 0;
      document.getElementById('statusProgress').textContent = `阅读进度：${pct}% (${idx + 1}/${totalChapters})`;

      const container = document.getElementById('readerContent');
      container.scrollTop = 0;
      container.innerHTML = `<div style="color:var(--text-muted); padding:30px; text-align:center;">正在解压并呈现正文...</div>`;

      try {
        const res = await fetch(`/api/book/${bookId}/chapter/${idx}`);
        const data = await res.json();
        if (data.success) {
          container.innerHTML = data.content;
        } else {
          container.innerHTML = `<div style="color:#ef4444; padding:30px;">无法加载章节正文: ${data.error}</div>`;
        }
      } catch (e) {
        container.innerHTML = `<div style="color:#ef4444; padding:30px;">加载章节超时或网络错误</div>`;
      }
    }

    function prevChapter() { if (currentChapter > 0) loadChapter(currentChapter - 1); }
    function nextChapter() { if (currentChapter < totalChapters - 1) loadChapter(currentChapter + 1); }

    function changeFontSize(delta) {
      currentFontSize = Math.max(14, Math.min(32, currentFontSize + delta));
      document.documentElement.style.setProperty('--reader-font-size', `${currentFontSize}px`);
    }

    function setTheme(theme) {
      if (theme === 'dark') {
        document.documentElement.style.setProperty('--reader-bg', '#0b0f19');
        document.documentElement.style.setProperty('--reader-text', '#e2e8f0');
      } else if (theme === 'sepia') {
        document.documentElement.style.setProperty('--reader-bg', '#f4ecd8');
        document.documentElement.style.setProperty('--reader-text', '#3f3122');
      } else if (theme === 'light') {
        document.documentElement.style.setProperty('--reader-bg', '#ffffff');
        document.documentElement.style.setProperty('--reader-text', '#1e293b');
      }
    }

    function toggleSidebar() {
      const side = document.getElementById('sidebar');
      const collapsed = side.classList.toggle('collapsed');
      document.getElementById('toggleText').textContent = collapsed ? '展开详情' : '折叠详情';
    }

    function switchSideTab(idx) {
      document.querySelectorAll('.side-tab').forEach((el, i) => el.classList.toggle('active', i === idx));
      document.getElementById('tabToc').classList.toggle('active', idx === 0);
      document.getElementById('tabDetail').classList.toggle('active', idx === 1);
    }

    function toggleFullScreen() {
      if (!document.fullscreenElement) document.documentElement.requestFullscreen();
      else if (document.exitFullscreen) document.exitFullscreen();
    }

    document.addEventListener("keydown", e => {
      if (e.key === "ArrowLeft") prevChapter();
      if (e.key === "ArrowRight") nextChapter();
      if (e.key === "f" || e.key === "F") toggleFullScreen();
    });

    init();
  </script>
</body>
</html>
"""
'''

with open(WEB_APP_PATH, "r", encoding="utf-8") as f:
    content = f.read()

pattern = r'STANDALONE_READER_HTML\s*=\s*"""<!DOCTYPE html>.*?"""'
if re.search(pattern, content, re.DOTALL):
    updated = re.sub(pattern, NEW_READER_HTML.strip(), content, count=1, flags=re.DOTALL)
    with open(WEB_APP_PATH, "w", encoding="utf-8") as f:
        f.write(updated)
    print("✅ 成功替换 web_app.py 中的 STANDALONE_READER_HTML！")
else:
    print("⚠️ 未正则匹配到原始块，正在做首尾锚点替换...")
    start_pos = content.find("STANDALONE_READER_HTML =")
    end_pos = content.find('"""\n\nfrom version import', start_pos)
    if start_pos != -1 and end_pos != -1:
        updated = content[:start_pos] + NEW_READER_HTML.strip() + content[end_pos+3:]
        with open(WEB_APP_PATH, "w", encoding="utf-8") as f:
            f.write(updated)
        print("✅ 锚点替换成功！")
    else:
        print("❌ 无法定位块，请检查文件。")

import py_compile
py_compile.compile(WEB_APP_PATH, doraise=True)
print("🎉 语法检查 100% 通过！")
# -*- coding: utf-8 -*-
"""
Book Organizer GUI - 智能图书整理与现代视觉书架系统 (Z-Library 风格画廊)
"""
import os
import sys
import json
import threading
import queue
import webbrowser
import subprocess
import urllib.parse

# 修复打包环境下 ssl 缺少 codex-rejected-cas.pem 导致的 [Errno 2] 崩溃
try:
    import ssl
    _orig_ssl_new = ssl.SSLContext.__new__
    def _safe_ssl_context_new(cls, *args, **kwargs):
        try:
            return _orig_ssl_new(cls, *args, **kwargs)
        except FileNotFoundError:
            return ssl._SSLContext.__new__(cls, *args, **kwargs)
    ssl.SSLContext.__new__ = _safe_ssl_context_new

    if getattr(sys, 'frozen', False):
        try:
            meipass = getattr(sys, '_MEIPASS', '')
            if meipass:
                pem_path = os.path.join(meipass, 'codex-rejected-cas.pem')
                if not os.path.exists(pem_path):
                    with open(pem_path, 'wb') as f:
                        pass
        except Exception:
            pass
except Exception:
    pass


# 处理打包与非打包状态下的 Tcl/Tk 路径，避免缺失库
if getattr(sys, 'frozen', False):
    bundle_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(sys.executable)))
    for cand in [
        os.path.join(bundle_dir, '_tcl_data'),
        os.path.join(bundle_dir, 'tcl', 'tcl8.6'),
        os.path.join(bundle_dir, 'tcl8.6'),
    ]:
        if os.path.isdir(cand):
            os.environ['TCL_LIBRARY'] = cand
            break
    for cand in [
        os.path.join(bundle_dir, '_tk_data'),
        os.path.join(bundle_dir, 'tcl', 'tk8.6'),
        os.path.join(bundle_dir, 'tk8.6'),
    ]:
        if os.path.isdir(cand):
            os.environ['TK_LIBRARY'] = cand
            break
else:
    base_tcl = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tcl")
    if not os.path.exists(os.path.join(base_tcl, "tcl8.6")):
        base_tcl = r"D:\图书管理\tcl"
    if os.path.exists(os.path.join(base_tcl, "tcl8.6")):
        os.environ.setdefault("TCL_LIBRARY", os.path.join(base_tcl, "tcl8.6"))
        os.environ.setdefault("TK_LIBRARY", os.path.join(base_tcl, "tk8.6"))

try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        import ctypes
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from PIL import Image, ImageTk

import config
import book_organizer
import bookshelf_manager

THEME = {
    'bg_app': '#131722',
    'bg_header': '#10141d',
    'bg_panel': '#181d28',
    'bg_card': '#1e2433',
    'bg_card_hover': '#252e42',
    'bg_input': '#11151f',
    'border': '#293245',
    'border_hover': '#38bdf8',
    'accent_cyan': '#38bdf8',
    'accent_teal': '#0891b2',
    'accent_green': '#10b981',
    'text_primary': '#f8fafc',
    'text_secondary': '#94a3b8',
    'text_muted': '#64748b',
}

def get_settings_file_paths():
    paths = []
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        exe_dir = os.path.dirname(os.path.abspath(__file__))
    paths.append(os.path.join(exe_dir, "settings.json"))

    appdata = os.environ.get('APPDATA')
    if appdata:
        app_dir = os.path.join(appdata, 'BookOrganizer')
        paths.append(os.path.join(app_dir, "settings.json"))
    return paths

def load_settings():
    for p in get_settings_file_paths():
        if os.path.exists(p):
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception:
                pass
    return {}

def save_settings(settings_dict):
    paths = get_settings_file_paths()
    for p in paths:
        try:
            parent = os.path.dirname(p)
            if parent and not os.path.exists(parent):
                os.makedirs(parent, exist_ok=True)
            with open(p, 'w', encoding='utf-8') as f:
                json.dump(settings_dict, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            continue
    return False

class BookOrganizerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("📚 智能图书整理与书架管理系统 (Z-Library 视觉画廊)")
        self.root.geometry("1200x820")
        self.root.minsize(1050, 700)
        self.root.configure(bg=THEME['bg_app'])

        self.saved_settings = load_settings()

        self.books = []
        self.filtered_books = []
        self.selected_book = None
        self.view_mode = "grid"
        self.card_widgets = []
        self.photo_refs = []
        self.current_cols = 0

        self.msg_queue = queue.Queue()
        self.is_running = False
        self.stop_event = threading.Event()
        self.worker = None

        self.stats = {
            'total': 0, 'organized': 0, 'col_skip': 0, 'no_isbn': 0, 'error': 0
        }

        self.font_title = ("Microsoft YaHei UI", 15, "bold")
        self.font_sub = ("Microsoft YaHei UI", 9)
        self.font_bold = ("Microsoft YaHei UI", 9, "bold")
        self.font_normal = ("Microsoft YaHei UI", 9)
        self.font_mono = ("Consolas", 9)

        self.center_window(1200, 820)
        self.setup_styles()
        self.create_widgets()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.after(100, self.process_queue)
        self.root.after(150, self.refresh_bookshelf)

    def center_window(self, width, height):
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = max(0, (sw - width) // 2)
        y = max(0, (sh - height) // 2 - 20)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def setup_styles(self):
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except Exception:
            pass

        style.configure('Main.TNotebook', background=THEME['bg_app'], borderwidth=0)
        style.configure(
            'Main.TNotebook.Tab',
            padding=[22, 9],
            font=('Microsoft YaHei UI', 10, 'bold'),
            background='#1a202c',
            foreground='#94a3b8',
            borderwidth=0
        )
        style.map(
            'Main.TNotebook.Tab',
            background=[('selected', THEME['bg_panel'])],
            foreground=[('selected', THEME['accent_cyan'])]
        )

        style.configure(
            "Dark.Treeview",
            font=self.font_normal,
            rowheight=30,
            background=THEME['bg_panel'],
            foreground=THEME['text_primary'],
            fieldbackground=THEME['bg_panel'],
            borderwidth=0
        )
        style.configure(
            "Dark.Treeview.Heading",
            font=self.font_bold,
            padding=[6, 6],
            background='#232a3b',
            foreground=THEME['text_primary']
        )
        style.map(
            "Dark.Treeview",
            background=[('selected', '#0284c7')],
            foreground=[('selected', '#ffffff')]
        )

        style.configure(
            "Green.Horizontal.TProgressbar",
            troughcolor=THEME['bg_input'],
            background=THEME['accent_cyan'],
            thickness=6
        )

    def create_widgets(self):
        banner = tk.Frame(self.root, bg=THEME['bg_header'], height=60, padx=20)
        banner.pack(fill=tk.X, side=tk.TOP)
        banner.pack_propagate(False)

        top_left = tk.Frame(banner, bg=THEME['bg_header'])
        top_left.pack(side=tk.LEFT, fill=tk.Y)

        lbl_logo = tk.Label(
            top_left,
            text="📚 MY BOOKSHELF",
            font=("Segoe UI", 13, "bold"),
            fg=THEME['accent_cyan'],
            bg=THEME['bg_header']
        )
        lbl_logo.pack(anchor="w", pady=(10, 0))

        lbl_motto = tk.Label(
            top_left,
            text="您通往知识和文化的书架 · 随时随地 尽享阅读",
            font=self.font_sub,
            fg=THEME['text_secondary'],
            bg=THEME['bg_header']
        )
        lbl_motto.pack(anchor="w", pady=(1, 0))

        self.notebook = ttk.Notebook(self.root, style='Main.TNotebook')
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=14, pady=(6, 8))

        self.tab_bookshelf = tk.Frame(self.notebook, bg=THEME['bg_app'], padx=10, pady=10)
        self.notebook.add(self.tab_bookshelf, text="  🖼️ 我的书架 (画廊)  ")

        self.tab_organizer = tk.Frame(self.notebook, bg=THEME['bg_panel'], padx=16, pady=14)
        self.notebook.add(self.tab_organizer, text="  ⚙️ 图书整理 (入库)  ")

        self.create_bookshelf_tab_widgets(self.tab_bookshelf)
        self.create_organizer_tab_widgets(self.tab_organizer)

        saved_tab = self.saved_settings.get("active_tab", 0)
        try:
            self.notebook.select(int(saved_tab))
        except Exception:
            pass

    def create_bookshelf_tab_widgets(self, parent):
        tool_frame = tk.Frame(parent, bg=THEME['bg_panel'], bd=1, relief=tk.SOLID, padx=16, pady=12)
        tool_frame.pack(fill=tk.X, pady=(0, 10))

        fmt_bar = tk.Frame(tool_frame, bg=THEME['bg_panel'])
        fmt_bar.pack(fill=tk.X, pady=(0, 8))

        self.shelf_format_filter = tk.StringVar(value="全部")
        formats = [("全部图书", "全部"), ("EPUB", "EPUB"), ("PDF", "PDF"), ("MOBI", "MOBI"), ("AZW3", "AZW3"), ("TXT", "TXT")]
        self.fmt_btns = {}

        for lbl, val in formats:
            btn = tk.Button(
                fmt_bar,
                text=lbl,
                font=self.font_bold,
                bg='#232a3b' if val != "全部" else THEME['accent_teal'],
                fg='#ffffff',
                activebackground=THEME['accent_cyan'],
                activeforeground='#ffffff',
                relief=tk.FLAT,
                padx=14,
                pady=3,
                cursor="hand2",
                command=lambda v=val: self.switch_format_filter(v)
            )
            btn.pack(side=tk.LEFT, padx=(0, 6))
            self.fmt_btns[val] = btn

        btn_refresh = tk.Button(
            fmt_bar,
            text="🔄 刷新书架",
            bg='#232a3b',
            fg=THEME['accent_cyan'],
            font=self.font_bold,
            relief=tk.FLAT,
            padx=12,
            pady=3,
            cursor="hand2",
            command=self.refresh_bookshelf
        )
        btn_refresh.pack(side=tk.RIGHT, padx=(6, 0))

        btn_ch_dir = tk.Button(
            fmt_bar,
            text="📂 切换书库目录...",
            bg='#232a3b',
            fg=THEME['text_primary'],
            font=self.font_normal,
            relief=tk.FLAT,
            padx=12,
            pady=3,
            cursor="hand2",
            command=self.browse_shelf_dir
        )
        btn_ch_dir.pack(side=tk.RIGHT, padx=3)

        btn_open_folder = tk.Button(
            fmt_bar,
            text="📁 打开文件夹",
            bg='#232a3b',
            fg=THEME['text_primary'],
            font=self.font_normal,
            relief=tk.FLAT,
            padx=10,
            pady=3,
            cursor="hand2",
            command=lambda: self.open_dir(self.shelf_dir_var.get())
        )
        btn_open_folder.pack(side=tk.RIGHT, padx=3)

        search_row = tk.Frame(tool_frame, bg=THEME['bg_panel'])
        search_row.pack(fill=tk.X, pady=(2, 0))

        search_box_wrapper = tk.Frame(search_row, bg=THEME['bg_input'], bd=1, relief=tk.SOLID)
        search_box_wrapper.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.shelf_search_var = tk.StringVar()
        self.shelf_search_var.trace_add("write", lambda *args: self.filter_bookshelf())

        self.search_entry = tk.Entry(
            search_box_wrapper,
            textvariable=self.shelf_search_var,
            font=("Microsoft YaHei UI", 11),
            bg=THEME['bg_input'],
            fg=THEME['text_primary'],
            insertbackground=THEME['accent_cyan'],
            relief=tk.FLAT,
            bd=0
        )
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=12, pady=7)

        btn_clear = tk.Button(
            search_box_wrapper,
            text="✖",
            font=self.font_bold,
            bg=THEME['bg_input'],
            fg=THEME['text_muted'],
            activebackground=THEME['bg_input'],
            activeforeground=THEME['text_primary'],
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            command=lambda: self.shelf_search_var.set("")
        )
        btn_clear.pack(side=tk.LEFT, padx=6)

        btn_search_icon = tk.Button(
            search_row,
            text="  🔍 搜索  ",
            font=self.font_bold,
            bg=THEME['accent_teal'],
            fg='#ffffff',
            activebackground=THEME['accent_cyan'],
            activeforeground='#ffffff',
            relief=tk.FLAT,
            padx=16,
            pady=6,
            cursor="hand2",
            command=self.filter_bookshelf
        )
        btn_search_icon.pack(side=tk.LEFT, padx=(8, 0))

        section_bar = tk.Frame(parent, bg=THEME['bg_app'])
        section_bar.pack(fill=tk.X, pady=(4, 8))

        lbl_section_title = tk.Label(
            section_bar,
            text="为您收藏的图书",
            font=("Microsoft YaHei UI", 13, "bold"),
            fg=THEME['accent_cyan'],
            bg=THEME['bg_app']
        )
        lbl_section_title.pack(side=tk.LEFT, padx=(2, 10))

        self.lbl_shelf_status = tk.Label(
            section_bar,
            text="在当前书库中探索已整理图书",
            font=self.font_normal,
            fg=THEME['text_secondary'],
            bg=THEME['bg_app']
        )
        self.lbl_shelf_status.pack(side=tk.LEFT)

        view_box = tk.Frame(section_bar, bg=THEME['bg_app'])
        view_box.pack(side=tk.RIGHT)

        self.btn_view_grid = tk.Button(
            view_box,
            text="🖼️ 封面画廊",
            font=self.font_bold,
            bg=THEME['accent_teal'],
            fg='#ffffff',
            relief=tk.FLAT,
            padx=10,
            pady=3,
            cursor="hand2",
            command=lambda: self.switch_view_mode("grid")
        )
        self.btn_view_grid.pack(side=tk.LEFT, padx=2)

        self.btn_view_list = tk.Button(
            view_box,
            text="📋 详细列表",
            font=self.font_bold,
            bg='#232a3b',
            fg=THEME['text_secondary'],
            relief=tk.FLAT,
            padx=10,
            pady=3,
            cursor="hand2",
            command=lambda: self.switch_view_mode("list")
        )
        self.btn_view_list.pack(side=tk.LEFT, padx=2)

        self.grid_container = tk.Frame(parent, bg=THEME['bg_app'])
        self.grid_container.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(
            self.grid_container,
            bg=THEME['bg_app'],
            highlightthickness=0,
            borderwidth=0
        )
        self.grid_scrollbar = ttk.Scrollbar(self.grid_container, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.grid_scrollbar.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.grid_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.grid_frame = tk.Frame(self.canvas, bg=THEME['bg_app'])
        self.canvas_window = self.canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")

        self.grid_frame.bind("<Configure>", self.on_frame_configure)
        self.canvas.bind("<Configure>", self.on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self.on_mousewheel)

        self.list_container = tk.Frame(parent, bg=THEME['bg_panel'])

        columns = ("index", "title", "author", "format", "size", "isbn", "publisher", "pubdate")
        self.shelf_tree = ttk.Treeview(
            self.list_container,
            columns=columns,
            show="headings",
            style="Dark.Treeview",
            selectmode="browse"
        )
        col_defs = [
            ("index", "#", 45, "center"),
            ("title", "书名", 280, "w"),
            ("author", "作者", 140, "w"),
            ("format", "格式", 60, "center"),
            ("size", "大小", 80, "e"),
            ("isbn", "ISBN", 130, "center"),
            ("publisher", "出版社", 120, "w"),
            ("pubdate", "出版日期", 90, "center"),
        ]
        for cid, cname, cwidth, canchor in col_defs:
            self.shelf_tree.heading(cid, text=cname)
            self.shelf_tree.column(cid, width=cwidth, anchor=canchor)

        tree_v = ttk.Scrollbar(self.list_container, orient=tk.VERTICAL, command=self.shelf_tree.yview)
        self.shelf_tree.configure(yscrollcommand=tree_v.set)
        self.shelf_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_v.pack(side=tk.RIGHT, fill=tk.Y)

        self.shelf_tree.bind("<Double-1>", lambda e: self.open_tree_selected_book())
        self.shelf_tree.bind("<Return>", lambda e: self.open_tree_selected_book())
        self.shelf_tree.bind("<Button-3>", self.show_tree_context_menu)

        self.shelf_menu = tk.Menu(self.root, tearoff=0, bg=THEME['bg_panel'], fg=THEME['text_primary'], activebackground=THEME['accent_teal'])
        self.shelf_menu.add_command(label="📖 立即打开观看 (默认阅读器)", command=self.open_selected_book)
        self.shelf_menu.add_command(label="📄 内置快速试读 (章节预览)", command=self.open_builtin_preview)
        self.shelf_menu.add_command(label="📁 在资源管理器中定位文件", command=self.open_selected_folder)
        self.shelf_menu.add_separator()
        self.shelf_menu.add_command(label="🔍 在豆瓣读书中检索", command=self.search_douban)
        self.shelf_menu.add_command(label="🔍 在谷歌图书中检索", command=self.search_google)
        self.shelf_menu.add_separator()
        self.shelf_menu.add_command(label="📋 复制书名", command=self.copy_shelf_title)
        self.shelf_menu.add_command(label="📋 复制ISBN", command=self.copy_shelf_isbn)
        self.shelf_menu.add_separator()
        self.shelf_menu.add_command(label="✏️ 编辑图书元数据...", command=self.edit_selected_metadata)
        self.shelf_menu.add_command(label="🗑️ 从书架彻底删除图书...", command=self.delete_selected_book)

        init_shelf_dir = str(self.saved_settings.get("bookshelf_dir") or self.saved_settings.get("dst") or config.DEFAULT_DST_DIR)
        self.shelf_dir_var = tk.StringVar(value=init_shelf_dir)

    def on_frame_configure(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def on_canvas_configure(self, event):
        canvas_width = event.width
        self.canvas.itemconfig(self.canvas_window, width=canvas_width)
        card_w = 168
        margin = 16
        cols = max(2, (canvas_width - margin) // (card_w + margin))
        if cols != self.current_cols:
            self.current_cols = cols
            self.relayout_grid()

    def on_mousewheel(self, event):
        if self.view_mode == "grid":
            try:
                self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except Exception:
                pass

    def switch_format_filter(self, val):
        self.shelf_format_filter.set(val)
        for k, btn in self.fmt_btns.items():
            if k == val:
                btn.config(bg=THEME['accent_teal'], fg='#ffffff')
            else:
                btn.config(bg='#232a3b', fg='#ffffff')
        self.filter_bookshelf()

    def switch_view_mode(self, mode):
        self.view_mode = mode
        if mode == "grid":
            self.btn_view_grid.config(bg=THEME['accent_teal'], fg='#ffffff')
            self.btn_view_list.config(bg='#232a3b', fg=THEME['text_secondary'])
            self.list_container.pack_forget()
            self.grid_container.pack(fill=tk.BOTH, expand=True)
            self.relayout_grid()
        else:
            self.btn_view_list.config(bg=THEME['accent_teal'], fg='#ffffff')
            self.btn_view_grid.config(bg='#232a3b', fg=THEME['text_secondary'])
            self.grid_container.pack_forget()
            self.list_container.pack(fill=tk.BOTH, expand=True)
            self.render_list_view()

    def browse_shelf_dir(self):
        curr = self.shelf_dir_var.get()
        init_dir = curr if os.path.exists(curr) else os.getcwd()
        path = filedialog.askdirectory(title="选择书库目录", initialdir=init_dir)
        if path:
            norm_p = os.path.normpath(path)
            self.shelf_dir_var.set(norm_p)
            self.save_current_settings()
            self.refresh_bookshelf()

    def refresh_bookshelf(self):
        target_dir = self.shelf_dir_var.get().strip()
        if not target_dir or not os.path.isdir(target_dir):
            self.lbl_shelf_status.config(text="未设置有效书库目录，请点击上方【切换书库目录】")
            self.books = []
            self.filtered_books = []
            self.render_cover_grid()
            return

        self.lbl_shelf_status.config(text="正在加载书架藏书...")
        self.root.update_idletasks()

        self.books = bookshelf_manager.scan_library(target_dir)
        self.filter_bookshelf()

    def filter_bookshelf(self):
        keyword = self.shelf_search_var.get().strip().lower()
        fmt_filter = self.shelf_format_filter.get().strip().upper()

        matched = []
        for b in self.books:
            if fmt_filter != "全部":
                if b.format != fmt_filter:
                    continue
            if keyword:
                combined = f"{b.title} {b.author} {b.publisher} {b.isbn}".lower()
                if keyword not in combined:
                    continue
            matched.append(b)

        self.filtered_books = matched
        total_sz = bookshelf_manager.format_file_size(sum(b.file_size for b in matched))
        count = len(matched)
        tot_count = len(self.books)

        if count == tot_count:
            self.lbl_shelf_status.config(text=f"在 当前书库 中探索 {count} 本图书 · 总大小: {total_sz}")
        else:
            self.lbl_shelf_status.config(text=f"筛选结果: {count} / {tot_count} 本 · 大小: {total_sz}")

        if self.view_mode == "grid":
            self.render_cover_grid()
        else:
            self.render_list_view()

    def render_cover_grid(self):
        for widget in self.grid_frame.winfo_children():
            widget.destroy()
        self.card_widgets.clear()
        self.photo_refs.clear()

        if not self.filtered_books:
            empty_box = tk.Frame(self.grid_frame, bg=THEME['bg_app'], pady=80)
            empty_box.pack(fill=tk.BOTH, expand=True)
            tk.Label(empty_box, text="📭", font=("Segoe UI", 48), fg=THEME['text_muted'], bg=THEME['bg_app']).pack()
            tk.Label(empty_box, text="书架暂无符合条件的图书", font=self.font_title, fg=THEME['text_primary'], bg=THEME['bg_app']).pack(pady=(10, 4))
            tk.Label(empty_box, text="请尝试切换筛选格式、清空搜索框，或前往【图书整理】标签页导入新书！", font=self.font_normal, fg=THEME['text_secondary'], bg=THEME['bg_app']).pack(pady=(0, 16))
            btn_goto_org = tk.Button(
                empty_box,
                text="🚀 前往整理图书入库",
                font=self.font_bold,
                bg=THEME['accent_teal'],
                fg='#ffffff',
                relief=tk.FLAT,
                padx=16,
                pady=6,
                cursor="hand2",
                command=lambda: self.notebook.select(self.tab_organizer)
            )
            btn_goto_org.pack()
            return

        cols = self.current_cols if self.current_cols > 0 else 4

        for idx, book in enumerate(self.filtered_books):
            card = self.create_book_card(self.grid_frame, book)
            r = idx // cols
            c = idx % cols
            card.grid(row=r, column=c, padx=10, pady=12, sticky="n")
            self.card_widgets.append((card, r, c))

        self.on_frame_configure()

    def relayout_grid(self):
        if not self.card_widgets or self.current_cols <= 0:
            return
        cols = self.current_cols
        for idx, (card, _, _) in enumerate(self.card_widgets):
            r = idx // cols
            c = idx % cols
            card.grid(row=r, column=c, padx=10, pady=12, sticky="n")
        self.on_frame_configure()

    def create_book_card(self, parent, book):
        card = tk.Frame(
            parent,
            bg=THEME['bg_card'],
            bd=1,
            relief=tk.SOLID,
            highlightthickness=1,
            highlightbackground=THEME['border'],
            highlightcolor=THEME['border_hover'],
            padx=7,
            pady=7,
            cursor="hand2"
        )

        badge_txt = book.format if book.format else "阅读"
        pil_thumb = bookshelf_manager.make_zlib_thumbnail(
            book.cover_path,
            book.title,
            book.author,
            badge_text=badge_txt,
            target_size=(150, 218)
        )
        photo = ImageTk.PhotoImage(pil_thumb)
        self.photo_refs.append(photo)

        cover_lbl = tk.Label(card, image=photo, bg=THEME['bg_card'], bd=0)
        cover_lbl.pack(side=tk.TOP)

        short_title = book.title if len(book.title) <= 22 else (book.title[:20] + "...")
        title_lbl = tk.Label(
            card,
            text=short_title,
            font=("Microsoft YaHei UI", 9, "bold"),
            fg=THEME['text_primary'],
            bg=THEME['bg_card'],
            wraplength=148,
            justify=tk.LEFT,
            anchor="w"
        )
        title_lbl.pack(fill=tk.X, pady=(6, 1))

        short_author = book.author if len(book.author) <= 14 else (book.author[:13] + "...")
        author_lbl = tk.Label(
            card,
            text=short_author,
            font=("Microsoft YaHei UI", 8),
            fg=THEME['text_secondary'],
            bg=THEME['bg_card'],
            anchor="w",
            justify=tk.LEFT
        )
        author_lbl.pack(fill=tk.X, pady=(0, 2))

        def on_enter(e):
            card.config(highlightbackground=THEME['border_hover'], bg=THEME['bg_card_hover'])
            cover_lbl.config(bg=THEME['bg_card_hover'])
            title_lbl.config(bg=THEME['bg_card_hover'], fg=THEME['accent_cyan'])
            author_lbl.config(bg=THEME['bg_card_hover'])

        def on_leave(e):
            card.config(highlightbackground=THEME['border'], bg=THEME['bg_card'])
            cover_lbl.config(bg=THEME['bg_card'])
            title_lbl.config(bg=THEME['bg_card'], fg=THEME['text_primary'])
            author_lbl.config(bg=THEME['bg_card'])

        def on_click(e):
            self.selected_book = book
            self.show_book_detail_dialog(book)

        def on_double_click(e):
            self.selected_book = book
            self.open_book_file(book.file_path)

        def on_right_click(e):
            self.selected_book = book
            self.shelf_menu.post(e.x_root, e.y_root)

        for w in (card, cover_lbl, title_lbl, author_lbl):
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)
            w.bind("<Button-1>", on_click)
            w.bind("<Double-1>", on_double_click)
            w.bind("<Button-3>", on_right_click)

        return card

    def show_book_detail_dialog(self, book):
        win = tk.Toplevel(self.root)
        win.title(f"📖 图书详情 - 《{book.title}》")
        win.geometry("680x560")
        win.minsize(580, 480)
        win.configure(bg=THEME['bg_panel'])
        win.transient(self.root)

        top_container = tk.Frame(win, bg=THEME['bg_panel'], padx=20, pady=16)
        top_container.pack(fill=tk.BOTH, expand=True)

        left_box = tk.Frame(top_container, bg=THEME['bg_panel'])
        left_box.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 20))

        pil_large = bookshelf_manager.make_zlib_thumbnail(
            book.cover_path,
            book.title,
            book.author,
            badge_text=book.format,
            target_size=(170, 246)
        )
        photo_large = ImageTk.PhotoImage(pil_large)
        lbl_large_cover = tk.Label(left_box, image=photo_large, bg=THEME['bg_panel'], bd=1, relief=tk.SOLID)
        lbl_large_cover.image = photo_large
        lbl_large_cover.pack()

        right_box = tk.Frame(top_container, bg=THEME['bg_panel'])
        right_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(
            right_box,
            text=book.title,
            font=("Microsoft YaHei UI", 14, "bold"),
            fg=THEME['text_primary'],
            bg=THEME['bg_panel'],
            wraplength=420,
            justify=tk.LEFT,
            anchor="w"
        ).pack(fill=tk.X, pady=(0, 4))

        tk.Label(
            right_box,
            text=f"作者: {book.author}",
            font=("Microsoft YaHei UI", 11, "bold"),
            fg=THEME['accent_cyan'],
            bg=THEME['bg_panel'],
            anchor="w"
        ).pack(fill=tk.X, pady=(0, 6))

        info_txt = (
            f"出版社: {book.publisher or '未知'}\n"
            f"出版日期: {book.pubdate or '未知'}\n"
            f"ISBN: {book.isbn or '无'}\n"
            f"格式: {book.format}  |  文件大小: {book.file_size_str}\n"
            f"所在目录: {os.path.basename(book.folder_path)}"
        )
        tk.Label(
            right_box,
            text=info_txt,
            font=self.font_normal,
            fg=THEME['text_secondary'],
            bg=THEME['bg_panel'],
            justify=tk.LEFT,
            anchor="w"
        ).pack(fill=tk.X, pady=(0, 12))

        act_row = tk.Frame(right_box, bg=THEME['bg_panel'])
        act_row.pack(fill=tk.X, pady=(0, 12))

        btn_open = tk.Button(
            act_row,
            text="📖 立即打开观看",
            font=self.font_bold,
            bg=THEME['accent_green'],
            fg='#ffffff',
            relief=tk.FLAT,
            padx=14,
            pady=6,
            cursor="hand2",
            command=lambda: [win.destroy(), self.open_book_file(book.file_path)]
        )
        btn_open.pack(side=tk.LEFT, padx=(0, 8))

        btn_prev = tk.Button(
            act_row,
            text="📄 内置试读",
            font=self.font_normal,
            bg=THEME['accent_teal'],
            fg='#ffffff',
            relief=tk.FLAT,
            padx=12,
            pady=6,
            cursor="hand2",
            command=lambda: [win.destroy(), self.open_builtin_preview()]
        )
        btn_prev.pack(side=tk.LEFT, padx=(0, 8))

        btn_loc = tk.Button(
            act_row,
            text="📁 打开目录",
            font=self.font_normal,
            bg='#232a3b',
            fg=THEME['text_primary'],
            relief=tk.FLAT,
            padx=10,
            pady=6,
            cursor="hand2",
            command=self.open_selected_folder
        )
        btn_loc.pack(side=tk.LEFT, padx=(0, 8))

        tk.Label(
            right_box,
            text="内容简介:",
            font=self.font_bold,
            fg=THEME['text_primary'],
            bg=THEME['bg_panel'],
            anchor="w"
        ).pack(fill=tk.X, pady=(4, 2))

        desc_box = scrolledtext.ScrolledText(
            right_box,
            font=("Microsoft YaHei UI", 9),
            bg=THEME['bg_card'],
            fg=THEME['text_primary'],
            relief=tk.SOLID,
            bd=1,
            padx=10,
            pady=8,
            height=7,
            wrap=tk.WORD
        )
        desc_box.pack(fill=tk.BOTH, expand=True)
        desc_box.insert(tk.END, book.description or "暂无详细内容简介。")
        desc_box.config(state=tk.DISABLED)

    def render_list_view(self):
        self.shelf_tree.delete(*self.shelf_tree.get_children())
        for idx, b in enumerate(self.filtered_books):
            self.shelf_tree.insert(
                "",
                tk.END,
                iid=str(idx),
                values=(
                    idx + 1,
                    b.title,
                    b.author,
                    b.format,
                    b.file_size_str,
                    b.isbn,
                    b.publisher,
                    b.pubdate
                )
            )

    def open_tree_selected_book(self):
        sel = self.shelf_tree.selection()
        if sel:
            idx = int(sel[0])
            if 0 <= idx < len(self.filtered_books):
                self.selected_book = self.filtered_books[idx]
                self.open_book_file(self.selected_book.file_path)

    def show_tree_context_menu(self, event):
        item = self.shelf_tree.identify_row(event.y)
        if item:
            self.shelf_tree.selection_set(item)
            idx = int(item)
            if 0 <= idx < len(self.filtered_books):
                self.selected_book = self.filtered_books[idx]
                self.shelf_menu.post(event.x_root, event.y_root)

    def open_selected_book(self):
        if self.selected_book and self.selected_book.file_path:
            self.open_book_file(self.selected_book.file_path)
        else:
            messagebox.showinfo("提示", "请先选择一本图书！")

    def open_book_file(self, file_path):
        if not file_path or not os.path.exists(file_path):
            messagebox.showerror("错误", "图书文件不存在！")
            return
        success, msg = bookshelf_manager.open_book_file(file_path)
        if not success:
            ext = os.path.splitext(file_path)[1].lower()
            if ext in ['.epub', '.txt']:
                ans = messagebox.askyesno(
                    "打开失败",
                    f"系统默认阅读器调用失败: {msg}\n\n是否使用【内置试读阅读器】直接打开观看本书？"
                )
                if ans:
                    self.open_builtin_preview()
            else:
                messagebox.showerror("打开失败", f"无法直接打开此图书: {msg}\n请确保系统已安装对应阅读器，或点击【打开目录】查看文件。")

    def open_selected_folder(self):
        if not self.selected_book:
            return
        folder = self.selected_book.folder_path
        file_p = self.selected_book.file_path
        bookshelf_manager.open_folder_in_explorer(folder, file_p)

    def open_builtin_preview(self):
        if not self.selected_book or not self.selected_book.file_path:
            messagebox.showinfo("提示", "请先选择一本图书！")
            return

        book = self.selected_book
        chaps = bookshelf_manager.extract_book_preview(book.file_path)
        if not chaps:
            messagebox.showinfo("提示", "未能提取到正文文本。")
            return

        win = tk.Toplevel(self.root)
        win.title(f"📖 快速试读 - 《{book.title}》")
        win.geometry("940x660")
        win.minsize(720, 520)
        win.configure(bg=THEME['bg_panel'])

        top_bar = tk.Frame(win, bg=THEME['bg_header'], padx=16, pady=10)
        top_bar.pack(fill=tk.X)

        tk.Label(
            top_bar,
            text=f"《{book.title}》  作者: {book.author}",
            font=("Microsoft YaHei UI", 11, "bold"),
            fg=THEME['accent_cyan'],
            bg=THEME['bg_header']
        ).pack(side=tk.LEFT)

        btn_ext = tk.Button(
            top_bar,
            text="🚀 系统阅读器打开",
            font=self.font_normal,
            bg=THEME['accent_green'],
            fg='#ffffff',
            relief=tk.FLAT,
            padx=10,
            pady=3,
            cursor="hand2",
            command=lambda: bookshelf_manager.open_book_file(book.file_path)
        )
        btn_ext.pack(side=tk.RIGHT)

        r_paned = ttk.PanedWindow(win, orient=tk.HORIZONTAL)
        r_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        chap_frame = tk.Frame(r_paned, bg=THEME['bg_panel'], width=220)
        r_paned.add(chap_frame, weight=1)

        tk.Label(chap_frame, text="目录导航:", font=self.font_bold, fg=THEME['text_primary'], bg=THEME['bg_panel']).pack(anchor="w", pady=(0, 4))
        chap_list = tk.Listbox(
            chap_frame,
            font=("Microsoft YaHei UI", 9),
            bg=THEME['bg_card'],
            fg=THEME['text_primary'],
            selectbackground=THEME['accent_teal'],
            bd=0
        )
        c_scroll = ttk.Scrollbar(chap_frame, orient=tk.VERTICAL, command=chap_list.yview)
        chap_list.configure(yscrollcommand=c_scroll.set)
        chap_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        c_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        for c in chaps:
            chap_list.insert(tk.END, f"  {c[0]}")

        text_frame = tk.Frame(r_paned, bg=THEME['bg_panel'])
        r_paned.add(text_frame, weight=4)

        reader_text = scrolledtext.ScrolledText(
            text_frame,
            wrap=tk.WORD,
            font=("Microsoft YaHei UI", 11),
            bg=THEME['bg_app'],
            fg='#e2e8f0',
            padx=20,
            pady=16,
            spacing1=6,
            spacing3=6,
            insertbackground=THEME['accent_cyan']
        )
        reader_text.pack(fill=tk.BOTH, expand=True)

        def on_select(evt):
            sel = chap_list.curselection()
            if sel:
                c_idx = sel[0]
                content = chaps[c_idx][1]
                reader_text.delete("1.0", tk.END)
                reader_text.insert(tk.END, f"\n=== {chaps[c_idx][0]} ===\n\n{content}\n")
                reader_text.yview_moveto(0.0)

        chap_list.bind("<<ListboxSelect>>", on_select)
        chap_list.selection_set(0)
        on_select(None)

    def search_douban(self):
        if self.selected_book:
            q = self.selected_book.isbn or self.selected_book.title
            webbrowser.open(f"https://search.douban.com/book/subject_search?search_text={urllib.parse.quote(q)}")

    def search_google(self):
        if self.selected_book:
            q = self.selected_book.isbn or self.selected_book.title
            webbrowser.open(f"https://www.google.com/search?tbm=bks&q={urllib.parse.quote(q)}")

    def copy_shelf_title(self):
        if self.selected_book:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.selected_book.title)

    def copy_shelf_isbn(self):
        if self.selected_book and self.selected_book.isbn:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.selected_book.isbn)

    def edit_selected_metadata(self):
        if not self.selected_book:
            return
        book = self.selected_book

        edit_win = tk.Toplevel(self.root)
        edit_win.title(f"编辑图书元数据 - 《{book.title}》")
        edit_win.geometry("540x500")
        edit_win.configure(bg=THEME['bg_panel'])
        edit_win.transient(self.root)
        edit_win.grab_set()

        container = tk.Frame(edit_win, bg=THEME['bg_panel'], padx=20, pady=16)
        container.pack(fill=tk.BOTH, expand=True)

        fields = [
            ("书名:", "title", book.title),
            ("作者:", "author", book.author),
            ("出版社:", "publisher", book.publisher),
            ("出版日期:", "pubdate", book.pubdate),
            ("ISBN:", "isbn", book.isbn),
        ]
        vars_dict = {}
        for row, (lbl, key, val) in enumerate(fields):
            tk.Label(container, text=lbl, font=self.font_bold, fg=THEME['text_primary'], bg=THEME['bg_panel']).grid(row=row, column=0, sticky="w", pady=4)
            v = tk.StringVar(value=val)
            vars_dict[key] = v
            ent = tk.Entry(container, textvariable=v, width=42, font=self.font_normal, bg=THEME['bg_input'], fg=THEME['text_primary'], insertbackground=THEME['accent_cyan'])
            ent.grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=4)

        tk.Label(container, text="简介:", font=self.font_bold, fg=THEME['text_primary'], bg=THEME['bg_panel']).grid(row=5, column=0, sticky="nw", pady=4)
        txt_desc = scrolledtext.ScrolledText(container, width=40, height=8, font=self.font_normal, bg=THEME['bg_input'], fg=THEME['text_primary'], insertbackground=THEME['accent_cyan'])
        txt_desc.grid(row=5, column=1, sticky="ew", padx=(8, 0), pady=4)
        txt_desc.insert(tk.END, book.description or "")

        container.columnconfigure(1, weight=1)

        btn_bar = tk.Frame(container, bg=THEME['bg_panel'])
        btn_bar.grid(row=6, column=0, columnspan=2, pady=(16, 0))

        def save_meta():
            new_meta = {
                'title': vars_dict['title'].get().strip(),
                'author': vars_dict['author'].get().strip(),
                'publisher': vars_dict['publisher'].get().strip(),
                'pubdate': vars_dict['pubdate'].get().strip(),
                'isbn': vars_dict['isbn'].get().strip(),
                'description': txt_desc.get("1.0", tk.END).strip()
            }
            succ, msg = bookshelf_manager.update_book_metadata(book, new_meta)
            if succ:
                messagebox.showinfo("成功", "元数据更新成功！", parent=edit_win)
                edit_win.destroy()
                self.filter_bookshelf()
            else:
                messagebox.showerror("失败", msg, parent=edit_win)

        tk.Button(btn_bar, text="💾 保存修改", font=self.font_bold, bg=THEME['accent_teal'], fg='#ffffff', relief=tk.FLAT, padx=12, pady=4, command=save_meta).pack(side=tk.LEFT, padx=6)
        tk.Button(btn_bar, text="取消", font=self.font_normal, bg='#232a3b', fg=THEME['text_secondary'], relief=tk.FLAT, padx=10, pady=4, command=edit_win.destroy).pack(side=tk.LEFT, padx=6)

    def delete_selected_book(self):
        if not self.selected_book:
            return
        book = self.selected_book
        if messagebox.askyesno("确认删除", f"确定要从书库中删除图书《{book.title}》吗？\n\n警告：此操作将从磁盘中彻底删除该书籍目录及所有文件！"):
            succ, msg = bookshelf_manager.delete_book_item(book)
            if succ:
                messagebox.showinfo("已删除", f"《{book.title}》已成功从书库中移除。")
                self.refresh_bookshelf()
            else:
                messagebox.showerror("删除失败", msg)

    def create_organizer_tab_widgets(self, parent):
        card_dir = tk.LabelFrame(parent, text=" 路径与目录配置 ", font=self.font_bold, bg=THEME['bg_panel'], fg=THEME['accent_cyan'], padx=14, pady=10)
        card_dir.pack(fill=tk.X, pady=(0, 10))

        tk.Label(card_dir, text="待整理图书源目录:", font=self.font_normal, fg=THEME['text_primary'], bg=THEME['bg_panel']).grid(row=0, column=0, sticky="w", pady=6)
        init_src = str(self.saved_settings.get("src", config.DEFAULT_SRC_DIR))
        self.src_var = tk.StringVar(value=init_src)
        self.src_entry = tk.Entry(card_dir, textvariable=self.src_var, font=self.font_normal, bg=THEME['bg_input'], fg=THEME['text_primary'], insertbackground=THEME['accent_cyan'])
        self.src_entry.grid(row=0, column=1, sticky="ew", padx=8, pady=6)

        tk.Button(card_dir, text="浏览...", font=self.font_normal, bg='#232a3b', fg='#ffffff', relief=tk.FLAT, padx=8, command=self.browse_src).grid(row=0, column=2, padx=4, pady=6)
        tk.Button(card_dir, text="打开", font=self.font_normal, bg='#232a3b', fg='#ffffff', relief=tk.FLAT, padx=8, command=lambda: self.open_dir(self.src_var.get())).grid(row=0, column=3, padx=4, pady=6)

        tk.Label(card_dir, text="目标已整理书库目录:", font=self.font_normal, fg=THEME['text_primary'], bg=THEME['bg_panel']).grid(row=1, column=0, sticky="w", pady=6)
        init_dst = str(self.saved_settings.get("dst", config.DEFAULT_DST_DIR))
        self.dst_var = tk.StringVar(value=init_dst)
        self.dst_entry = tk.Entry(card_dir, textvariable=self.dst_var, font=self.font_normal, bg=THEME['bg_input'], fg=THEME['text_primary'], insertbackground=THEME['accent_cyan'])
        self.dst_entry.grid(row=1, column=1, sticky="ew", padx=8, pady=6)

        tk.Button(card_dir, text="浏览...", font=self.font_normal, bg='#232a3b', fg='#ffffff', relief=tk.FLAT, padx=8, command=self.browse_dst).grid(row=1, column=2, padx=4, pady=6)
        tk.Button(card_dir, text="打开", font=self.font_normal, bg='#232a3b', fg='#ffffff', relief=tk.FLAT, padx=8, command=lambda: self.open_dir(self.dst_var.get())).grid(row=1, column=3, padx=4, pady=6)

        card_dir.columnconfigure(1, weight=1)

        card_rule = tk.LabelFrame(parent, text=" 整理规则与参数 ", font=self.font_bold, bg=THEME['bg_panel'], fg=THEME['accent_cyan'], padx=14, pady=10)
        card_rule.pack(fill=tk.X, pady=(0, 10))

        r1 = tk.Frame(card_rule, bg=THEME['bg_panel'])
        r1.pack(fill=tk.X, pady=2)
        tk.Label(r1, text="整理方式:", font=self.font_normal, fg=THEME['text_primary'], bg=THEME['bg_panel']).pack(side=tk.LEFT, padx=(0, 8))
        self.action_var = tk.StringVar(value=str(self.saved_settings.get("action", "copy")))
        tk.Radiobutton(r1, text="复制模式 (保留源文件, 安全推荐)", variable=self.action_var, value="copy", font=self.font_normal, fg=THEME['text_primary'], bg=THEME['bg_panel'], selectcolor=THEME['bg_card']).pack(side=tk.LEFT, padx=6)
        tk.Radiobutton(r1, text="移动模式 (移动源文件)", variable=self.action_var, value="move", font=self.font_normal, fg=THEME['text_primary'], bg=THEME['bg_panel'], selectcolor=THEME['bg_card']).pack(side=tk.LEFT, padx=6)

        self.skip_col_var = tk.BooleanVar(value=bool(self.saved_settings.get("skip_collections", True)))
        tk.Checkbutton(
            r1,
            text="遇到多本合集/全本，若未找到出版ISBN则直接跳过不整理 (硬性规则)",
            variable=self.skip_col_var,
            font=self.font_normal,
            fg=THEME['accent_cyan'],
            bg=THEME['bg_panel'],
            selectcolor=THEME['bg_card']
        ).pack(side=tk.RIGHT, padx=6)

        r2 = tk.Frame(card_rule, bg=THEME['bg_panel'])
        r2.pack(fill=tk.X, pady=(6, 2))
        tk.Label(r2, text="数量限制:", font=self.font_normal, fg=THEME['text_primary'], bg=THEME['bg_panel']).pack(side=tk.LEFT, padx=(0, 4))
        self.limit_var = tk.StringVar(value=str(self.saved_settings.get("limit", "")))
        tk.Entry(r2, textvariable=self.limit_var, width=8, font=self.font_normal, bg=THEME['bg_input'], fg=THEME['text_primary'], insertbackground=THEME['accent_cyan']).pack(side=tk.LEFT, padx=(0, 14))

        tk.Label(r2, text="请求延时:", font=self.font_normal, fg=THEME['text_primary'], bg=THEME['bg_panel']).pack(side=tk.LEFT, padx=(0, 4))
        self.delay_var = tk.StringVar(value=str(self.saved_settings.get("delay", config.REQUEST_DELAY)))
        tk.Entry(r2, textvariable=self.delay_var, width=6, font=self.font_normal, bg=THEME['bg_input'], fg=THEME['text_primary'], insertbackground=THEME['accent_cyan']).pack(side=tk.LEFT, padx=(0, 14))

        tk.Label(r2, text="Google Books Key:", font=self.font_normal, fg=THEME['text_primary'], bg=THEME['bg_panel']).pack(side=tk.LEFT, padx=(0, 4))
        self.key_var = tk.StringVar(value=str(self.saved_settings.get("google_key", "")))
        tk.Entry(r2, textvariable=self.key_var, width=24, font=self.font_normal, bg=THEME['bg_input'], fg=THEME['text_primary'], insertbackground=THEME['accent_cyan']).pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(r2, text="🔗 申请Key...", font=self.font_normal, bg='#232a3b', fg=THEME['accent_cyan'], relief=tk.FLAT, padx=6, command=self.open_google_api_page).pack(side=tk.LEFT)

        act_frame = tk.Frame(parent, bg=THEME['bg_panel'])
        act_frame.pack(fill=tk.X, pady=(2, 6))

        self.btn_dry_run = tk.Button(
            act_frame,
            text="🔍  预演测试 (Dry-Run)",
            font=self.font_bold,
            bg='#2563eb',
            fg='#ffffff',
            relief=tk.FLAT,
            padx=16,
            pady=6,
            cursor="hand2",
            command=self.start_dry_run
        )
        self.btn_dry_run.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_start = tk.Button(
            act_frame,
            text="🚀  开始整理入库",
            font=self.font_bold,
            bg=THEME['accent_green'],
            fg='#ffffff',
            relief=tk.FLAT,
            padx=18,
            pady=6,
            cursor="hand2",
            command=self.start_organize
        )
        self.btn_start.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_stop = tk.Button(
            act_frame,
            text="⏹  停止任务",
            font=self.font_bold,
            bg='#dc2626',
            fg='#ffffff',
            relief=tk.FLAT,
            padx=14,
            pady=6,
            state=tk.DISABLED,
            command=self.stop_task
        )
        self.btn_stop.pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(act_frame, text="🧹 清空日志", font=self.font_normal, bg='#232a3b', fg=THEME['text_secondary'], relief=tk.FLAT, padx=10, command=self.clear_log).pack(side=tk.RIGHT)

        prog_frame = tk.Frame(parent, bg=THEME['bg_panel'])
        prog_frame.pack(fill=tk.X, pady=(2, 6))
        self.progress_bar = ttk.Progressbar(prog_frame, orient="horizontal", mode="determinate", style="Green.Horizontal.TProgressbar")
        self.progress_bar.pack(fill=tk.X, side=tk.TOP, pady=(0, 3))
        self.status_lbl = tk.Label(prog_frame, text="就绪状态：等待开始", font=self.font_normal, fg=THEME['text_secondary'], bg=THEME['bg_panel'], anchor="w")
        self.status_lbl.pack(fill=tk.X)

        stats_frame = tk.Frame(parent, bg=THEME['bg_panel'])
        stats_frame.pack(fill=tk.X, pady=(2, 8))
        self.stat_vars = {
            'total': tk.StringVar(value="0"),
            'organized': tk.StringVar(value="0"),
            'col_skip': tk.StringVar(value="0"),
            'no_isbn': tk.StringVar(value="0"),
            'error': tk.StringVar(value="0"),
        }
        self.add_stat_box(stats_frame, "待处理总数", self.stat_vars['total'], THEME['text_primary'], 0)
        self.add_stat_box(stats_frame, "成功整理入库", self.stat_vars['organized'], THEME['accent_green'], 1)
        self.add_stat_box(stats_frame, "无ISBN合集跳过", self.stat_vars['col_skip'], "#f59e0b", 2)
        self.add_stat_box(stats_frame, "无出版ISBN跳过", self.stat_vars['no_isbn'], THEME['text_secondary'], 3)
        self.add_stat_box(stats_frame, "处理异常", self.stat_vars['error'], "#ef4444", 4)
        for i in range(5): stats_frame.columnconfigure(i, weight=1)

        log_frame = tk.LabelFrame(parent, text=" 执行日志与明细 ", font=self.font_bold, bg=THEME['bg_panel'], fg=THEME['accent_cyan'], padx=10, pady=8)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            font=self.font_mono,
            bg=THEME['bg_card'],
            fg=THEME['text_primary'],
            insertbackground=THEME['accent_cyan'],
            relief=tk.FLAT,
            padx=10,
            pady=10
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self.log_text.tag_config('heading', foreground=THEME['accent_cyan'], font=("Consolas", 9, "bold"))
        self.log_text.tag_config('success', foreground=THEME['accent_green'], font=("Consolas", 9, "bold"))
        self.log_text.tag_config('skip', foreground="#f59e0b")
        self.log_text.tag_config('error', foreground="#ef4444", font=("Consolas", 9, "bold"))
        self.log_text.tag_config('warning', foreground="#fbbf24")
        self.log_text.tag_config('info', foreground="#cbd5e1")

        self.log("【智能图书整理与现代书架系统 就绪】", 'heading')
        self.log("源图书目录: " + self.src_var.get())
        self.log("目标书库目录: " + self.dst_var.get())
        if self.key_var.get().strip():
            self.log("已加载保存的 Google Books API Key")
        else:
            self.log("未配置 Google Key（支持免Key运行；若需专属配额可点击'申请Key...'）")
        self.log("书架画廊：支持 Z-Library 风格封面网格、双击直接打开阅读、章节试读与全套元数据编辑。\n")

    def add_stat_box(self, parent, label_text, str_var, color, col_idx):
        box = tk.Frame(parent, bg=THEME['bg_card'], bd=1, relief=tk.SOLID, padx=6, pady=4)
        box.grid(row=0, column=col_idx, sticky="nsew", padx=3)
        tk.Label(box, textvariable=str_var, font=("Segoe UI", 12, "bold"), fg=color, bg=THEME['bg_card']).pack()
        tk.Label(box, text=label_text, font=("Microsoft YaHei UI", 8), fg=THEME['text_secondary'], bg=THEME['bg_card']).pack()

    def get_current_settings(self):
        active_tab_idx = 0
        try:
            active_tab_idx = self.notebook.index(self.notebook.select())
        except Exception:
            pass

        return {
            "src": self.src_var.get().strip(),
            "dst": self.dst_var.get().strip(),
            "bookshelf_dir": self.shelf_dir_var.get().strip(),
            "active_tab": active_tab_idx,
            "action": self.action_var.get(),
            "skip_collections": bool(self.skip_col_var.get()),
            "limit": self.limit_var.get().strip(),
            "delay": self.delay_var.get().strip(),
            "google_key": self.key_var.get().strip()
        }

    def save_current_settings(self):
        curr = self.get_current_settings()
        save_settings(curr)

    def open_google_api_page(self):
        url = "https://console.cloud.google.com/apis/credentials"
        webbrowser.open(url)
        self.log(f"[帮助] 已在浏览器中打开 Google Cloud 凭据申请页: {url}")

    def browse_src(self):
        curr = self.src_var.get()
        init_dir = curr if os.path.exists(curr) else os.getcwd()
        path = filedialog.askdirectory(title="选择待整理图书源目录", initialdir=init_dir)
        if path:
            self.src_var.set(os.path.normpath(path))
            self.save_current_settings()

    def browse_dst(self):
        curr = self.dst_var.get()
        init_dir = curr if os.path.exists(curr) else os.getcwd()
        path = filedialog.askdirectory(title="选择目标书库目录", initialdir=init_dir)
        if path:
            norm_p = os.path.normpath(path)
            self.dst_var.set(norm_p)
            self.shelf_dir_var.set(norm_p)
            self.save_current_settings()
            self.refresh_bookshelf()

    def open_dir(self, dir_path):
        if dir_path and os.path.exists(dir_path):
            os.startfile(dir_path)
        else:
            messagebox.showwarning("警告", f"目录不存在: {dir_path}")

    def clear_log(self):
        self.log_text.delete("1.0", tk.END)

    def log(self, text, tag='info'):
        self.log_text.insert(tk.END, text + "\n", tag)
        self.log_text.see(tk.END)

    def update_progress(self, current, total):
        if total > 0:
            pct = (current / total) * 100
            self.progress_bar['value'] = pct
            self.status_lbl.config(text=f"整理处理中... [{current}/{total}] ({pct:.1f}%)")

    def update_stats(self, **kwargs):
        for k, v in kwargs.items():
            if k in self.stats:
                self.stats[k] = v
                self.stat_vars[k].set(str(v))

    def process_queue(self):
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                mtype = msg.get('type')
                if mtype == 'log':
                    self.log(msg.get('text', ''), msg.get('tag', 'info'))
                elif mtype == 'progress':
                    self.update_progress(msg.get('current', 0), msg.get('total', 0))
                elif mtype == 'stats':
                    self.update_stats(**msg.get('data', {}))
                elif mtype == 'status':
                    self.status_lbl.config(text=msg.get('text', ''))
                elif mtype == 'done':
                    self.set_ui_state(running=False)
                    self.status_lbl.config(text=msg.get('status_text', '任务完成'))
                    if msg.get('success', False):
                        messagebox.showinfo("完成", msg.get('summary', '图书处理完成！'))
                        if self.stats['organized'] > 0:
                            self.refresh_bookshelf()
                            self.log("【书架同步】已自动更新书架画廊数据，切换至【我的书架】即可浏览与阅读！", 'success')
                    else:
                        messagebox.showwarning("已停止", msg.get('summary', '任务已提前中止或异常。'))
        except queue.Empty:
            pass

        self.root.after(100, self.process_queue)

    def set_ui_state(self, running):
        self.is_running = running
        st = tk.DISABLED if running else tk.NORMAL
        self.btn_dry_run.config(state=st)
        self.btn_start.config(state=st)
        self.btn_stop.config(state=tk.NORMAL if running else tk.DISABLED)
        self.src_entry.config(state=st)
        self.dst_entry.config(state=st)

    def start_dry_run(self):
        self.start_task(dry_run=True)

    def start_organize(self):
        self.start_task(dry_run=False)

    def start_task(self, dry_run=False):
        if self.is_running:
            return
        self.save_current_settings()

        src = self.src_var.get().strip()
        dst = self.dst_var.get().strip()
        if not src or not os.path.exists(src):
            messagebox.showerror("错误", f"待整理源目录不存在: {src}")
            return
        if not dst:
            messagebox.showerror("错误", "请输入或选择目标书库目录！")
            return

        limit_val = None
        limit_str = self.limit_var.get().strip()
        if limit_str:
            try:
                limit_val = int(limit_str)
                if limit_val <= 0: limit_val = None
            except ValueError:
                messagebox.showerror("错误", "数量限制必须为大于0的正整数！")
                return

        delay_val = config.REQUEST_DELAY
        delay_str = self.delay_var.get().strip()
        if delay_str:
            try:
                delay_val = float(delay_str)
            except ValueError:
                pass

        key_val = self.key_var.get().strip() or None

        self.stats = {'total': 0, 'organized': 0, 'col_skip': 0, 'no_isbn': 0, 'error': 0}
        for k, v in self.stat_vars.items():
            v.set("0")
        self.progress_bar['value'] = 0

        self.set_ui_state(running=True)
        self.stop_event.clear()

        task_mode_desc = "预演分析 (Dry-Run: 仅分析输出报告，不写入或移动)" if dry_run else f"正式整理入库 ({self.action_var.get()}模式)"
        self.log(f"\n{'='*60}", 'heading')
        self.log(f"任务启动: {task_mode_desc}", 'heading')
        self.log(f"源目录: {src}")
        self.log(f"目标库: {dst}")
        self.log(f"{'='*60}\n", 'heading')

        self.worker = threading.Thread(
            target=self.worker_thread,
            args=(src, dst, self.action_var.get(), self.skip_col_var.get(), limit_val, delay_val, key_val, dry_run),
            daemon=True
        )
        self.worker.start()

    def worker_thread(self, src, dst, action, skip_col, limit, delay, key, dry_run):
        try:
            reporter = book_organizer.OrganizerReporter(self.msg_queue)
            organizer = book_organizer.BookOrganizer(
                src_dir=src,
                dst_dir=dst,
                action=action,
                skip_collections=skip_col,
                request_delay=delay,
                google_api_key=key,
                dry_run=dry_run,
                reporter=reporter,
                stop_event=self.stop_event
            )
            success = organizer.run(dry_run=dry_run, limit=limit)
            summary = organizer.get_summary_text()
            self.msg_queue.put({
                'type': 'done',
                'success': True if success else False,
                'summary': summary,
                'status_text': "预演完成" if dry_run else "整理完成"
            })
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.msg_queue.put({'type': 'log', 'text': f"[严重异常] 运行崩溃: {e}\n{tb}", 'tag': 'error'})
            self.msg_queue.put({'type': 'done', 'success': False, 'summary': f"运行发生异常: {e}\n{tb}", 'status_text': "异常中止"})

    def stop_task(self):
        if self.is_running:
            self.stop_event.set()
            self.status_lbl.config(text="正在停止任务中...")
            self.log("[提示] 用户已发起终止任务请求，正在等待当前书籍处理完毕安全退出...", 'warning')
            self.btn_stop.config(state=tk.DISABLED)

    def on_closing(self):
        self.save_current_settings()
        if self.is_running:
            if messagebox.askyesno("正在运行", "整理任务正在后台执行中，确定要强制退出吗？"):
                self.stop_event.set()
                self.root.destroy()
        else:
            self.root.destroy()

def launch_gui():
    root = tk.Tk()
    app = BookOrganizerGUI(root)
    root.mainloop()

if __name__ == '__main__':
    launch_gui()

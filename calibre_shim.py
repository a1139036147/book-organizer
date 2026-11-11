# -*- coding: utf-8 -*-
"""
Calibre Plugin Shim & Dynamic Loader for Book Organizer
Allows loading and executing mature Calibre community metadata plugins directly
without needing a full Calibre desktop/C-extension environment.
"""

import sys
import os
import io
import re
import json
import queue
import zipfile
import tempfile
import importlib.util
from types import ModuleType
from PIL import Image

# ---------------------------------------------------------------------------
# 1. Calibre Logging & Abort Mocks
# ---------------------------------------------------------------------------

class CalibreLogger:
    """Mock for calibre.utils.logging.default_log"""
    def __init__(self, prefix="[CalibrePlugin]"):
        self.prefix = prefix

    def info(self, *args):
        # Optional debug print
        pass

    def warn(self, *args):
        pass

    def warning(self, *args):
        pass

    def error(self, *args):
        pass

    def debug(self, *args):
        pass

    def exception(self, *args):
        pass

default_log = CalibreLogger()

class CalibreAbort:
    """Mock for Calibre abort token passed into identify()"""
    def is_set(self):
        return False
    def __call__(self):
        return False

# ---------------------------------------------------------------------------
# 2. Calibre Config Mock (JSONConfig)
# ---------------------------------------------------------------------------

class JSONConfig(dict):
    """Mock for calibre.utils.config.JSONConfig"""
    def __init__(self, name, config_dir=None):
        super().__init__()
        self.name = name
        self.config_dir = config_dir or os.path.join(os.path.dirname(__file__), "calibre_plugins", ".configs")
        os.makedirs(self.config_dir, exist_ok=True)
        self.file_path = os.path.join(self.config_dir, f"{name}.json")
        self.load()

    def load(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    self.update(json.load(f))
            except Exception:
                pass

    def commit(self):
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(dict(self), f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def set(self, key, value):
        self[key] = value

# ---------------------------------------------------------------------------
# 3. Calibre Metadata Data Container Mock
# ---------------------------------------------------------------------------

class Metadata:
    """Mock for calibre.ebooks.metadata.book.base.Metadata"""
    def __init__(self, title, authors=None):
        self.title = title or ""
        self.authors = list(authors) if authors else []
        self.author_sort = None
        self.publisher = None
        self.pubdate = None
        self.comments = None
        self.isbn = None
        self.rating = None
        self.tags = []
        self.identifiers = {}
        self.series = None
        self.series_index = None
        self.languages = []
        self.cover_data = (None, None)
        self.has_cover = False

    def set_identifier(self, id_type, val):
        if val is not None:
            s_type = str(id_type).lower().strip()
            s_val = str(val).strip()
            self.identifiers[s_type] = s_val
            if s_type == "isbn":
                self.isbn = s_val

    def has_identifier(self, id_type):
        return str(id_type).lower().strip() in self.identifiers

    def get_identifiers(self):
        return dict(self.identifiers)

    def format_field(self, field):
        return str(getattr(self, field, ""))

    def deepcopy(self):
        import copy
        return copy.deepcopy(self)

    def __repr__(self):
        return f"<CalibreMetadata title={self.title!r} authors={self.authors!r} isbn={self.isbn!r}>"

# ---------------------------------------------------------------------------
# 4. Calibre Source Base Class Mock
# ---------------------------------------------------------------------------

class Option:
    """Mock for calibre.ebooks.metadata.sources.base.Option"""
    def __init__(self, name, type, default, label, desc):
        self.name = name
        self.type = type
        self.default = default
        self.label = label
        self.desc = desc

class Source:
    """Mock for calibre.ebooks.metadata.sources.base.Source"""
    name = "Calibre Source"
    description = ""
    author = ""
    version = (1, 0, 0)
    minimum_calibre_version = (0, 8, 0)
    capabilities = frozenset(['identify', 'cover'])
    touched_fields = frozenset(['title', 'authors', 'tags', 'pubdate', 'comments', 'publisher', 'identifier:isbn', 'rating'])
    supports_gzip_transfer_encoding = False
    prefer_results_with_isbn = True
    options = ()

    def __init__(self, *args, **kwargs):
        pass

    def is_customizable(self):
        return False

    def config_widget(self):
        return None

    def save_settings(self, config_widget):
        pass

    def get_cached_cover_url(self, identifiers):
        return None

    def clean_downloaded_metadata(self, mi):
        pass

    def identify(self, log, result_queue, abort, title=None, authors=None, identifiers={}, timeout=30):
        pass

    def download_cover(self, log, result_queue, abort, title=None, authors=None, identifiers={}, timeout=30, get_best_cover=False):
        pass

# ---------------------------------------------------------------------------
# 5. String / HTML Utility Helpers Mock
# ---------------------------------------------------------------------------

def clean_html(raw_html):
    if not raw_html:
        return ""
    text = re.sub(r'<[^>]+>', ' ', raw_html)
    return ' '.join(text.split()).strip()

def comments_to_text(html_text):
    if not html_text:
        return ""
    text = re.sub(r'<script.*?</script>', '', html_text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    return ' '.join(text.split()).strip()

def clean_ascii_chars(txt):
    if not txt:
        return ""
    return "".join(ch for ch in txt if ch >= ' ' or ch in '\n\r\t')

def as_unicode(obj, encoding='utf-8', errors='replace'):
    if obj is None:
        return ''
    if isinstance(obj, str):
        return obj
    if isinstance(obj, bytes):
        return obj.decode(encoding, errors=errors)
    return str(obj)

# ---------------------------------------------------------------------------
# 6. Global Calibre Module Shim Setup
# ---------------------------------------------------------------------------

def install_calibre_shim():
    """Register virtual calibre namespace modules in sys.modules"""
    modules_to_create = [
        "calibre",
        "calibre.ebooks",
        "calibre.ebooks.metadata",
        "calibre.ebooks.metadata.sources",
        "calibre.ebooks.metadata.sources.base",
        "calibre.ebooks.metadata.book",
        "calibre.ebooks.metadata.book.base",
        "calibre.utils",
        "calibre.utils.config",
        "calibre.utils.logging",
        "calibre.utils.cleantext",
        "calibre.library",
        "calibre.library.comments",
    ]

    for mod_name in modules_to_create:
        if mod_name not in sys.modules:
            m = ModuleType(mod_name)
            sys.modules[mod_name] = m

    # Populate module attributes
    c_root = sys.modules["calibre"]
    c_root.as_unicode = as_unicode
    c_root.prints = print

    c_sources_base = sys.modules["calibre.ebooks.metadata.sources.base"]
    c_sources_base.Source = Source
    c_sources_base.Option = Option

    c_book_base = sys.modules["calibre.ebooks.metadata.book.base"]
    c_book_base.Metadata = Metadata

    c_config = sys.modules["calibre.utils.config"]
    c_config.JSONConfig = JSONConfig

    c_logging = sys.modules["calibre.utils.logging"]
    c_logging.default_log = default_log

    c_cleantext = sys.modules["calibre.utils.cleantext"]
    c_cleantext.clean_ascii_chars = clean_ascii_chars

    c_comments = sys.modules["calibre.library.comments"]
    c_comments.clean_html = clean_html
    c_comments.comments_to_text = comments_to_text

# Auto-install on module import
install_calibre_shim()

# ---------------------------------------------------------------------------
# 7. CalibrePluginAdapter: Bridge a Calibre Source instance to Book Organizer
# ---------------------------------------------------------------------------

class CalibrePluginAdapter:
    """Wraps an instantiated Calibre Source plugin to unify with UnifiedMetadataProvider"""
    def __init__(self, plugin_instance):
        self.plugin = plugin_instance
        self.name = getattr(plugin_instance, 'name', 'CalibrePlugin')

    def identify_by_isbn(self, isbn, timeout=15):
        if not isbn:
            return None
        clean_isbn = str(isbn).replace('-', '').strip()
        q = queue.Queue()
        abort = CalibreAbort()
        try:
            self.plugin.identify(
                default_log,
                q,
                abort,
                title=None,
                authors=[],
                identifiers={'isbn': clean_isbn},
                timeout=timeout
            )
        except Exception:
            return None

        return self._extract_best_metadata(q, clean_isbn)

    def identify_by_query(self, title, author="", timeout=15):
        if not title:
            return None
        authors_list = [author] if author else []
        q = queue.Queue()
        abort = CalibreAbort()
        try:
            self.plugin.identify(
                default_log,
                q,
                abort,
                title=title,
                authors=authors_list,
                identifiers={},
                timeout=timeout
            )
        except Exception:
            return None

        return self._extract_best_metadata(q)

    def _extract_best_metadata(self, q, fallback_isbn=""):
        items = []
        while not q.empty():
            try:
                mi = q.get_nowait()
                if mi:
                    items.append(mi)
            except Exception:
                break

        if not items:
            return None

        # Pick first valid metadata
        mi = items[0]
        isbn = mi.isbn or mi.identifiers.get('isbn') or fallback_isbn
        if isbn:
            isbn = str(isbn).replace('-', '').strip()

        authors_str = ', '.join(mi.authors) if getattr(mi, 'authors', None) else ''
        pubdate_str = ''
        if getattr(mi, 'pubdate', None):
            try:
                pubdate_str = str(mi.pubdate)[:10]
            except Exception:
                pass

        rating_val = None
        if getattr(mi, 'rating', None) is not None:
            try:
                # Calibre ratings are usually 1-5 or 1-10
                r = float(mi.rating)
                if r <= 5.0 and r > 0:
                    r = r * 2.0  # normalize to 10
                rating_val = int(round(r))
            except Exception:
                pass

        cover_url = ''
        try:
            cover_url = self.plugin.get_cached_cover_url(mi.identifiers) or ''
        except Exception:
            pass

        return {
            'source': f"calibre:{self.name}",
            'title': getattr(mi, 'title', ''),
            'author': authors_str,
            'publisher': getattr(mi, 'publisher', '') or '',
            'pubdate': pubdate_str,
            'isbn': isbn,
            'cover_url': cover_url,
            'description': getattr(mi, 'comments', '') or '',
            'rating': rating_val,
            'tags': list(getattr(mi, 'tags', []))[:10],
            '_calibre_meta': mi,
            '_calibre_plugin': self.plugin
        }

    def download_cover(self, meta, timeout=15):
        """Invoke the Calibre plugin's download_cover implementation"""
        if not meta:
            return None
        mi = meta.get('_calibre_meta')
        if not mi:
            return None

        q = queue.Queue()
        abort = CalibreAbort()
        try:
            self.plugin.download_cover(
                default_log,
                q,
                abort,
                title=getattr(mi, 'title', None),
                authors=getattr(mi, 'authors', []),
                identifiers=getattr(mi, 'identifiers', {}),
                timeout=timeout,
                get_best_cover=True
            )
        except Exception:
            return None

        while not q.empty():
            try:
                res = q.get_nowait()
                # res is typically (plugin_self, image_data_bytes)
                if isinstance(res, tuple) and len(res) == 2:
                    raw_bytes = res[1]
                elif isinstance(res, (bytes, bytearray)):
                    raw_bytes = res
                else:
                    continue

                if raw_bytes:
                    im = Image.open(io.BytesIO(raw_bytes))
                    if im.mode != 'RGB':
                        im = im.convert('RGB')
                    return im
            except Exception:
                break
        return None

# ---------------------------------------------------------------------------
# 8. CalibrePluginLoader: Auto-discovery and loader for external plugins
# ---------------------------------------------------------------------------

class CalibrePluginLoader:
    """Scans and loads Calibre plugins from directory (.zip packages, folders, or .py files)"""
    def __init__(self, plugin_dir=None):
        try:
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(os.path.abspath(sys.executable))
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))
            self.plugin_dir = plugin_dir or os.path.join(base_dir, "calibre_plugins")
            self.cache_dir = os.path.join(self.plugin_dir, ".extracted")
            self._ensure_dir()
        except Exception:
            self.plugin_dir = ""
            self.cache_dir = ""

    def _ensure_dir(self):
        try:
            if not self.plugin_dir:
                return
            os.makedirs(self.plugin_dir, exist_ok=True)
            readme_path = os.path.join(self.plugin_dir, "README.txt")
            if not os.path.exists(readme_path):
                with open(readme_path, "w", encoding="utf-8") as f:
                    f.write("Calibre Plugins Drop-in Folder\n")
        except Exception:
            pass

    def load_all(self):
        """Scans plugin_dir, loads all valid Calibre plugins, and returns list of CalibrePluginAdapter"""
        adapters = []
        if not os.path.exists(self.plugin_dir):
            return adapters

        for item in os.listdir(self.plugin_dir):
            if item.startswith('.') or item == 'README.txt':
                continue
            item_path = os.path.join(self.plugin_dir, item)

            try:
                if os.path.isfile(item_path) and item.lower().endswith('.zip'):
                    ad = self._load_from_zip(item_path)
                    if ad:
                        adapters.append(ad)
                elif os.path.isfile(item_path) and item.lower().endswith('.py'):
                    ad = self._load_from_py_file(item_path)
                    if ad:
                        adapters.append(ad)
                elif os.path.isdir(item_path):
                    init_py = os.path.join(item_path, "__init__.py")
                    if os.path.isfile(init_py):
                        ad = self._load_from_py_file(init_py, mod_name=os.path.basename(item_path))
                        if ad:
                            adapters.append(ad)
            except Exception as e:
                pass

        return adapters

    def _load_from_zip(self, zip_path):
        os.makedirs(self.cache_dir, exist_ok=True)
        plugin_name = os.path.splitext(os.path.basename(zip_path))[0]
        target_dir = os.path.join(self.cache_dir, plugin_name)
        os.makedirs(target_dir, exist_ok=True)

        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(target_dir)
        except Exception:
            return None

        # Add target_dir to sys.path so inner relative imports work
        if target_dir not in sys.path:
            sys.path.insert(0, target_dir)

        init_file = os.path.join(target_dir, "__init__.py")
        if os.path.exists(init_file):
            return self._load_from_py_file(init_file, mod_name=f"calibre_plugin_{plugin_name}")

        # Scan for any .py file containing Source
        for f in os.listdir(target_dir):
            if f.endswith('.py'):
                ad = self._load_from_py_file(os.path.join(target_dir, f), mod_name=f"calibre_plugin_{plugin_name}_{f[:-3]}")
                if ad:
                    return ad
        return None

    def _load_from_py_file(self, file_path, mod_name=None):
        if not mod_name:
            mod_name = f"calibre_plugin_{os.path.splitext(os.path.basename(file_path))[0]}"

        spec = importlib.util.spec_from_file_location(mod_name, file_path)
        if not spec or not spec.loader:
            return None

        module = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = module
        spec.loader.exec_module(module)

        # Look for subclass of Source
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, Source) and attr is not Source:
                plugin_instance = attr()
                return CalibrePluginAdapter(plugin_instance)

        return None

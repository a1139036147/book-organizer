"""Persistent configuration for the metadata sources used by organizer jobs."""
import json
import logging
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock

logger = logging.getLogger(__name__)
CONFIG_FILE = Path(os.getenv("CONFIG_DIR", "/config" if os.path.exists("/config") else ".")) / "plugins_config.json"

SOURCES = {
    "calibre": ("Calibre 本地插件", {}),
    "douban": ("豆瓣读书", {"cookie": "Cookie", "user_agent": "User-Agent"}),
    "dangdang": ("当当图书", {}),
    "weread": ("微信读书", {}),
    "google_books": ("Google Books", {"api_key": "API Key"}),
    "bangumi": ("Bangumi 番组计划", {}),
    "openlibrary": ("Open Library", {}),
}
SECRET_FIELDS = {"cookie", "api_key"}


class PluginManager:
    def __init__(self):
        self.lock = Lock()
        self.settings = {}
        try:
            self.settings = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except FileNotFoundError:
            pass
        except (ValueError, OSError):
            logger.warning("无法读取刮削源设置")

    def enabled_sources(self, selected=None):
        with self.lock:
            result = []
            for priority, (source_id, (name, _)) in enumerate(SOURCES.items(), 1):
                saved = self.settings.get(source_id, {})
                if saved.get("enabled", True) and (selected is None or source_id in selected):
                    result.append((
                        saved.get("priority", priority), source_id, name,
                        dict(saved.get("config", {})),
                    ))
            return [(source_id, name, config) for _, source_id, name, config in sorted(result, key=lambda row: row[0])]

    def list(self):
        with self.lock:
            sources = []
            for priority, (source_id, (name, fields)) in enumerate(SOURCES.items(), 1):
                saved = self.settings.get(source_id, {})
                config = saved.get("config", {})
                sources.append({
                    "id": source_id,
                    "name": name,
                    "enabled": saved.get("enabled", True),
                    "priority": saved.get("priority", priority),
                    "fields": [
                        {"key": key, "label": label, "secret": key in SECRET_FIELDS,
                         "configured": bool(config.get(key)),
                         "value": "" if key in SECRET_FIELDS else config.get(key, "")}
                        for key, label in fields.items()
                    ],
                })
            return sorted(sources, key=lambda source: source["priority"])

    def update(self, source_id, enabled, priority, fields):
        allowed = SOURCES[source_id][1]
        with self.lock:
            config = dict(self.settings.get(source_id, {}).get("config", {}))
            config.update({key: value for key, value in fields.items() if key in allowed})
            settings = {
                **self.settings,
                source_id: {"enabled": enabled, "priority": priority, "config": config},
            }
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            temp_path = None
            try:
                with NamedTemporaryFile(mode="w", encoding="utf-8", dir=CONFIG_FILE.parent, delete=False) as temp:
                    temp_path = Path(temp.name)
                    json.dump(settings, temp, ensure_ascii=False, indent=2)
                os.replace(temp_path, CONFIG_FILE)
            finally:
                if temp_path is not None:
                    temp_path.unlink(missing_ok=True)
            self.settings = settings


plugin_manager = PluginManager()

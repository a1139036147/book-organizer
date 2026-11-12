#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
插件化数据源管理系统 (Plugin Architecture for Book Scrapers)
负责数据源插件注册、Cookie/API Key认证维护、穿透测试与动态流水线调度。
"""
import os
import json
import logging
import urllib.request
import urllib.parse
import re

logger = logging.getLogger("PluginManager")

CONFIG_FILE = os.path.join(os.getenv("CONFIG_DIR", "/config" if os.path.exists("/config") else "."), "plugins_config.json")

class BasePlugin:
    def __init__(self, plugin_id, name, icon, desc, priority=10):
        self.id = plugin_id
        self.name = name
        self.icon = icon
        self.desc = desc
        self.priority = priority
        self.enabled = True
        self.config = {}
        self.fields = []  # 配置表单字段清单

    def get_config(self, key, default=""):
        return self.config.get(key, default)

    def test_connection(self):
        """测试连通性与 Cookie/Key 是否有效"""
        return True, "连接正常"

    def search(self, title, author="", isbns=None):
        raise NotImplementedError

# --- 插件 1: 当当图书插件 ---
class DangdangPlugin(BasePlugin):
    def __init__(self):
        super().__init__("dangdang", "当当图书 (出版物主力)", "📚", "国内最大图书数据库之一，免登录、抗封锁、精准解析13位出版ISBN", priority=1)
        self.fields = [
            {"key": "delay", "label": "请求间隔 (秒)", "type": "number", "default": "1.0", "desc": "并发刮削时的礼貌延迟时间"}
        ]

    def test_connection(self):
        try:
            req = urllib.request.Request("http://search.dangdang.com/?key=9787805151335", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    return True, "🟢 当当网连接通畅，免登录服务正常"
        except Exception as e:
            return False, f"连接异常: {e}"
        return False, "连接失败"

# --- 插件 2: 豆瓣读书插件 (支持Cookie穿透) ---
class DoubanPlugin(BasePlugin):
    def __init__(self):
        super().__init__("douban", "豆瓣读书 (评分与书评)", "🟢", "豆瓣读书源。支持配置个人登录Cookie与自定义User-Agent，彻底突破游客403与风险IP拦截", priority=2)
        self.fields = [
            {"key": "cookie", "label": "豆瓣会员 Cookie", "type": "textarea", "default": "", "desc": "在浏览器登录豆瓣后复制 Cookie（含 bid/dbcl2），即可彻底绕过 403 游客风控"},
            {"key": "user_agent", "label": "自定义 User-Agent", "type": "text", "default": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36", "desc": "请求时伪装的浏览器标识"}
        ]

    def test_connection(self):
        cookie = self.get_config("cookie")
        ua = self.get_config("user_agent") or "Mozilla/5.0"
        headers = {"User-Agent": ua}
        if cookie:
            headers["Cookie"] = cookie
        try:
            req = urllib.request.Request("https://book.douban.com/", headers=headers)
            with urllib.request.urlopen(req, timeout=6) as resp:
                if resp.status == 200:
                    status_text = "🟢 成功穿透豆瓣风控！Cookie 会员凭证生效，无 403 拦截。" if cookie else "🟡 连通正常，当前以游客身份运行（建议填入Cookie防封）"
                    return True, status_text
        except urllib.error.HTTPError as e:
            if e.code == 403:
                return False, "🔴 触发豆瓣 403 游客拦截！请在下方填入登录后的 Cookie 即可穿透限制。"
            return False, f"HTTP 错误: {e.code}"
        except Exception as e:
            return False, f"连接失败: {e}"
        return False, "未知响应"

# --- 插件 3: Google 图书插件 ---
class GoogleBooksPlugin(BasePlugin):
    def __init__(self):
        super().__init__("google_books", "Google Books (国际官方源)", "🌐", "Google 图书官方 API，全球出版物收录最全，支持配置官方 API Key", priority=3)
        self.fields = [
            {"key": "api_key", "label": "Google Books API Key", "type": "text", "default": "", "desc": "在 Google Cloud Console 获取的免费 Books API 密钥"},
            {"key": "proxy", "label": "HTTP/SOCKS5 代理地址", "type": "text", "default": "", "desc": "海外接口网络加速代理 (如 http://127.0.0.1:7890)"}
        ]

    def test_connection(self):
        key = self.get_config("api_key")
        url = "https://www.googleapis.com/books/v1/volumes?q=isbn:9787805151335"
        if key:
            url += f"&key={key}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                if resp.status == 200:
                    return True, "🟢 Google Books API 连通正常" + (" (已附带专属API Key)" if key else "")
        except Exception as e:
            return False, f"连接失败 (国内直连通常需配置代理或Key): {e}"
        return False, "连接超时"

# --- 插件 4: 起点中文网插件 ---
class QidianPlugin(BasePlugin):
    def __init__(self):
        super().__init__("qidian", "起点中文网 (网络小说主力)", "🔥", "当查不到出版ISBN时自动兜底启用，抓取起点官方原画600px大封面、玄幻修仙流派与连载状态", priority=4)
        self.fields = [
            {"key": "cookie", "label": "起点中文网 Cookie", "type": "textarea", "default": "", "desc": "起点账号 Cookie (可选，用于获取完整字数和专属标签)"}
        ]

    def test_connection(self):
        try:
            req = urllib.request.Request("https://www.qidian.com/", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    return True, "🟢 起点中文网网络小说库连接顺畅"
        except Exception as e:
            return False, f"连接异常: {e}"
        return False, "连接失败"

class PluginManager:
    def __init__(self):
        self.plugins = {
            "dangdang": DangdangPlugin(),
            "douban": DoubanPlugin(),
            "google_books": GoogleBooksPlugin(),
            "qidian": QidianPlugin()
        }
        self.load_configs()

    def load_configs(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                for pid, pdata in saved.items():
                    if pid in self.plugins:
                        self.plugins[pid].enabled = pdata.get("enabled", True)
                        self.plugins[pid].priority = pdata.get("priority", self.plugins[pid].priority)
                        self.plugins[pid].config = pdata.get("config", {})
            except Exception as e:
                logger.error(f"加载插件配置失败: {e}")

    def save_configs(self):
        saved = {}
        for pid, p in self.plugins.items():
            saved[pid] = {
                "enabled": p.enabled,
                "priority": p.priority,
                "config": p.config
            }
        try:
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(saved, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"保存插件配置失败: {e}")
            return False

    def get_plugin_list(self):
        res = []
        for pid, p in sorted(self.plugins.items(), key=lambda x: x[1].priority):
            res.append({
                "id": p.id,
                "name": p.name,
                "icon": p.icon,
                "desc": p.desc,
                "priority": p.priority,
                "enabled": p.enabled,
                "config": p.config,
                "fields": p.fields
            })
        return res

    def update_plugin_config(self, plugin_id, config_dict, enabled=None, priority=None):
        if plugin_id in self.plugins:
            p = self.plugins[plugin_id]
            p.config.update(config_dict)
            if enabled is not None:
                p.enabled = bool(enabled)
            if priority is not None:
                p.priority = int(priority)
            self.save_configs()
            return True
        return False

plugin_manager = PluginManager()

#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os

# 优先读取 CI/CD 流水线构建时动态注入的自增版本号
APP_VERSION = os.getenv("APP_VERSION", "2.5.0")
BUILD_DATE = os.getenv("BUILD_DATE", "2026-11-12")
GIT_COMMIT = os.getenv("GIT_COMMIT", "")
APP_NAME = "智能图书整理与现代视觉书架系统 (All-in-One)"
FEATURES = ["PostgreSQL-16内置数据库", "SHA-256毫秒级去重", "EPUB-Spine骨架正序", "起点中文网网文刮削", "自动版本流水线"]

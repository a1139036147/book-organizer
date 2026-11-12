#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os

APP_VERSION = os.getenv("APP_VERSION", "2.5.0")
BUILD_DATE = os.getenv("BUILD_DATE", "2026-11-13")
GIT_COMMIT = os.getenv("GIT_COMMIT", "")
APP_NAME = "智能图书整理与现代视觉书架系统 (All-in-One)"
FEATURES = ["PostgreSQL-16内置数据库", "SHA-256毫秒级去重", "EPUB-Spine骨架正序", "起点中文网网文刮削", "左下角版本标示"]

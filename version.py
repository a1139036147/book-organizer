#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os

APP_VERSION = os.getenv('APP_VERSION', '2.6.0')
BUILD_DATE = os.getenv('BUILD_DATE', '2026-11-13')
GIT_COMMIT = os.getenv('GIT_COMMIT', '')
APP_NAME = 'Smart Book Organizer All-in-One'
FEATURES = ['PostgreSQL-16', 'SHA-256', 'Koodo-Reader', 'Qidian-Scraper', 'Hot-Update']
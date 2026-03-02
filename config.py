#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
配置管理模块
"""

import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)


class Config:
    """应用配置类"""

    BASE_DIR = Path(__file__).parent

    DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
    DEEPSEEK_MODEL = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
    DEEPSEEK_TEMPERATURE = float(os.getenv('DEEPSEEK_TEMPERATURE', '0.7'))

    SILICONFLOW_API_KEY = os.getenv('SILICONFLOW_API_KEY', '')
    SILICONFLOW_BASE_URL = os.getenv('SILICONFLOW_BASE_URL', 'https://api.siliconflow.cn/v1')
    SILICONFLOW_EMBEDDING_MODEL = os.getenv('SILICONFLOW_EMBEDDING_MODEL', 'BAAI/bge-m3')

    LMSTUDIO_BASE_URL = os.getenv('LMSTUDIO_BASE_URL', 'http://localhost:1234/v1')
    LMSTUDIO_EMBEDDING_MODEL = os.getenv('LMSTUDIO_EMBEDDING_MODEL', 'text-embedding-qwen3-embedding-8b')

    VECTOR_DB_PATH = str(BASE_DIR / os.getenv('VECTOR_DB_PATH', 'vector_db'))
    UPLOAD_FOLDER = str(BASE_DIR / os.getenv('UPLOAD_FOLDER', 'uploads'))
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', str(16 * 1024 * 1024)))

    DATABASE_PATH = str(BASE_DIR / os.getenv('DATABASE_PATH', 'data/ciqas.db'))

    MAX_CONVERSATIONS = int(os.getenv('MAX_CONVERSATIONS', '100'))
    CHUNK_SIZE = int(os.getenv('CHUNK_SIZE', '500'))
    CHUNK_OVERLAP = int(os.getenv('CHUNK_OVERLAP', '50'))
    RETRIEVAL_K = int(os.getenv('RETRIEVAL_K', '3'))

    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = str(BASE_DIR / os.getenv('LOG_FILE', 'logs/ciqas.log'))

    FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
    FLASK_PORT = int(os.getenv('FLASK_PORT', '5000'))
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'true').lower() == 'true'

    @classmethod
    def validate(cls):
        """验证必要配置"""
        errors = []

        if not cls.DEEPSEEK_API_KEY:
            errors.append('DEEPSEEK_API_KEY 未设置')

        if errors:
            raise ValueError('配置错误:\n' + '\n'.join(f'  - {e}' for e in errors))

        return True

    @classmethod
    def ensure_directories(cls):
        """确保必要目录存在"""
        directories = [
            cls.VECTOR_DB_PATH,
            cls.UPLOAD_FOLDER,
            Path(cls.DATABASE_PATH).parent,
            Path(cls.LOG_FILE).parent,
        ]

        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)

#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
配置管理模块
支持动态参数配置
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
    DEEPSEEK_MAX_TOKENS = int(os.getenv('DEEPSEEK_MAX_TOKENS', '4096'))

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

    # 参数默认值和范围定义
    SETTINGS_DEFAULTS = {
        # 大语言模型参数
        'llm_temperature': {'value': 0.7, 'min': 0.0, 'max': 2.0, 'type': 'float'},
        'llm_max_tokens': {'value': 4096, 'min': 100, 'max': 8192, 'type': 'int'},
        'llm_top_p': {'value': 0.9, 'min': 0.0, 'max': 1.0, 'type': 'float'},
        'llm_frequency_penalty': {'value': 0.0, 'min': -2.0, 'max': 2.0, 'type': 'float'},
        'llm_presence_penalty': {'value': 0.0, 'min': -2.0, 'max': 2.0, 'type': 'float'},
        # 嵌入模型参数
        'embedding_chunk_size': {'value': 500, 'min': 100, 'max': 2000, 'type': 'int'},
        'embedding_chunk_overlap': {'value': 50, 'min': 0, 'max': 500, 'type': 'int'},
        'embedding_retrieval_k': {'value': 3, 'min': 1, 'max': 10, 'type': 'int'},
    }

    # 数据库实例缓存（延迟加载）
    _db = None

    @classmethod
    def _get_db(cls):
        """延迟加载数据库实例"""
        if cls._db is None:
            from database import db
            cls._db = db
        return cls._db

    @classmethod
    def get_setting(cls, key: str, default=None):
        """
        动态获取参数值（优先从数据库读取）

        @param key 参数键名
        @param default 默认值
        @return 参数值
        """
        try:
            db = cls._get_db()
            value = db.get_setting(key)
            if value is not None:
                return value
        except Exception:
            pass

        # 如果数据库读取失败，使用默认值
        if key in cls.SETTINGS_DEFAULTS:
            return cls.SETTINGS_DEFAULTS[key]['value']
        return default

    @classmethod
    def get_llm_settings(cls) -> dict:
        """
        获取所有 LLM 相关参数

        @return LLM 参数字典
        """
        return {
            'temperature': cls.get_setting('llm_temperature', cls.DEEPSEEK_TEMPERATURE),
            'max_tokens': cls.get_setting('llm_max_tokens', cls.DEEPSEEK_MAX_TOKENS),
            'top_p': cls.get_setting('llm_top_p', 0.9),
            'frequency_penalty': cls.get_setting('llm_frequency_penalty', 0.0),
            'presence_penalty': cls.get_setting('llm_presence_penalty', 0.0),
        }

    @classmethod
    def get_embedding_settings(cls) -> dict:
        """
        获取所有 Embedding 相关参数

        @return Embedding 参数字典
        """
        return {
            'chunk_size': cls.get_setting('embedding_chunk_size', cls.CHUNK_SIZE),
            'chunk_overlap': cls.get_setting('embedding_chunk_overlap', cls.CHUNK_OVERLAP),
            'retrieval_k': cls.get_setting('embedding_retrieval_k', cls.RETRIEVAL_K),
        }

    @classmethod
    def validate_setting(cls, key: str, value) -> tuple:
        """
        验证参数值是否在有效范围内

        @param key 参数键名
        @param value 参数值
        @return (是否有效, 错误信息)
        """
        if key not in cls.SETTINGS_DEFAULTS:
            return False, f'未知参数: {key}'

        setting = cls.SETTINGS_DEFAULTS[key]
        setting_type = setting['type']
        min_val = setting.get('min')
        max_val = setting.get('max')

        try:
            if setting_type == 'int':
                value = int(value)
            elif setting_type == 'float':
                value = float(value)
        except (ValueError, TypeError):
            return False, f'参数 {key} 必须是 {setting_type} 类型'

        if min_val is not None and value < min_val:
            return False, f'参数 {key} 不能小于 {min_val}'
        if max_val is not None and value > max_val:
            return False, f'参数 {key} 不能大于 {max_val}'

        return True, None

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

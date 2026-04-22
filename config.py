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
    DEEPSEEK_API_BASE = os.getenv('DEEPSEEK_API_BASE', 'https://api.deepseek.com')
    DEEPSEEK_MODEL = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
    DEEPSEEK_TEMPERATURE = float(os.getenv('DEEPSEEK_TEMPERATURE', '0.7'))
    DEEPSEEK_MAX_TOKENS = int(os.getenv('DEEPSEEK_MAX_TOKENS', '4096'))

    SILICONFLOW_API_KEY = os.getenv('SILICONFLOW_API_KEY', '')
    SILICONFLOW_BASE_URL = os.getenv('SILICONFLOW_BASE_URL', 'https://api.siliconflow.cn/v1')
    SILICONFLOW_EMBEDDING_MODEL = os.getenv('SILICONFLOW_EMBEDDING_MODEL', 'BAAI/bge-m3')

    LMSTUDIO_BASE_URL = os.getenv('LMSTUDIO_BASE_URL', 'http://localhost:1234/v1')
    OPENAI_COMPATIBLE_LLM_BASE_URL = os.getenv('OPENAI_COMPATIBLE_LLM_BASE_URL', LMSTUDIO_BASE_URL)
    OPENAI_COMPATIBLE_LLM_API_KEY = os.getenv('OPENAI_COMPATIBLE_LLM_API_KEY', '')
    OPENAI_COMPATIBLE_LLM_MODEL = os.getenv('OPENAI_COMPATIBLE_LLM_MODEL', '')
    OPENAI_COMPATIBLE_EMBEDDING_BASE_URL = os.getenv('OPENAI_COMPATIBLE_EMBEDDING_BASE_URL', LMSTUDIO_BASE_URL)
    OPENAI_COMPATIBLE_EMBEDDING_API_KEY = os.getenv('OPENAI_COMPATIBLE_EMBEDDING_API_KEY', '')
    OPENAI_COMPATIBLE_EMBEDDING_MODEL = os.getenv(
        'OPENAI_COMPATIBLE_EMBEDDING_MODEL',
        os.getenv('LMSTUDIO_EMBEDDING_MODEL', 'text-embedding-qwen3-embedding-8b')
    )
    LMSTUDIO_EMBEDDING_MODEL = os.getenv('LMSTUDIO_EMBEDDING_MODEL', 'text-embedding-qwen3-embedding-8b')
    LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'deepseek')
    EMBEDDING_PROVIDER = os.getenv('EMBEDDING_PROVIDER', 'siliconflow')

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

    LLM_PROVIDER_DEFAULTS = {
        'deepseek': {
            'base_url': DEEPSEEK_API_BASE,
            'api_key': DEEPSEEK_API_KEY,
            'model': DEEPSEEK_MODEL,
        },
        'openai_compatible': {
            'base_url': OPENAI_COMPATIBLE_LLM_BASE_URL,
            'api_key': OPENAI_COMPATIBLE_LLM_API_KEY,
            'model': OPENAI_COMPATIBLE_LLM_MODEL,
        },
    }
    EMBEDDING_PROVIDER_DEFAULTS = {
        'siliconflow': {
            'base_url': SILICONFLOW_BASE_URL,
            'api_key': SILICONFLOW_API_KEY,
            'model': SILICONFLOW_EMBEDDING_MODEL,
        },
        'openai_compatible': {
            'base_url': OPENAI_COMPATIBLE_EMBEDDING_BASE_URL,
            'api_key': OPENAI_COMPATIBLE_EMBEDDING_API_KEY,
            'model': OPENAI_COMPATIBLE_EMBEDDING_MODEL,
        },
    }
    DEFAULT_LLM_PROVIDER_SETTINGS = LLM_PROVIDER_DEFAULTS.get(
        LLM_PROVIDER,
        LLM_PROVIDER_DEFAULTS['deepseek']
    )
    DEFAULT_EMBEDDING_PROVIDER_SETTINGS = EMBEDDING_PROVIDER_DEFAULTS.get(
        EMBEDDING_PROVIDER,
        EMBEDDING_PROVIDER_DEFAULTS['siliconflow']
    )

    # 参数默认值和范围定义
    SETTINGS_DEFAULTS = {
        'llm_provider': {
            'value': LLM_PROVIDER,
            'type': 'string',
            'category': 'llm',
            'description': 'LLM 供应商',
            'choices': ['deepseek', 'openai_compatible'],
        },
        'llm_base_url': {
            'value': DEFAULT_LLM_PROVIDER_SETTINGS['base_url'],
            'type': 'string',
            'category': 'llm',
            'description': 'LLM 接口基地址',
        },
        'llm_api_key': {
            'value': DEFAULT_LLM_PROVIDER_SETTINGS['api_key'],
            'type': 'string',
            'category': 'llm',
            'description': 'LLM 接口 API Key',
            'allow_blank': True,
        },
        'llm_model': {
            'value': DEFAULT_LLM_PROVIDER_SETTINGS['model'],
            'type': 'string',
            'category': 'llm',
            'description': 'LLM 模型名称',
        },
        # 大语言模型参数
        'llm_temperature': {
            'value': 0.7,
            'min': 0.0,
            'max': 2.0,
            'type': 'float',
            'category': 'llm',
            'description': '大语言模型温度参数，控制输出的随机性',
        },
        'llm_max_tokens': {
            'value': 4096,
            'min': 100,
            'max': 8192,
            'type': 'int',
            'category': 'llm',
            'description': '大语言模型最大生成token数',
        },
        'llm_top_p': {
            'value': 0.9,
            'min': 0.0,
            'max': 1.0,
            'type': 'float',
            'category': 'llm',
            'description': '大语言模型核采样参数',
        },
        'llm_frequency_penalty': {
            'value': 0.0,
            'min': -2.0,
            'max': 2.0,
            'type': 'float',
            'category': 'llm',
            'description': '大语言模型频率惩罚参数',
        },
        'llm_presence_penalty': {
            'value': 0.0,
            'min': -2.0,
            'max': 2.0,
            'type': 'float',
            'category': 'llm',
            'description': '大语言模型存在惩罚参数',
        },
        # 嵌入模型参数
        'embedding_provider': {
            'value': EMBEDDING_PROVIDER,
            'type': 'string',
            'category': 'embedding',
            'description': '嵌入模型供应商',
            'choices': ['siliconflow', 'openai_compatible'],
        },
        'embedding_base_url': {
            'value': DEFAULT_EMBEDDING_PROVIDER_SETTINGS['base_url'],
            'type': 'string',
            'category': 'embedding',
            'description': '嵌入模型接口基地址',
        },
        'embedding_api_key': {
            'value': DEFAULT_EMBEDDING_PROVIDER_SETTINGS['api_key'],
            'type': 'string',
            'category': 'embedding',
            'description': '嵌入模型接口 API Key',
            'allow_blank': True,
        },
        'embedding_model': {
            'value': DEFAULT_EMBEDDING_PROVIDER_SETTINGS['model'],
            'type': 'string',
            'category': 'embedding',
            'description': '嵌入模型名称',
        },
        'embedding_chunk_size': {
            'value': 500,
            'min': 100,
            'max': 2000,
            'type': 'int',
            'category': 'embedding',
            'description': '文本分块大小',
        },
        'embedding_chunk_overlap': {
            'value': 50,
            'min': 0,
            'max': 500,
            'type': 'int',
            'category': 'embedding',
            'description': '文本分块重叠大小',
        },
        'embedding_retrieval_k': {
            'value': 3,
            'min': 1,
            'max': 10,
            'type': 'int',
            'category': 'embedding',
            'description': '检索返回的文档数量',
        },
        'embedding_batch_size': {
            'value': 20,
            'min': 1,
            'max': 200,
            'type': 'int',
            'category': 'embedding',
            'description': 'Embedding 批量处理大小',
        },
        'embedding_max_workers': {
            'value': 4,
            'min': 1,
            'max': 32,
            'type': 'int',
            'category': 'embedding',
            'description': 'Embedding 并发处理线程数',
        },
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
    def get_non_empty_setting(cls, key: str, default=''):
        """
        获取非空字符串设置，空值时回退到默认值

        @param key 参数键名
        @param default 默认值
        @return 非空字符串
        """
        value = cls.get_setting(key, None)

        if value is None:
            return default

        if isinstance(value, str):
            stripped_value = value.strip()
            return stripped_value if stripped_value else default

        return value

    @classmethod
    def get_llm_provider_settings(cls) -> dict:
        """
        获取 LLM 提供商配置

        @return LLM 提供商配置字典
        """
        provider = cls.get_non_empty_setting('llm_provider', cls.LLM_PROVIDER)
        provider_defaults = cls.LLM_PROVIDER_DEFAULTS.get(
            provider,
            cls.LLM_PROVIDER_DEFAULTS['deepseek']
        )
        return {
            'provider': provider,
            'base_url': cls.get_non_empty_setting('llm_base_url', provider_defaults['base_url']),
            'api_key': cls.get_non_empty_setting('llm_api_key', provider_defaults['api_key']),
            'model': cls.get_non_empty_setting('llm_model', provider_defaults['model']),
        }

    @classmethod
    def get_embedding_provider_settings(cls) -> dict:
        """
        获取 Embedding 提供商配置

        @return Embedding 提供商配置字典
        """
        provider = cls.get_non_empty_setting('embedding_provider', cls.EMBEDDING_PROVIDER)
        provider_defaults = cls.EMBEDDING_PROVIDER_DEFAULTS.get(
            provider,
            cls.EMBEDDING_PROVIDER_DEFAULTS['siliconflow']
        )
        return {
            'provider': provider,
            'base_url': cls.get_non_empty_setting('embedding_base_url', provider_defaults['base_url']),
            'api_key': cls.get_non_empty_setting('embedding_api_key', provider_defaults['api_key']),
            'model': cls.get_non_empty_setting('embedding_model', provider_defaults['model']),
        }

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
            'batch_size': cls.get_setting('embedding_batch_size', 20),
            'max_workers': cls.get_setting('embedding_max_workers', 4),
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
        choices = setting.get('choices')
        allow_blank = setting.get('allow_blank', False)

        if setting_type == 'string':
            value = '' if value is None else str(value).strip()
            if not value and not allow_blank:
                return False, f'参数 {key} 不能为空'
            if value and choices and value not in choices:
                return False, f'参数 {key} 必须是以下值之一: {", ".join(choices)}'
            return True, None

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

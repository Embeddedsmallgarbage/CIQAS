#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
数据库管理模块 - SQLite 持久化存储
"""

import sqlite3
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from pathlib import Path

from config import Config
from logger import logger


class Database:
    """SQLite 数据库管理类"""

    def __init__(self, db_path: str = None):
        """
        初始化数据库

        @param db_path 数据库文件路径
        """
        self.db_path = db_path or Config.DATABASE_PATH
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    @contextmanager
    def get_connection(self):
        """获取数据库连接上下文管理器"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"数据库操作失败: {e}")
            raise
        finally:
            conn.close()

    def _init_tables(self):
        """初始化数据表"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT '新对话',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                )
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_messages_conversation
                ON messages(conversation_id)
            ''')

            logger.info(f"数据库初始化完成: {self.db_path}")

    def create_conversation(self, conversation_id: str = None, title: str = '新对话') -> str:
        """
        创建新对话

        @param conversation_id 对话ID，不提供则自动生成
        @param title 对话标题
        @return 对话ID
        """
        conv_id = conversation_id or str(uuid.uuid4())

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO conversations (id, title)
                VALUES (?, ?)
            ''', (conv_id, title))

        logger.debug(f"创建对话: {conv_id}")
        return conv_id

    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        获取对话详情

        @param conversation_id 对话ID
        @return 对话信息字典
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id, title, created_at, updated_at
                FROM conversations
                WHERE id = ?
            ''', (conversation_id,))
            row = cursor.fetchone()

            if not row:
                return None

            conversation = dict(row)

            cursor.execute('''
                SELECT role, content, created_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC
            ''', (conversation_id,))

            conversation['messages'] = [dict(m) for m in cursor.fetchall()]

        return conversation

    def list_conversations(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取对话列表

        @param limit 返回数量限制
        @return 对话列表
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT c.id, c.title, c.created_at, c.updated_at,
                       COUNT(m.id) as message_count
                FROM conversations c
                LEFT JOIN messages m ON c.id = m.conversation_id
                GROUP BY c.id
                ORDER BY c.updated_at DESC
                LIMIT ?
            ''', (limit,))

            return [dict(row) for row in cursor.fetchall()]

    def add_message(self, conversation_id: str, role: str, content: str) -> int:
        """
        添加消息到对话

        @param conversation_id 对话ID
        @param role 角色 (user/assistant)
        @param content 消息内容
        @return 消息ID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO messages (conversation_id, role, content)
                VALUES (?, ?, ?)
            ''', (conversation_id, role, content))

            message_id = cursor.lastrowid

            cursor.execute('''
                UPDATE conversations
                SET updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (conversation_id,))

        logger.debug(f"添加消息: conversation={conversation_id}, role={role}")
        return message_id

    def update_conversation_title(self, conversation_id: str, title: str):
        """
        更新对话标题

        @param conversation_id 对话ID
        @param title 新标题
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE conversations
                SET title = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (title, conversation_id))

    def delete_conversation(self, conversation_id: str) -> bool:
        """
        删除对话

        @param conversation_id 对话ID
        @return 是否成功
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM conversations WHERE id = ?', (conversation_id,))
            deleted = cursor.rowcount > 0

        if deleted:
            logger.info(f"删除对话: {conversation_id}")
        return deleted

    def cleanup_old_conversations(self, max_count: int = None):
        """
        清理旧对话，保留最新的 N 条

        @param max_count 最大保留数量
        """
        max_count = max_count or Config.MAX_CONVERSATIONS

        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                DELETE FROM conversations
                WHERE id NOT IN (
                    SELECT id FROM conversations
                    ORDER BY updated_at DESC
                    LIMIT ?
                )
            ''', (max_count,))

            deleted = cursor.rowcount
            if deleted > 0:
                logger.info(f"清理了 {deleted} 条旧对话")


db = Database()

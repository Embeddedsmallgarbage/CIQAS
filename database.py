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

    # 默认管理员账号
    DEFAULT_ADMIN_ID = 'admin_001'

    def __init__(self, db_path: str = None):
        """
        初始化数据库

        @param db_path 数据库文件路径
        """
        self.db_path = db_path or Config.DATABASE_PATH
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()
        self._migrate_user_id()
        self._init_default_admin()
        self._init_default_student_category()
        self._init_default_settings()

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

            # 创建用户表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('admin', 'student')),
                    name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_users_username
                ON users(username)
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_users_role
                ON users(role)
            ''')

            # 创建学生分类表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS student_categories (
                    category_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_student_categories_name
                ON student_categories(name)
            ''')

            # 先创建基础表结构（不包含 user_id，迁移时会添加）
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

            # 检查 users 表是否已有 category_id 列，如果没有则添加
            cursor.execute("PRAGMA table_info(users)")
            user_columns = [column[1] for column in cursor.fetchall()]

            if 'category_id' not in user_columns:
                logger.info("添加 category_id 列到 users 表")
                cursor.execute('''
                    ALTER TABLE users
                    ADD COLUMN category_id TEXT
                    REFERENCES student_categories(category_id) ON DELETE SET NULL
                ''')
                logger.info("成功添加 category_id 列")

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_users_category_id
                ON users(category_id)
            ''')

            # 创建系统参数表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_settings (
                    setting_key TEXT PRIMARY KEY,
                    setting_value TEXT NOT NULL,
                    setting_type TEXT NOT NULL CHECK(setting_type IN ('int', 'float', 'string')),
                    min_value TEXT,
                    max_value TEXT,
                    description TEXT,
                    category TEXT NOT NULL CHECK(category IN ('llm', 'embedding')),
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_system_settings_category
                ON system_settings(category)
            ''')

            logger.info(f"数据库初始化完成: {self.db_path}")

    def _migrate_user_id(self):
        """
        数据库迁移：添加 user_id 列并将现有数据关联到默认管理员账号
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 检查 conversations 表是否已有 user_id 列
            cursor.execute("PRAGMA table_info(conversations)")
            columns = [column[1] for column in cursor.fetchall()]

            if 'user_id' not in columns:
                logger.info("开始数据库迁移：添加 user_id 列")
                try:
                    # 添加 user_id 列（不带 NOT NULL 约束，避免现有数据冲突）
                    cursor.execute('''
                        ALTER TABLE conversations
                        ADD COLUMN user_id TEXT DEFAULT 'admin_001'
                    ''')
                    logger.info("成功添加 user_id 列")

                    # 更新现有数据，将 user_id 设置为默认管理员账号
                    cursor.execute('''
                        UPDATE conversations
                        SET user_id = ?
                        WHERE user_id IS NULL OR user_id = ''
                    ''', (self.DEFAULT_ADMIN_ID,))

                    updated_count = cursor.rowcount
                    logger.info(f"已将 {updated_count} 条现有对话关联到默认管理员账号 '{self.DEFAULT_ADMIN_ID}'")

                    # 创建索引
                    cursor.execute('''
                        CREATE INDEX IF NOT EXISTS idx_conversations_user_id
                        ON conversations(user_id)
                    ''')
                    logger.info("成功创建 user_id 索引")

                except Exception as e:
                    logger.error(f"数据库迁移失败: {e}")
                    raise
            else:
                # 检查是否有 NULL 或空值的 user_id
                cursor.execute('''
                    SELECT COUNT(*) FROM conversations
                    WHERE user_id IS NULL OR user_id = ''
                ''')
                null_count = cursor.fetchone()[0]

                if null_count > 0:
                    logger.info(f"发现 {null_count} 条对话的 user_id 为空，更新为默认管理员账号")
                    cursor.execute('''
                        UPDATE conversations
                        SET user_id = ?
                        WHERE user_id IS NULL OR user_id = ''
                    ''', (self.DEFAULT_ADMIN_ID,))
                    logger.info(f"已更新 {cursor.rowcount} 条对话")

    def create_conversation(self, user_id: str, conversation_id: str = None, title: str = '新对话') -> str:
        """
        创建新对话

        @param user_id 用户ID
        @param conversation_id 对话ID，不提供则自动生成
        @param title 对话标题
        @return 对话ID
        @raises ValueError: 当 user_id 为空时
        """
        if not user_id:
            logger.error("创建对话失败: user_id 不能为空")
            raise ValueError("user_id 不能为空")

        conv_id = conversation_id or str(uuid.uuid4())

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO conversations (id, user_id, title)
                VALUES (?, ?, ?)
            ''', (conv_id, user_id, title))

        logger.info(f"创建对话: {conv_id}, 用户: {user_id}")
        return conv_id

    def get_conversation(self, conversation_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        获取对话详情

        @param conversation_id 对话ID
        @param user_id 用户ID，用于验证权限
        @return 对话信息字典，无权限或不存在返回 None
        @raises ValueError: 当 user_id 为空时
        """
        if not user_id:
            logger.error("获取对话失败: user_id 不能为空")
            raise ValueError("user_id 不能为空")

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 先验证用户是否有权限访问此对话
            cursor.execute('''
                SELECT id, user_id, title, created_at, updated_at
                FROM conversations
                WHERE id = ? AND user_id = ?
            ''', (conversation_id, user_id))
            row = cursor.fetchone()

            if not row:
                logger.warning(f"用户 {user_id} 无权访问对话 {conversation_id} 或对话不存在")
                return None

            conversation = dict(row)

            cursor.execute('''
                SELECT role, content, created_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC
            ''', (conversation_id,))

            conversation['messages'] = [dict(m) for m in cursor.fetchall()]

        logger.debug(f"获取对话: {conversation_id}, 用户: {user_id}")
        return conversation

    def list_conversations(self, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取对话列表

        @param user_id 用户ID，只返回该用户的对话
        @param limit 返回数量限制
        @return 对话列表
        @raises ValueError: 当 user_id 为空时
        """
        if not user_id:
            logger.error("获取对话列表失败: user_id 不能为空")
            raise ValueError("user_id 不能为空")

        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT c.id, c.user_id, c.title, c.created_at, c.updated_at,
                       COUNT(m.id) as message_count
                FROM conversations c
                LEFT JOIN messages m ON c.id = m.conversation_id
                WHERE c.user_id = ?
                GROUP BY c.id
                ORDER BY c.updated_at DESC
                LIMIT ?
            ''', (user_id, limit))

            result = [dict(row) for row in cursor.fetchall()]

        logger.debug(f"获取对话列表: 用户 {user_id}, 数量 {len(result)}")
        return result

    def add_message(self, conversation_id: str, role: str, content: str, user_id: str = None) -> int:
        """
        添加消息到对话

        @param conversation_id 对话ID
        @param role 角色 (user/assistant)
        @param content 消息内容
        @param user_id 用户ID，用于验证权限（可选）
        @return 消息ID
        @raises PermissionError: 当用户无权访问此对话时
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 如果提供了 user_id，验证权限
            if user_id:
                cursor.execute('''
                    SELECT id FROM conversations
                    WHERE id = ? AND user_id = ?
                ''', (conversation_id, user_id))
                if not cursor.fetchone():
                    logger.warning(f"用户 {user_id} 无权向对话 {conversation_id} 添加消息")
                    raise PermissionError(f"无权访问此对话: {conversation_id}")

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

    def update_conversation_title(self, conversation_id: str, title: str, user_id: str = None) -> bool:
        """
        更新对话标题

        @param conversation_id 对话ID
        @param title 新标题
        @param user_id 用户ID，用于验证权限（可选）
        @return 是否成功
        @raises PermissionError: 当用户无权访问此对话时
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 如果提供了 user_id，验证权限
            if user_id:
                cursor.execute('''
                    SELECT id FROM conversations
                    WHERE id = ? AND user_id = ?
                ''', (conversation_id, user_id))
                if not cursor.fetchone():
                    logger.warning(f"用户 {user_id} 无权更新对话 {conversation_id}")
                    raise PermissionError(f"无权访问此对话: {conversation_id}")

            cursor.execute('''
                UPDATE conversations
                SET title = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (title, conversation_id))

            success = cursor.rowcount > 0

        if success:
            logger.info(f"更新对话标题: {conversation_id}, 新标题: {title}")
        return success

    def delete_conversation(self, conversation_id: str, user_id: str) -> bool:
        """
        删除对话

        @param conversation_id 对话ID
        @param user_id 用户ID，用于验证权限
        @return 是否成功
        @raises ValueError: 当 user_id 为空时
        @raises PermissionError: 当用户无权访问此对话时
        """
        if not user_id:
            logger.error("删除对话失败: user_id 不能为空")
            raise ValueError("user_id 不能为空")

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 先验证用户是否有权限删除此对话
            cursor.execute('''
                SELECT id FROM conversations
                WHERE id = ? AND user_id = ?
            ''', (conversation_id, user_id))

            if not cursor.fetchone():
                logger.warning(f"用户 {user_id} 无权删除对话 {conversation_id} 或对话不存在")
                raise PermissionError(f"无权删除此对话: {conversation_id}")

            cursor.execute('DELETE FROM conversations WHERE id = ?', (conversation_id,))
            deleted = cursor.rowcount > 0

        if deleted:
            logger.info(f"删除对话: {conversation_id}, 用户: {user_id}")
        return deleted

    def cleanup_old_conversations(self, user_id: str = None, max_count: int = None):
        """
        清理旧对话，保留最新的 N 条

        @param user_id 用户ID，只清理该用户的对话（可选，不提供则清理所有）
        @param max_count 最大保留数量
        """
        max_count = max_count or Config.MAX_CONVERSATIONS

        with self.get_connection() as conn:
            cursor = conn.cursor()

            if user_id:
                # 只清理指定用户的对话
                cursor.execute('''
                    DELETE FROM conversations
                    WHERE user_id = ? AND id NOT IN (
                        SELECT id FROM conversations
                        WHERE user_id = ?
                        ORDER BY updated_at DESC
                        LIMIT ?
                    )
                ''', (user_id, user_id, max_count))
            else:
                # 清理所有对话（每个用户保留最新的 N 条）
                cursor.execute('''
                    DELETE FROM conversations
                    WHERE id NOT IN (
                        SELECT id FROM (
                            SELECT id, ROW_NUMBER() OVER (
                                PARTITION BY user_id ORDER BY updated_at DESC
                            ) as rn
                            FROM conversations
                        ) WHERE rn <= ?
                    )
                ''', (max_count,))

            deleted = cursor.rowcount
            if deleted > 0:
                logger.info(f"清理了 {deleted} 条旧对话")

    # ==================== 用户管理方法 ====================

    def create_user(self, user_id: str, username: str, password_hash: str, salt: str, role: str, name: str) -> bool:
        """
        创建用户

        @param user_id 用户唯一ID
        @param username 用户名/学号
        @param password_hash 密码哈希
        @param salt 盐值
        @param role 角色 (admin/student)
        @param name 显示名称
        @return 是否创建成功
        @raises ValueError: 当参数无效时
        @raises sqlite3.IntegrityError: 当用户名已存在时
        """
        if not all([user_id, username, password_hash, salt, role, name]):
            logger.error("创建用户失败: 参数不能为空")
            raise ValueError("所有参数都不能为空")

        if role not in ('admin', 'student'):
            logger.error(f"创建用户失败: 无效的角色 '{role}'")
            raise ValueError("角色必须是 'admin' 或 'student'")

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO users (user_id, username, password_hash, salt, role, name)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, username, password_hash, salt, role, name))

            logger.info(f"创建用户成功: {username}, 角色: {role}")
            return True

        except sqlite3.IntegrityError as e:
            logger.error(f"创建用户失败: 用户名 '{username}' 已存在")
            raise sqlite3.IntegrityError(f"用户名 '{username}' 已存在") from e
        except Exception as e:
            logger.error(f"创建用户失败: {e}")
            raise

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """
        根据用户名获取用户

        @param username 用户名
        @return 用户信息字典，不存在返回 None
        """
        if not username:
            logger.error("获取用户失败: username 不能为空")
            return None

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, username, password_hash, salt, role, name, created_at
                FROM users
                WHERE username = ?
            ''', (username,))
            row = cursor.fetchone()

        if row:
            logger.debug(f"获取用户成功: {username}")
            return dict(row)
        else:
            logger.debug(f"用户不存在: {username}")
            return None

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        根据ID获取用户

        @param user_id 用户ID
        @return 用户信息字典，不存在返回 None
        """
        if not user_id:
            logger.error("获取用户失败: user_id 不能为空")
            return None

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, username, password_hash, salt, role, name, created_at
                FROM users
                WHERE user_id = ?
            ''', (user_id,))
            row = cursor.fetchone()

        if row:
            logger.debug(f"获取用户成功: user_id={user_id}")
            return dict(row)
        else:
            logger.debug(f"用户不存在: user_id={user_id}")
            return None

    def list_users(self, role: str = None) -> List[Dict[str, Any]]:
        """
        获取用户列表，可按角色筛选

        @param role 角色筛选 (admin/student)，None 表示不过滤
        @return 用户列表
        @raises ValueError: 当角色无效时
        """
        if role is not None and role not in ('admin', 'student'):
            logger.error(f"获取用户列表失败: 无效的角色 '{role}'")
            raise ValueError("角色必须是 'admin' 或 'student'")

        with self.get_connection() as conn:
            cursor = conn.cursor()

            if role:
                cursor.execute('''
                    SELECT user_id, username, role, name, created_at
                    FROM users
                    WHERE role = ?
                    ORDER BY created_at DESC
                ''', (role,))
            else:
                cursor.execute('''
                    SELECT user_id, username, role, name, created_at
                    FROM users
                    ORDER BY created_at DESC
                ''')

            result = [dict(row) for row in cursor.fetchall()]

        logger.debug(f"获取用户列表: 角色={role}, 数量={len(result)}")
        return result

    def delete_user(self, username: str) -> bool:
        """
        删除用户

        @param username 用户名
        @return 是否删除成功
        @raises ValueError: 当 username 为空时
        """
        if not username:
            logger.error("删除用户失败: username 不能为空")
            raise ValueError("username 不能为空")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM users WHERE username = ?', (username,))
            deleted = cursor.rowcount > 0

        if deleted:
            logger.info(f"删除用户成功: {username}")
        else:
            logger.warning(f"删除用户失败: 用户 '{username}' 不存在")
        return deleted

    def update_user(self, username: str, **kwargs) -> bool:
        """
        更新用户信息

        @param username 用户名
        @param kwargs 要更新的字段 (password_hash, salt, role, name)
        @return 是否更新成功
        @raises ValueError: 当 username 为空或字段无效时
        """
        if not username:
            logger.error("更新用户失败: username 不能为空")
            raise ValueError("username 不能为空")

        # 允许的字段
        allowed_fields = {'password_hash', 'salt', 'role', 'name'}

        # 过滤无效字段
        valid_updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not valid_updates:
            logger.error("更新用户失败: 没有有效的更新字段")
            raise ValueError(f"无效的更新字段，允许的字段: {allowed_fields}")

        # 验证角色
        if 'role' in valid_updates and valid_updates['role'] not in ('admin', 'student'):
            logger.error(f"更新用户失败: 无效的角色 '{valid_updates['role']}'")
            raise ValueError("角色必须是 'admin' 或 'student'")

        # 构建更新语句
        set_clause = ', '.join([f"{k} = ?" for k in valid_updates.keys()])
        values = list(valid_updates.values()) + [username]

        with self.get_connection() as conn:
            cursor = conn.cursor()
            sql = f"UPDATE users SET {set_clause} WHERE username = ?"
            cursor.execute(sql, values)
            updated = cursor.rowcount > 0

        if updated:
            logger.info(f"更新用户成功: {username}, 字段: {list(valid_updates.keys())}")
        else:
            logger.warning(f"更新用户失败: 用户 '{username}' 不存在")
        return updated

    def _init_default_admin(self):
        """
        初始化默认管理员账号
        - 检查是否存在管理员账号
        - 如果不存在，创建默认管理员账号
        """
        try:
            # 检查是否已存在管理员账号
            admin_users = self.list_users(role='admin')

            if admin_users:
                logger.info(f"已存在 {len(admin_users)} 个管理员账号，跳过默认管理员创建")
                return

            # 创建默认管理员账号
            import hashlib
            import secrets

            default_user_id = 'admin_001'
            default_username = '202203010104'
            default_password = '123456'

            # 生成盐值
            salt = secrets.token_hex(16)

            # 计算密码哈希 (PBKDF2-HMAC-SHA256，与 auth.py 保持一致)
            password_hash = hashlib.pbkdf2_hmac(
                'sha256',
                default_password.encode('utf-8'),
                salt.encode('utf-8'),
                100000
            ).hex()

            self.create_user(
                user_id=default_user_id,
                username=default_username,
                password_hash=password_hash,
                salt=salt,
                role='admin',
                name='系统管理员'
            )

            logger.info(f"已创建默认管理员账号: {default_username}")

        except Exception as e:
            logger.error(f"初始化默认管理员账号失败: {e}")
            raise

    # ==================== 学生分类管理方法 ====================

    def create_category(self, category_id: str, name: str) -> bool:
        """
        创建学生分类

        @param category_id 分类唯一ID
        @param name 分类名称
        @return 是否创建成功
        @raises ValueError: 当参数无效时
        @raises sqlite3.IntegrityError: 当分类ID已存在时
        """
        if not category_id:
            logger.error("创建分类失败: category_id 不能为空")
            raise ValueError("category_id 不能为空")
        if not name:
            logger.error("创建分类失败: name 不能为空")
            raise ValueError("name 不能为空")

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO student_categories (category_id, name)
                    VALUES (?, ?)
                ''', (category_id, name))

            logger.info(f"创建分类成功: {category_id}, 名称: {name}")
            return True

        except sqlite3.IntegrityError as e:
            logger.error(f"创建分类失败: 分类ID '{category_id}' 已存在")
            raise sqlite3.IntegrityError(f"分类ID '{category_id}' 已存在") from e
        except Exception as e:
            logger.error(f"创建分类失败: {e}")
            raise

    def get_category(self, category_id: str) -> Optional[Dict[str, Any]]:
        """
        获取分类详情

        @param category_id 分类ID
        @return 分类信息字典，不存在返回 None
        """
        if not category_id:
            logger.error("获取分类失败: category_id 不能为空")
            return None

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT category_id, name, created_at
                FROM student_categories
                WHERE category_id = ?
            ''', (category_id,))
            row = cursor.fetchone()

        if row:
            logger.debug(f"获取分类成功: {category_id}")
            return dict(row)
        else:
            logger.debug(f"分类不存在: {category_id}")
            return None

    def list_categories(self) -> List[Dict[str, Any]]:
        """
        获取所有分类列表

        @return 分类列表，包含每个分类的学生数量
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT sc.category_id, sc.name, sc.created_at,
                       COUNT(u.user_id) as student_count
                FROM student_categories sc
                LEFT JOIN users u ON sc.category_id = u.category_id AND u.role = 'student'
                GROUP BY sc.category_id
                ORDER BY sc.created_at ASC
            ''')
            result = [dict(row) for row in cursor.fetchall()]

        logger.debug(f"获取分类列表: 数量={len(result)}")
        return result

    def delete_category(self, category_id: str) -> bool:
        """
        删除分类（仅当分类下没有学生时）

        @param category_id 分类ID
        @return 是否删除成功
        @raises ValueError: 当分类下还有学生时
        """
        if not category_id:
            logger.error("删除分类失败: category_id 不能为空")
            raise ValueError("category_id 不能为空")

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 检查分类下是否有学生
            cursor.execute('''
                SELECT COUNT(*) FROM users
                WHERE category_id = ? AND role = 'student'
            ''', (category_id,))
            student_count = cursor.fetchone()[0]

            if student_count > 0:
                logger.warning(f"删除分类失败: 分类 '{category_id}' 下还有 {student_count} 名学生")
                raise ValueError(f"分类下还有 {student_count} 名学生，无法删除")

            cursor.execute('DELETE FROM student_categories WHERE category_id = ?', (category_id,))
            deleted = cursor.rowcount > 0

        if deleted:
            logger.info(f"删除分类成功: {category_id}")
        else:
            logger.warning(f"删除分类失败: 分类 '{category_id}' 不存在")
        return deleted

    def update_user_category(self, username: str, category_id: str) -> bool:
        """
        更新用户所属分类

        @param username 用户名
        @param category_id 分类ID，None 表示移除分类
        @return 是否更新成功
        @raises ValueError: 当用户名为空时
        """
        if not username:
            logger.error("更新用户分类失败: username 不能为空")
            raise ValueError("username 不能为空")

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 如果提供了 category_id，验证分类是否存在
            if category_id:
                cursor.execute('SELECT category_id FROM student_categories WHERE category_id = ?', (category_id,))
                if not cursor.fetchone():
                    logger.error(f"更新用户分类失败: 分类 '{category_id}' 不存在")
                    raise ValueError(f"分类 '{category_id}' 不存在")

            cursor.execute('''
                UPDATE users
                SET category_id = ?
                WHERE username = ?
            ''', (category_id, username))
            updated = cursor.rowcount > 0

        if updated:
            logger.info(f"更新用户分类成功: {username}, 分类: {category_id}")
        else:
            logger.warning(f"更新用户分类失败: 用户 '{username}' 不存在")
        return updated

    def get_users_by_category(self, category_id: str) -> List[Dict[str, Any]]:
        """
        获取某分类下的所有学生

        @param category_id 分类ID
        @return 学生用户列表
        @raises ValueError: 当 category_id 为空时
        """
        if not category_id:
            logger.error("获取分类学生失败: category_id 不能为空")
            raise ValueError("category_id 不能为空")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, username, role, name, created_at, category_id
                FROM users
                WHERE category_id = ? AND role = 'student'
                ORDER BY created_at DESC
            ''', (category_id,))
            result = [dict(row) for row in cursor.fetchall()]

        logger.debug(f"获取分类学生: 分类={category_id}, 数量={len(result)}")
        return result

    def get_student_tree(self) -> List[Dict[str, Any]]:
        """
        获取学生分类树（按分类组织的学生列表）

        @return 分类树列表，每个分类包含其下的学生列表
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 获取所有分类
            cursor.execute('''
                SELECT category_id, name, created_at
                FROM student_categories
                ORDER BY created_at ASC
            ''')
            categories = [dict(row) for row in cursor.fetchall()]

            # 获取所有学生及其分类
            cursor.execute('''
                SELECT user_id, username, name, created_at, category_id
                FROM users
                WHERE role = 'student'
                ORDER BY created_at DESC
            ''')
            students = [dict(row) for row in cursor.fetchall()]

        # 组织成树形结构
        category_map = {cat['category_id']: cat for cat in categories}
        for cat in categories:
            cat['students'] = []

        # 将学生添加到对应分类
        uncategorized = []
        for student in students:
            cat_id = student.get('category_id')
            if cat_id and cat_id in category_map:
                category_map[cat_id]['students'].append(student)
            else:
                uncategorized.append(student)

        # 构建结果
        result = {
            'categories': categories,
            'uncategorized': uncategorized
        }

        logger.debug(f"获取学生分类树: 分类数={len(categories)}, 未分类学生数={len(uncategorized)}")
        return result

    def _init_default_student_category(self):
        """
        初始化默认学生分类
        - 检查是否存在"学生"默认分类
        - 如果不存在，创建默认分类（category_id='cat_default', name='学生'）
        """
        try:
            # 检查是否已存在默认分类
            default_category = self.get_category('cat_default')

            if default_category:
                logger.info("默认学生分类已存在，跳过创建")
                return

            # 创建默认分类
            self.create_category(
                category_id='cat_default',
                name='学生'
            )

            logger.info("已创建默认学生分类: cat_default")

        except Exception as e:
            logger.error(f"初始化默认学生分类失败: {e}")
            raise

    # ==================== 系统参数管理方法 ====================

    def _init_default_settings(self):
        """
        初始化默认系统参数
        - 大语言模型参数
        - 嵌入模型参数
        """
        default_settings = [
            # 大语言模型参数
            {
                'key': 'llm_temperature',
                'value': '0.7',
                'type': 'float',
                'min': '0.0',
                'max': '2.0',
                'description': '大语言模型温度参数，控制输出的随机性',
                'category': 'llm'
            },
            {
                'key': 'llm_max_tokens',
                'value': '4096',
                'type': 'int',
                'min': '100',
                'max': '8192',
                'description': '大语言模型最大生成token数',
                'category': 'llm'
            },
            {
                'key': 'llm_top_p',
                'value': '0.9',
                'type': 'float',
                'min': '0.0',
                'max': '1.0',
                'description': '大语言模型核采样参数',
                'category': 'llm'
            },
            {
                'key': 'llm_frequency_penalty',
                'value': '0.0',
                'type': 'float',
                'min': '-2.0',
                'max': '2.0',
                'description': '大语言模型频率惩罚参数',
                'category': 'llm'
            },
            {
                'key': 'llm_presence_penalty',
                'value': '0.0',
                'type': 'float',
                'min': '-2.0',
                'max': '2.0',
                'description': '大语言模型存在惩罚参数',
                'category': 'llm'
            },
            # 嵌入模型参数
            {
                'key': 'embedding_chunk_size',
                'value': '500',
                'type': 'int',
                'min': '100',
                'max': '2000',
                'description': '文本分块大小',
                'category': 'embedding'
            },
            {
                'key': 'embedding_chunk_overlap',
                'value': '50',
                'type': 'int',
                'min': '0',
                'max': '500',
                'description': '文本分块重叠大小',
                'category': 'embedding'
            },
            {
                'key': 'embedding_retrieval_k',
                'value': '3',
                'type': 'int',
                'min': '1',
                'max': '10',
                'description': '检索返回的文档数量',
                'category': 'embedding'
            }
        ]

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                for setting in default_settings:
                    # 检查参数是否已存在
                    cursor.execute('''
                        SELECT setting_key FROM system_settings WHERE setting_key = ?
                    ''', (setting['key'],))

                    if not cursor.fetchone():
                        # 插入默认参数
                        cursor.execute('''
                            INSERT INTO system_settings
                            (setting_key, setting_value, setting_type, min_value, max_value, description, category)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            setting['key'],
                            setting['value'],
                            setting['type'],
                            setting['min'],
                            setting['max'],
                            setting['description'],
                            setting['category']
                        ))
                        logger.info(f"初始化默认参数: {setting['key']} = {setting['value']}")

            logger.info("系统参数初始化完成")

        except Exception as e:
            logger.error(f"初始化默认系统参数失败: {e}")
            raise

    def get_setting(self, key: str, default=None):
        """
        获取参数值

        @param key 参数键名
        @param default 默认值，当参数不存在时返回
        @return 参数值（根据类型自动转换），不存在返回 default
        """
        if not key:
            logger.error("获取参数失败: key 不能为空")
            return default

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT setting_value, setting_type
                    FROM system_settings
                    WHERE setting_key = ?
                ''', (key,))
                row = cursor.fetchone()

            if not row:
                logger.debug(f"参数不存在: {key}, 返回默认值: {default}")
                return default

            value_str = row['setting_value']
            value_type = row['setting_type']

            # 根据类型转换值
            if value_type == 'int':
                return int(value_str)
            elif value_type == 'float':
                return float(value_str)
            else:
                return value_str

        except Exception as e:
            logger.error(f"获取参数失败: {key}, 错误: {e}")
            return default

    def set_setting(self, key: str, value) -> bool:
        """
        设置参数值

        @param key 参数键名
        @param value 参数值
        @return 是否设置成功
        @raises ValueError: 当参数不存在或值超出范围时
        """
        if not key:
            logger.error("设置参数失败: key 不能为空")
            raise ValueError("key 不能为空")

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # 检查参数是否存在并获取类型和范围
                cursor.execute('''
                    SELECT setting_type, min_value, max_value
                    FROM system_settings
                    WHERE setting_key = ?
                ''', (key,))
                row = cursor.fetchone()

                if not row:
                    logger.error(f"设置参数失败: 参数 '{key}' 不存在")
                    raise ValueError(f"参数 '{key}' 不存在")

                setting_type = row['setting_type']
                min_value = row['min_value']
                max_value = row['max_value']

                # 转换为字符串存储
                value_str = str(value)

                # 验证类型
                try:
                    if setting_type == 'int':
                        int_value = int(value)
                    elif setting_type == 'float':
                        float_value = float(value)
                except (ValueError, TypeError):
                    logger.error(f"设置参数失败: 参数 '{key}' 的值 '{value}' 不是有效的 {setting_type} 类型")
                    raise ValueError(f"参数 '{key}' 的值必须是 {setting_type} 类型")

                # 验证范围
                if setting_type in ('int', 'float'):
                    current_value = float(value)
                    if min_value is not None:
                        min_val = float(min_value)
                        if current_value < min_val:
                            logger.error(f"设置参数失败: 参数 '{key}' 的值 {value} 小于最小值 {min_value}")
                            raise ValueError(f"参数 '{key}' 的值不能小于 {min_value}")
                    if max_value is not None:
                        max_val = float(max_value)
                        if current_value > max_val:
                            logger.error(f"设置参数失败: 参数 '{key}' 的值 {value} 大于最大值 {max_value}")
                            raise ValueError(f"参数 '{key}' 的值不能大于 {max_value}")

                # 更新参数值
                cursor.execute('''
                    UPDATE system_settings
                    SET setting_value = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE setting_key = ?
                ''', (value_str, key))

                updated = cursor.rowcount > 0

            if updated:
                logger.info(f"设置参数成功: {key} = {value}")
            return updated

        except (ValueError, sqlite3.Error):
            raise
        except Exception as e:
            logger.error(f"设置参数失败: {key}, 错误: {e}")
            raise

    def get_all_settings(self, category: str = None) -> List[Dict[str, Any]]:
        """
        获取所有参数

        @param category 参数类别筛选 (llm/embedding)，None 表示不过滤
        @return 参数列表
        @raises ValueError: 当类别无效时
        """
        if category is not None and category not in ('llm', 'embedding'):
            logger.error(f"获取参数列表失败: 无效的类别 '{category}'")
            raise ValueError("类别必须是 'llm' 或 'embedding'")

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                if category:
                    cursor.execute('''
                        SELECT setting_key, setting_value, setting_type,
                               min_value, max_value, description, category, updated_at
                        FROM system_settings
                        WHERE category = ?
                        ORDER BY category, setting_key
                    ''', (category,))
                else:
                    cursor.execute('''
                        SELECT setting_key, setting_value, setting_type,
                               min_value, max_value, description, category, updated_at
                        FROM system_settings
                        ORDER BY category, setting_key
                    ''')

                rows = cursor.fetchall()
                result = []

                for row in rows:
                    setting = dict(row)
                    # 根据类型转换值
                    value_type = setting['setting_type']
                    value_str = setting['setting_value']

                    if value_type == 'int':
                        setting['value'] = int(value_str)
                    elif value_type == 'float':
                        setting['value'] = float(value_str)
                    else:
                        setting['value'] = value_str

                    result.append(setting)

            logger.debug(f"获取参数列表: 类别={category}, 数量={len(result)}")
            return result

        except Exception as e:
            logger.error(f"获取参数列表失败: {e}")
            raise

    def reset_settings_to_default(self) -> bool:
        """
        恢复所有参数为默认值

        @return 是否恢复成功
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # 删除所有现有参数
                cursor.execute('DELETE FROM system_settings')

            # 重新初始化默认参数
            self._init_default_settings()

            logger.info("所有参数已恢复为默认值")
            return True

        except Exception as e:
            logger.error(f"恢复默认参数失败: {e}")
            raise


db = Database()

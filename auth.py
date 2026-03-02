#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
用户认证模块
支持管理员和学生角色登录
"""

import hashlib
import secrets
from datetime import timedelta
from functools import wraps
from flask import session, redirect, url_for, flash
from typing import Optional, Dict, Callable

from logger import logger


class UserRole:
    """用户角色常量"""
    ADMIN = 'admin'
    STUDENT = 'student'


class User:
    """用户数据类"""
    
    def __init__(self, user_id: str, username: str, role: str, name: str):
        """
        初始化用户对象
        
        @param user_id 用户ID
        @param username 用户名
        @param role 角色
        @param name 显示名称
        """
        self.user_id = user_id
        self.username = username
        self.role = role
        self.name = name
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'user_id': self.user_id,
            'username': self.username,
            'role': self.role,
            'name': self.name
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'User':
        """从字典创建"""
        return cls(
            user_id=data.get('user_id'),
            username=data.get('username'),
            role=data.get('role'),
            name=data.get('name')
        )
    
    def is_admin(self) -> bool:
        """是否为管理员"""
        return self.role == UserRole.ADMIN


class UserManager:
    """用户管理器"""
    
    def __init__(self):
        """初始化用户管理器"""
        self._users: Dict[str, Dict] = {}
        self._init_default_users()
    
    def _hash_password(self, password: str, salt: str = None) -> tuple:
        """
        哈希密码
        
        @param password 原始密码
        @param salt 盐值，如果为 None 则生成新的
        @return (哈希后的密码, 盐值)
        """
        if salt is None:
            salt = secrets.token_hex(16)
        
        hashed = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        )
        return hashed.hex(), salt
    
    def _init_default_users(self):
        """初始化默认用户"""
        admin_password_hash, admin_salt = self._hash_password('123456')
        
        self._users = {
            '202203010104': {
                'user_id': 'admin_001',
                'username': '202203010104',
                'password_hash': admin_password_hash,
                'salt': admin_salt,
                'role': UserRole.ADMIN,
                'name': '管理员'
            }
        }
        
        logger.info("用户管理器初始化完成，已加载默认管理员账号")
    
    def verify_user(self, username: str, password: str) -> Optional[User]:
        """
        验证用户登录
        
        @param username 用户名
        @param password 密码
        @return 验证成功返回 User 对象，失败返回 None
        """
        user_data = self._users.get(username)
        
        if not user_data:
            logger.warning(f"登录失败: 用户不存在 - {username}")
            return None
        
        password_hash, _ = self._hash_password(password, user_data['salt'])
        
        if password_hash != user_data['password_hash']:
            logger.warning(f"登录失败: 密码错误 - {username}")
            return None
        
        logger.info(f"用户登录成功: {username} ({user_data['role']})")
        
        return User(
            user_id=user_data['user_id'],
            username=user_data['username'],
            role=user_data['role'],
            name=user_data['name']
        )
    
    def add_user(self, username: str, password: str, role: str, name: str) -> bool:
        """
        添加新用户
        
        @param username 用户名
        @param password 密码
        @param role 角色
        @param name 显示名称
        @return 是否成功
        """
        if username in self._users:
            return False
        
        password_hash, salt = self._hash_password(password)
        
        self._users[username] = {
            'user_id': f"{role}_{secrets.token_hex(4)}",
            'username': username,
            'password_hash': password_hash,
            'salt': salt,
            'role': role,
            'name': name
        }
        
        logger.info(f"新用户已添加: {username} ({role})")
        return True
    
    def get_user(self, username: str) -> Optional[Dict]:
        """获取用户信息（不含密码）"""
        user_data = self._users.get(username)
        if user_data:
            return {
                'user_id': user_data['user_id'],
                'username': user_data['username'],
                'role': user_data['role'],
                'name': user_data['name']
            }
        return None
    
    def list_students(self) -> list:
        """
        获取所有学生列表
        
        @return 学生列表
        """
        students = []
        for username, data in self._users.items():
            if data['role'] == UserRole.STUDENT:
                students.append({
                    'username': username,
                    'name': data['name'],
                    'user_id': data['user_id']
                })
        return students
    
    def delete_user(self, username: str) -> bool:
        """
        删除用户
        
        @param username 用户名
        @return 是否成功
        """
        if username not in self._users:
            return False
        
        user_data = self._users[username]
        if user_data['role'] == UserRole.ADMIN:
            return False
        
        del self._users[username]
        logger.info(f"用户已删除: {username}")
        return True


user_manager = UserManager()


class AuthManager:
    """认证管理器"""
    
    SESSION_KEY = 'user'
    SESSION_PERMANENT = True
    SESSION_LIFETIME = timedelta(hours=24)
    
    @classmethod
    def login(cls, user: User) -> None:
        """
        登录用户，创建会话
        
        @param user 用户对象
        """
        session.permanent = cls.SESSION_PERMANENT
        session[cls.SESSION_KEY] = user.to_dict()
        logger.info(f"会话已创建: {user.username}")
    
    @classmethod
    def logout(cls) -> None:
        """登出用户，清除会话"""
        user = cls.get_current_user()
        if user:
            logger.info(f"用户登出: {user.username}")
        session.pop(cls.SESSION_KEY, None)
    
    @classmethod
    def get_current_user(cls) -> Optional[User]:
        """获取当前登录用户"""
        user_data = session.get(cls.SESSION_KEY)
        if user_data:
            return User.from_dict(user_data)
        return None
    
    @classmethod
    def is_logged_in(cls) -> bool:
        """检查是否已登录"""
        return cls.SESSION_KEY in session
    
    @classmethod
    def is_admin(cls) -> bool:
        """检查当前用户是否为管理员"""
        user = cls.get_current_user()
        return user is not None and user.is_admin()


def login_required(f: Callable) -> Callable:
    """
    登录验证装饰器
    
    @param f 被装饰的函数
    @return 装饰后的函数
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not AuthManager.is_logged_in():
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f: Callable) -> Callable:
    """
    管理员权限验证装饰器
    
    @param f 被装饰的函数
    @return 装饰后的函数
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not AuthManager.is_logged_in():
            return redirect(url_for('login'))
        if not AuthManager.is_admin():
            flash('您没有权限访问此功能', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

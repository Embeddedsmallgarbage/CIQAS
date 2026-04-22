#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Flask 后端主程序
"""

import os
import re
import json
import secrets
import uuid
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, Response, stream_with_context, redirect, url_for, flash

from config import Config
from logger import logger
from database import db
from rag_engine import QASystem
from build_db import KnowledgeBaseBuilder
from auth import AuthManager, user_manager, login_required, admin_required


def safe_filename(filename: str) -> str:
    """
    安全文件名处理，支持中文
    
    @param filename 原始文件名
    @return 安全的文件名
    """
    filename = re.sub(r'[/\\]', '_', filename)
    filename = re.sub(r'[<>:"|?*]', '', filename)
    filename = filename.strip()
    if not filename:
        filename = 'unnamed_file'
    return filename


Config.ensure_directories()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = Config.UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_hex(32))
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

qa_system = None
qa_system_error = None
kb_builder = None
kb_builder_error = None


def get_qa_system():
    """延迟初始化问答系统，避免缺少配置时应用无法启动。"""
    global qa_system, qa_system_error

    if qa_system is not None:
        return qa_system

    if qa_system_error is not None:
        return None

    try:
        qa_system = QASystem()
    except Exception as e:
        qa_system_error = str(e)
        logger.error(f"问答系统初始化失败: {e}")
        return None

    return qa_system


def get_kb_builder():
    """延迟初始化知识库构建器，避免缺少配置时应用无法启动。"""
    global kb_builder, kb_builder_error

    if kb_builder is not None:
        return kb_builder

    if kb_builder_error is not None:
        return None

    try:
        kb_builder = KnowledgeBaseBuilder()
    except Exception as e:
        kb_builder_error = str(e)
        logger.error(f"知识库构建器初始化失败: {e}")
        return None

    return kb_builder


def get_service_error_message() -> str:
    """获取当前服务不可用的错误提示。"""
    return qa_system_error or kb_builder_error or '系统服务暂时不可用，请检查配置'


def clear_service_cache(target: str = 'all'):
    """清除延迟初始化服务缓存，允许在配置变更后重新初始化。"""
    global qa_system, qa_system_error, kb_builder, kb_builder_error

    if target in ('all', 'qa'):
        qa_system = None
        qa_system_error = None

    if target in ('all', 'kb'):
        kb_builder = None
        kb_builder_error = None


def build_stream_error_response(message: str, status_code: int = 503) -> Response:
    """返回 SSE 格式的错误响应，兼容前端流式解析。"""
    data = json.dumps({
        'type': 'error',
        'message': message
    }, ensure_ascii=False)
    return Response(f"data: {data}\n\n", mimetype='text/event-stream', status=status_code)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    登录页面
    
    @return 登录页面或重定向
    """
    if AuthManager.is_logged_in():
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('请输入账号和密码', 'error')
            return render_template('login.html')
        
        user = user_manager.verify_user(username, password)
        
        if user:
            AuthManager.login(user)
            return redirect(url_for('index'))
        else:
            flash('账号或密码错误', 'error')
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    """
    登出
    
    @return 重定向到登录页
    """
    AuthManager.logout()
    return redirect(url_for('login'))


@app.route('/api/user/info')
@login_required
def user_info():
    """
    获取当前用户信息
    
    @return 用户信息 JSON
    """
    user = AuthManager.get_current_user()
    if user:
        return jsonify({
            'logged_in': True,
            'user': user.to_dict()
        })
    return jsonify({'logged_in': False, 'user': None})


@app.route('/')
@login_required
def index():
    """主页面"""
    user = AuthManager.get_current_user()
    return render_template('index.html', user=user)


@app.route('/health')
def health():
    """健康检查端点"""
    qa = get_qa_system()
    return jsonify({
        'status': 'healthy',
        'kb_ready': qa.is_db_ready() if qa else False,
        'service_error': get_service_error_message() if not qa else None,
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/chat', methods=['POST'])
@login_required
def chat():
    """处理聊天请求"""
    data = request.get_json(silent=True) or {}
    question = data.get('question', '')
    conversation_id = data.get('conversation_id')
    stream = data.get('stream', False)

    if not question:
        if stream:
            return build_stream_error_response('问题不能为空', status_code=400)
        return jsonify({'error': '问题不能为空'}), 400

    qa = get_qa_system()
    if not qa:
        message = f"问答系统当前不可用: {get_service_error_message()}"
        if stream:
            return build_stream_error_response(message)
        return jsonify({'error': message}), 503

    current_user = AuthManager.get_current_user()
    user_id = current_user.user_id if current_user else None

    if not conversation_id:
        conversation_id = db.create_conversation(user_id=user_id)
    else:
        conversation = db.get_conversation(conversation_id, user_id=user_id)
        if not conversation:
            conversation_id = db.create_conversation(user_id=user_id)

    db.add_message(conversation_id, 'user', question, user_id=user_id)

    user_messages = db.get_conversation(conversation_id, user_id=user_id).get('messages', [])
    user_msg_count = sum(1 for m in user_messages if m['role'] == 'user')
    if user_msg_count == 1:
        title = question[:20] + '...' if len(question) > 20 else question
        db.update_conversation_title(conversation_id, title, user_id=user_id)

    if stream:
        return Response(
            stream_with_context(generate_stream_response(question, conversation_id, user_id)),
            mimetype='text/event-stream'
        )

    answer, source_docs = qa.get_answer(question)
    sources = format_sources(source_docs)

    db.add_message(conversation_id, 'assistant', answer, user_id=user_id, sources=sources)

    logger.info(f"问答完成: conversation={conversation_id}, user={user_id}")

    return jsonify({
        'answer': answer,
        'sources': sources,
        'conversation_id': conversation_id
    })


def generate_stream_response(question: str, conversation_id: str, user_id: str = None):
    """生成流式响应"""
    full_answer = ""
    sources = []
    qa = get_qa_system()

    if not qa:
        error_data = json.dumps({
            'type': 'error',
            'message': f"问答系统当前不可用: {get_service_error_message()}"
        }, ensure_ascii=False)
        yield f"data: {error_data}\n\n"
        return

    try:
        for chunk, docs in qa.get_answer_stream(question):
            full_answer += chunk
            if not sources and docs:
                sources = format_sources(docs)

            data = json.dumps({
                'type': 'chunk',
                'content': chunk
            }, ensure_ascii=False)
            yield f"data: {data}\n\n"

        db.add_message(conversation_id, 'assistant', full_answer, user_id=user_id, sources=sources)

        done_data = json.dumps({
            'type': 'done',
            'sources': sources,
            'conversation_id': conversation_id
        }, ensure_ascii=False)
        yield f"data: {done_data}\n\n"

        logger.info(f"流式问答完成: conversation={conversation_id}, user={user_id}")

    except Exception as e:
        logger.error(f"流式响应错误: {e}")
        error_data = json.dumps({
            'type': 'error',
            'message': str(e)
        }, ensure_ascii=False)
        yield f"data: {error_data}\n\n"


def format_sources(source_docs) -> list:
    """格式化来源文档"""
    sources = []
    for doc in source_docs:
        sources.append({
            'source': doc.metadata.get('source', '未知文件'),
            'content': doc.page_content[:200] + '...' if len(doc.page_content) > 200 else doc.page_content
        })
    return sources


@app.route('/api/conversations', methods=['GET'])
@login_required
def get_conversations():
    """获取当前用户的对话列表"""
    current_user = AuthManager.get_current_user()
    user_id = current_user.user_id if current_user else None
    conv_list = db.list_conversations(user_id=user_id)
    return jsonify(conv_list)


@app.route('/api/conversations/<conversation_id>', methods=['GET'])
@login_required
def get_conversation(conversation_id):
    """获取单个对话详情"""
    current_user = AuthManager.get_current_user()
    user_id = current_user.user_id if current_user else None
    conversation = db.get_conversation(conversation_id, user_id=user_id)

    if not conversation:
        return jsonify({'error': '对话不存在'}), 404

    return jsonify(conversation)


@app.route('/api/conversations', methods=['POST'])
@login_required
def create_conversation_endpoint():
    """创建新对话"""
    current_user = AuthManager.get_current_user()
    user_id = current_user.user_id if current_user else None
    conv_id = db.create_conversation(user_id=user_id)
    conversation = db.get_conversation(conv_id, user_id=user_id)

    return jsonify({
        'id': conv_id,
        'title': conversation['title'],
        'timestamp': conversation['created_at']
    })


@app.route('/api/conversations/<conversation_id>', methods=['DELETE'])
@login_required
def delete_conversation_endpoint(conversation_id):
    """删除对话"""
    current_user = AuthManager.get_current_user()
    user_id = current_user.user_id if current_user else None

    try:
        success = db.delete_conversation(conversation_id, user_id=user_id)
    except PermissionError:
        return jsonify({'error': '无权删除此对话'}), 403

    if not success:
        return jsonify({'error': '对话不存在'}), 404

    conversations = db.list_conversations(user_id=user_id, limit=1)
    new_current_id = conversations[0]['id'] if conversations else None

    return jsonify({
        'success': True,
        'new_current_id': new_current_id
    })


@app.route('/api/kb/status', methods=['GET'])
@login_required
def kb_status():
    """获取知识库状态"""
    qa = get_qa_system()
    kb = get_kb_builder()
    return jsonify({
        'ready': qa.is_db_ready() if qa else False,
        'documents': kb.list_documents() if kb else [],
        'categories': kb.list_documents_by_category() if kb else {},
        'service_error': get_service_error_message() if not qa or not kb else None,
    })


@app.route('/api/kb/categories', methods=['GET'])
@admin_required
def get_categories():
    """获取文档分类列表（仅管理员）"""
    from build_db import DocumentCategory
    return jsonify(DocumentCategory.get_all_categories())


@app.route('/api/kb/custom-categories', methods=['GET'])
@admin_required
def get_custom_categories():
    """获取自定义文档分类列表（仅管理员）"""
    from build_db import DocumentCategory
    return jsonify(DocumentCategory.get_custom_categories())


@app.route('/api/kb/custom-categories', methods=['POST'])
@admin_required
def create_custom_category():
    """创建自定义文档分类（仅管理员）"""
    from build_db import DocumentCategory

    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()

    if not name:
        return jsonify({'error': '分类名称不能为空'}), 400

    try:
        category_id = DocumentCategory.add_custom_category(name)
        logger.info(f"创建自定义分类: {category_id} - {name}")
        return jsonify({
            'success': True,
            'message': f'分类 "{name}" 创建成功',
            'category': {
                'id': category_id,
                'name': name
            }
        })
    except ValueError as e:
        logger.warning(f"创建分类失败: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"创建分类失败: {e}")
        return jsonify({'error': f'创建分类失败: {str(e)}'}), 500


@app.route('/api/kb/custom-categories/<category_id>', methods=['DELETE'])
@admin_required
def delete_custom_category(category_id):
    """删除自定义文档分类（仅管理员）

    只能删除自定义分类，不能删除预设分类
    """
    from build_db import DocumentCategory

    try:
        # 检查是否是预设分类
        preset_ids = ['regulations', 'procedures', 'campus_life', 'teaching', 'other']
        if category_id in preset_ids:
            return jsonify({'error': '不能删除预设分类'}), 400

        # 删除分类
        success = DocumentCategory.delete_custom_category(category_id)

        if success:
            logger.info(f"删除自定义分类: {category_id}")
            return jsonify({
                'success': True,
                'message': '分类已删除'
            })
        else:
            return jsonify({'error': '分类不存在'}), 404

    except Exception as e:
        logger.error(f"删除分类失败: {e}")
        return jsonify({'error': f'删除分类失败: {str(e)}'}), 500


@app.route('/api/kb/documents', methods=['GET'])
@admin_required
def get_documents_by_category():
    """获取按分类组织的文档列表（仅管理员）"""
    kb = get_kb_builder()
    if not kb:
        return jsonify({'error': f'知识库服务当前不可用: {get_service_error_message()}'}), 503
    return jsonify(kb.list_documents_by_category())


@app.route('/api/students', methods=['GET'])
@admin_required
def get_students():
    """获取学生列表（仅管理员）
    
    支持按分类筛选: GET /api/students?category_id=xxx
    不提供 category_id 时返回所有学生
    """
    category_id = request.args.get('category_id')
    
    try:
        if category_id:
            # 获取指定分类下的学生
            students = db.get_users_by_category(category_id)
            # 格式化返回数据
            students = [
                {
                    'user_id': s['user_id'],
                    'username': s['username'],
                    'name': s['name'],
                    'category_id': s.get('category_id')
                }
                for s in students
            ]
            logger.info(f"获取分类学生列表: category_id={category_id}, 数量={len(students)}")
        else:
            # 获取所有学生
            students = user_manager.list_students()
            logger.info(f"获取所有学生列表: 数量={len(students)}")
        
        return jsonify(students)
    except Exception as e:
        logger.error(f"获取学生列表失败: {e}")
        return jsonify({'error': f'获取学生列表失败: {str(e)}'}), 500


@app.route('/api/students', methods=['POST'])
@admin_required
def create_student():
    """创建学生账号（仅管理员）
    
    支持字段:
    - username: 学号（必填）
    - name: 姓名（必填）
    - password: 密码（必填）
    - category_id: 分类ID（可选，默认为 'cat_default'）
    """
    data = request.get_json(silent=True) or {}
    
    username = data.get('username', '').strip()
    name = data.get('name', '').strip()
    password = data.get('password', '')
    category_id = (data.get('category_id') or 'cat_default').strip()
    
    if not username or not name or not password:
        return jsonify({'error': '请填写所有必填字段（username, name, password）'}), 400
    
    try:
        # 创建用户
        success = user_manager.add_user(username, password, 'student', name, category_id=category_id)
        
        if not success:
            return jsonify({'error': '该学号已存在'}), 400

        logger.info(f"学生账号已创建: {username}, 分类: {category_id}")
        return jsonify({
            'success': True, 
            'message': f'学生账号 {username} 创建成功',
            'username': username,
            'category_id': category_id
        })
    except ValueError as e:
        logger.error(f"创建学生账号失败: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"创建学生账号失败: {e}")
        return jsonify({'error': f'创建失败: {str(e)}'}), 500


@app.route('/api/students/<username>', methods=['DELETE'])
@admin_required
def delete_student(username):
    """删除学生账号（仅管理员）"""
    success = user_manager.delete_user(username)
    
    if success:
        logger.info(f"学生账号已删除: {username}")
        return jsonify({'success': True, 'message': f'学生账号 {username} 已删除'})
    else:
        return jsonify({'error': '删除失败，账号不存在或为管理员账号'}), 400


# ==================== 学生分类管理 API ====================

@app.route('/api/student-categories', methods=['GET'])
@admin_required
def get_student_categories():
    """获取所有学生分类列表（仅管理员）"""
    try:
        categories = db.list_categories()
        logger.info(f"获取学生分类列表: 数量={len(categories)}")
        return jsonify(categories)
    except Exception as e:
        logger.error(f"获取学生分类列表失败: {e}")
        return jsonify({'error': f'获取分类列表失败: {str(e)}'}), 500


@app.route('/api/student-categories', methods=['POST'])
@admin_required
def create_student_category():
    """创建新学生分类（仅管理员）
    
    请求体:
    - name: 分类名称（必填）
    """
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()
    
    if not name:
        return jsonify({'error': '分类名称不能为空'}), 400
    
    try:
        # 生成唯一分类ID
        category_id = f"cat_{uuid.uuid4().hex[:8]}"
        
        db.create_category(category_id, name, description=description)

        logger.info(f"学生分类已创建: {category_id}, 名称: {name}")
        return jsonify({
            'success': True,
            'message': f'分类 "{name}" 创建成功',
            'category_id': category_id,
            'name': name,
            'description': description
        })
    except Exception as e:
        logger.error(f"创建学生分类失败: {e}")
        return jsonify({'error': f'创建分类失败: {str(e)}'}), 500


@app.route('/api/student-categories/<category_id>', methods=['DELETE'])
@admin_required
def delete_student_category(category_id):
    """删除学生分类（仅管理员）
    
    仅当分类下没有学生时才能删除
    """
    try:
        db.delete_category(category_id)
        
        logger.info(f"学生分类已删除: {category_id}")
        return jsonify({
            'success': True,
            'message': f'分类已删除'
        })
    except ValueError as e:
        logger.warning(f"删除学生分类失败: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"删除学生分类失败: {e}")
        return jsonify({'error': f'删除分类失败: {str(e)}'}), 500


@app.route('/api/student-tree', methods=['GET'])
@admin_required
def get_student_tree():
    """获取学生分类树（仅管理员）
    
    返回按分类组织的学生树结构:
    {
        categories: [
            {
                category_id: "xxx",
                name: "分类名称",
                students: [
                    {user_id, username, name}
                ]
            }
        ],
        uncategorized: [
            {user_id, username, name}
        ]
    }
    """
    try:
        tree_data = db.get_student_tree()
        
        # 格式化返回数据
        result = {
            'categories': [
                {
                    'category_id': cat['category_id'],
                    'name': cat['name'],
                    'students': [
                        {
                            'user_id': s['user_id'],
                            'username': s['username'],
                            'name': s['name']
                        }
                        for s in cat.get('students', [])
                    ]
                }
                for cat in tree_data.get('categories', [])
            ],
            'uncategorized': [
                {
                    'user_id': s['user_id'],
                    'username': s['username'],
                    'name': s['name']
                }
                for s in tree_data.get('uncategorized', [])
            ]
        }
        
        total_students = sum(len(cat['students']) for cat in result['categories']) + len(result['uncategorized'])
        logger.info(f"获取学生分类树: 分类数={len(result['categories'])}, 学生总数={total_students}")
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"获取学生分类树失败: {e}")
        return jsonify({'error': f'获取学生分类树失败: {str(e)}'}), 500


@app.route('/api/kb/upload', methods=['POST'])
@admin_required
def upload_document():
    """上传文档到知识库（仅管理员）"""
    if 'file' not in request.files:
        return jsonify({'error': '没有文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '文件名为空'}), 400

    allowed_extensions = {'.txt', '.pdf'}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        return jsonify({'error': f'不支持的文件格式: {ext}'}), 400

    category = request.form.get('category', 'other')
    
    filename = safe_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)

    try:
        kb = get_kb_builder()
        qa = get_qa_system()
        if not kb or not qa:
            raise ValueError(get_service_error_message())

        count = kb.process_documents([file_path], category=category)
        qa.reload_vector_store()

        logger.info(f"文档上传成功: {filename}, 分类: {category}")

        return jsonify({
            'success': True,
            'message': f'成功处理 {count} 个文档片段',
            'document': filename,
            'category': category
        })
    except Exception as e:
        logger.error(f"文档处理失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/kb/documents/<doc_name>', methods=['DELETE'])
@admin_required
def delete_document(doc_name):
    """删除知识库中的文档（仅管理员）"""
    kb = get_kb_builder()
    if not kb:
        return jsonify({'error': f'知识库服务当前不可用: {get_service_error_message()}'}), 503

    success = kb.delete_document(doc_name)

    if success:
        qa = get_qa_system()
        if qa:
            qa.reload_vector_store()
        logger.info(f"文档删除成功: {doc_name}")
        return jsonify({'success': True, 'message': f'已删除 {doc_name}'})
    else:
        return jsonify({'error': '删除失败'}), 400


@app.route('/api/kb/clear', methods=['POST'])
@admin_required
def clear_kb():
    """清空知识库（仅管理员）"""
    kb = get_kb_builder()
    if not kb:
        return jsonify({'error': f'知识库服务当前不可用: {get_service_error_message()}'}), 503

    kb.clear_all()

    qa = get_qa_system()
    if qa:
        qa.reload_vector_store()
    logger.info("知识库已清空")
    return jsonify({'success': True, 'message': '知识库已清空'})


# ==================== 模型参数管理 API ====================

@app.route('/api/settings', methods=['GET'])
@admin_required
def get_settings():
    """
    获取所有模型配置与参数（仅管理员）

    支持按类别筛选: GET /api/settings?category=llm
    类别: llm - 大语言模型参数, embedding - 嵌入模型参数
    """
    try:
        category = request.args.get('category')
        settings = db.get_all_settings(category=category)

        logger.info(f"获取模型参数: category={category}, 数量={len(settings)}")
        return jsonify({
            'success': True,
            'settings': settings
        })
    except ValueError as e:
        logger.warning(f"获取参数失败: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"获取参数失败: {e}")
        return jsonify({'error': f'获取参数失败: {str(e)}'}), 500


@app.route('/api/settings', methods=['POST'])
@admin_required
def update_setting():
    """
    更新模型配置或参数（仅管理员）

    请求体:
    - key: 参数键名（必填）
    - value: 参数值（必填）

    支持的参数:
    - llm_provider: LLM 供应商
    - llm_base_url: LLM 接口基地址
    - llm_api_key: LLM 接口 API Key
    - llm_model: LLM 模型名
    - llm_temperature: 温度参数 (0.0-2.0)
    - llm_max_tokens: 最大token数 (100-8192)
    - llm_top_p: 核采样参数 (0.0-1.0)
    - llm_frequency_penalty: 频率惩罚 (-2.0-2.0)
    - llm_presence_penalty: 存在惩罚 (-2.0-2.0)
    - embedding_provider: Embedding 供应商
    - embedding_base_url: Embedding 接口基地址
    - embedding_api_key: Embedding 接口 API Key
    - embedding_model: Embedding 模型名
    - embedding_chunk_size: 分块大小 (100-2000)
    - embedding_chunk_overlap: 重叠大小 (0-500)
    - embedding_retrieval_k: 检索数量 (1-10)
    """
    data = request.get_json(silent=True) or {}

    if not data:
        return jsonify({'error': '请求体不能为空'}), 400

    key = data.get('key')
    value = data.get('value')

    if not key:
        return jsonify({'error': '参数 key 不能为空'}), 400

    if value is None:
        return jsonify({'error': '参数 value 不能为空'}), 400

    # 验证参数
    is_valid, error_msg = Config.validate_setting(key, value)
    if not is_valid:
        logger.warning(f"参数验证失败: {error_msg}")
        return jsonify({'error': error_msg}), 400

    try:
        # 更新数据库中的参数
        success = db.set_setting(key, value)

        if success:
            logger.info(f"参数更新成功: {key} = {value}")
            message = f'参数 {key} 已更新为 {value}'
            embedding_config_keys = {
                'embedding_provider',
                'embedding_base_url',
                'embedding_api_key',
                'embedding_model',
            }
            builder_reload_keys = {
                'embedding_chunk_size',
                'embedding_chunk_overlap',
                'embedding_batch_size',
                'embedding_max_workers',
            }
            vector_store_exists = os.path.exists(Config.VECTOR_DB_PATH) and bool(os.listdir(Config.VECTOR_DB_PATH))

            # 重新加载相关组件的设置
            try:
                if key.startswith('llm_'):
                    clear_service_cache('qa')
                    qa = get_qa_system()
                    if qa:
                        logger.info("问答系统设置已重新加载")
                elif key in embedding_config_keys and not vector_store_exists:
                    clear_service_cache('qa')
                    get_qa_system()
            except Exception as e:
                logger.warning(f"重新加载问答系统设置失败: {e}")

            # 重新加载知识库构建器设置（如果修改了 embedding 相关参数）
            if key in embedding_config_keys:
                if vector_store_exists:
                    message = 'Embedding 配置已保存。当前知识库仍基于旧嵌入模型构建，请先清空并重建知识库后再继续上传或问答。'
                else:
                    try:
                        clear_service_cache('kb')
                        kb = get_kb_builder()
                        if kb:
                            logger.info("知识库构建器设置已重新加载")
                    except Exception as e:
                        logger.warning(f"重新加载知识库构建器设置失败: {e}")
            elif key in builder_reload_keys:
                try:
                    clear_service_cache('kb')
                    kb = get_kb_builder()
                    if kb:
                        logger.info("知识库构建器设置已重新加载")
                except Exception as e:
                    logger.warning(f"重新加载知识库构建器设置失败: {e}")

            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({'error': '参数更新失败'}), 500

    except ValueError as e:
        logger.warning(f"更新参数失败: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"更新参数失败: {e}")
        return jsonify({'error': f'更新参数失败: {str(e)}'}), 500


@app.route('/api/settings/reset', methods=['POST'])
@admin_required
def reset_settings():
    """
    恢复所有参数为默认值（仅管理员）

    此操作会将所有模型参数恢复为系统默认值
    """
    try:
        success = db.reset_settings_to_default()

        if success:
            logger.info("所有参数已恢复为默认值")
            clear_service_cache()

            # 重新加载相关组件的设置
            try:
                qa = get_qa_system()
                if qa:
                    logger.info("问答系统设置已重新加载")
            except Exception as e:
                logger.warning(f"重新加载问答系统设置失败: {e}")

            # 重新加载知识库构建器设置
            try:
                kb = get_kb_builder()
                if kb:
                    logger.info("知识库构建器设置已重新加载")
            except Exception as e:
                logger.warning(f"重新加载知识库构建器设置失败: {e}")

            return jsonify({
                'success': True,
                'message': '所有参数已恢复为默认值'
            })
        else:
            return jsonify({'error': '恢复默认参数失败'}), 500

    except Exception as e:
        logger.error(f"恢复默认参数失败: {e}")
        return jsonify({'error': f'恢复默认参数失败: {str(e)}'}), 500


def open_browser():
    """自动打开浏览器"""
    import webbrowser
    import time
    time.sleep(1.5)
    webbrowser.open(f'http://localhost:{Config.FLASK_PORT}')


if __name__ == '__main__':
    import threading

    print("=" * 50)
    print("高校事务智能问答系统 (Flask)")
    print("=" * 50)
    print(f"\n启动中...")
    print(f"访问地址: http://localhost:{Config.FLASK_PORT}")
    print("\n按 Ctrl+C 停止服务")
    print("=" * 50 + "\n")

    browser_thread = threading.Thread(target=open_browser)
    browser_thread.daemon = True
    browser_thread.start()

    app.run(
        host=Config.FLASK_HOST,
        port=Config.FLASK_PORT,
        debug=Config.FLASK_DEBUG,
        use_reloader=False
    )
